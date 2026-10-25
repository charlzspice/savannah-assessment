from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.appointments.models import Appointment
from apps.appointments.serializers import AppointmentSerializer
from apps.audit import service as audit

from .models import Patient
from .serializers import PatientCreateSerializer, PatientSerializer, RegisterSerializer


class RegisterView(APIView):
    """Patient self-registration (creates a login + patient profile + consent record)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"
    throttle_classes = [ScopedRateThrottle]

    @extend_schema(request=RegisterSerializer, responses={201: PatientSerializer})
    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        patient = ser.save()
        audit.record(patient.user, "patient.register", "patient", patient.pk)
        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)


class PatientCreateView(APIView):
    """Staff registers a patient who has no online account."""

    permission_classes = [IsAdminUser]

    @extend_schema(request=PatientCreateSerializer, responses={201: PatientSerializer})
    def post(self, request):
        ser = PatientCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        patient = ser.save()
        audit.record(request.user, "patient.create", "patient", patient.pk)
        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)


def get_visible_patient(user, patient_id) -> Patient:
    """Staff may see any patient; a patient only themselves. Everything else is a 404."""
    qs = Patient.objects.filter(pk=patient_id)
    if not user.is_staff:
        qs = qs.filter(user=user)
    patient = qs.first()
    if patient is None:
        raise Http404
    return patient


class PatientExportView(APIView):
    """Data-subject access / portability (DPA 2019): everything we hold about a patient."""

    @extend_schema(responses={200: dict})
    def get(self, request, patient_id):
        patient = get_visible_patient(request.user, patient_id)
        appointments = Appointment.objects.filter(patient=patient).select_related("doctor")
        audit.record(request.user, "patient.export", "patient", patient.pk)
        return Response(
            {
                "patient": PatientSerializer(patient).data,
                "appointments": AppointmentSerializer(appointments, many=True).data,
            }
        )


class LoginView(TokenObtainPairView):
    """Exchange email + password for a short-lived access token and a refresh token."""

    throttle_scope = "auth"
    throttle_classes = [ScopedRateThrottle]
