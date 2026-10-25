from django.conf import settings
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Patient
from apps.accounts.views import get_visible_patient
from apps.audit import service as audit
from apps.clinic.models import Doctor
from apps.clinic.serializers import DoctorSerializer
from apps.core import clock
from apps.core.exceptions import DateInPast, DoctorNotFound, SlotTooFarAhead

from . import services
from .models import Appointment
from .serializers import (
    AppointmentSerializer,
    AvailabilityQuerySerializer,
    BookAppointmentSerializer,
    CancelAppointmentSerializer,
    RescheduleAppointmentSerializer,
)


class BookingThrottleMixin:
    """Tighter rate limit on state-changing booking calls (anti slot-hoarding)."""

    throttle_scope = "booking"
    throttle_classes = [ScopedRateThrottle, UserRateThrottle]


class DoctorListView(ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.filter(is_active=True)
    pagination_class = None


class DoctorAvailabilityView(APIView):
    """Public: exposes only *free* slots, never who holds a booked one (no PII)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        parameters=[OpenApiParameter("date", str, description="YYYY-MM-DD (clinic local date)")],
        responses={200: dict},
    )
    def get(self, request, doctor_id):
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        day = query.validated_data["date"]

        try:
            doctor = Doctor.objects.get(pk=doctor_id, is_active=True)
        except Doctor.DoesNotExist:
            raise DoctorNotFound() from None

        today = clock.now().astimezone(settings.CLINIC_TZ).date()
        if day < today:
            raise DateInPast()
        if (day - today).days > settings.BOOKING_MAX_ADVANCE_DAYS:
            raise SlotTooFarAhead(
                f"Availability is only published {settings.BOOKING_MAX_ADVANCE_DAYS} days ahead."
            )

        slots = services.available_slots(doctor, day)
        tz = settings.CLINIC_TZ
        return Response(
            {
                "doctor_id": doctor.pk,
                "doctor_name": doctor.full_name,
                "date": day.isoformat(),
                "timezone": settings.CLINIC_TIMEZONE_NAME,
                "slot_minutes": doctor.slot_minutes,
                "slots": [
                    {"start": s.astimezone(tz).isoformat(), "end": e.astimezone(tz).isoformat()}
                    for s, e in slots
                ],
            }
        )


class AppointmentCreateView(BookingThrottleMixin, APIView):
    @extend_schema(request=BookAppointmentSerializer, responses={201: AppointmentSerializer})
    def post(self, request):
        ser = BookAppointmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if request.user.is_staff:
            if "patient_id" not in data:
                raise ValidationError(
                    {"patient_id": ["Required when booking on behalf of a patient."]}
                )
            patient = services.get_patient(data["patient_id"])
        else:
            patient = Patient.objects.filter(user=request.user, anonymised_at__isnull=True).first()
            if patient is None:
                raise PermissionDenied("This account has no patient profile.")
            if "patient_id" in data and data["patient_id"] != patient.pk:
                raise PermissionDenied("You can only book appointments for yourself.")

        appointment = services.book_appointment(
            patient=patient,
            doctor_id=data["doctor_id"],
            start=data["start_time"],
            actor=request.user,
        )
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


class AppointmentDetailView(APIView):
    @extend_schema(responses={200: AppointmentSerializer})
    def get(self, request, appointment_id):
        appointment = (
            Appointment.objects.visible_to(request.user)
            .select_related("doctor")
            .filter(pk=appointment_id)
            .first()
        )
        if appointment is None:
            raise Http404
        return Response(AppointmentSerializer(appointment).data)


def _visible_or_404(user, appointment_id):
    if not Appointment.objects.visible_to(user).filter(pk=appointment_id).exists():
        raise Http404


class AppointmentCancelView(BookingThrottleMixin, APIView):
    @extend_schema(request=CancelAppointmentSerializer, responses={200: AppointmentSerializer})
    def patch(self, request, appointment_id):
        _visible_or_404(request.user, appointment_id)
        ser = CancelAppointmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        appointment = services.cancel_appointment(
            appointment_id=appointment_id,
            actor=request.user,
            reason=ser.validated_data["reason"],
            reason_code=ser.validated_data.get("reason_code", Appointment.CancelReason.OTHER),
        )
        return Response(AppointmentSerializer(appointment).data)


class AppointmentRescheduleView(BookingThrottleMixin, APIView):
    @extend_schema(request=RescheduleAppointmentSerializer, responses={200: AppointmentSerializer})
    def patch(self, request, appointment_id):
        _visible_or_404(request.user, appointment_id)
        ser = RescheduleAppointmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        appointment = services.reschedule_appointment(
            appointment_id=appointment_id,
            actor=request.user,
            new_start=ser.validated_data["start_time"],
        )
        return Response(AppointmentSerializer(appointment).data)


class PatientAppointmentsView(APIView):
    """Upcoming (future, still-booked) appointments for a patient, soonest first."""

    @extend_schema(responses={200: AppointmentSerializer(many=True)})
    def get(self, request, patient_id):
        patient = get_visible_patient(request.user, patient_id)
        upcoming = (
            Appointment.objects.filter(
                patient=patient, status=Appointment.Status.BOOKED, start_time__gte=clock.now()
            )
            .select_related("doctor")
            .order_by("start_time")
        )
        audit.record(request.user, "patient.appointments.view", "patient", patient.pk)
        return Response(AppointmentSerializer(upcoming, many=True).data)
