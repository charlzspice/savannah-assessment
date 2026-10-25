"""Booking business logic. Views stay thin; everything testable lives here.

Concurrency model: validation does friendly pre-checks, but the *authoritative* guard is the
partial unique constraint on (doctor, start_time) WHERE status='booked'. Two simultaneous
requests can both pass a pre-check; the database lets only one INSERT/UPDATE win and the
loser's IntegrityError is translated into a 409.
"""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import Http404

from apps.accounts.models import Patient
from apps.audit import service as audit
from apps.clinic.models import Doctor
from apps.clinic.slots import clinic_day_bounds_utc, slot_starts_for_day, working_hours_summary
from apps.core import clock
from apps.core.exceptions import (
    AlreadyCancelled,
    AppointmentCancelled,
    AppointmentInPast,
    DoctorNotFound,
    OutsideWorkingHours,
    PatientDoubleBooked,
    PatientNotFound,
    SameSlot,
    SlotInPast,
    SlotTaken,
    SlotTooFarAhead,
    SlotTooSoon,
)

from .models import Appointment

ACTIVE = Appointment.Status.BOOKED


def get_active_doctor(doctor_id) -> Doctor:
    try:
        return Doctor.objects.get(pk=doctor_id, is_active=True)
    except Doctor.DoesNotExist:
        raise DoctorNotFound() from None


def get_patient(patient_id) -> Patient:
    try:
        return Patient.objects.get(pk=patient_id, anonymised_at__isnull=True)
    except Patient.DoesNotExist:
        raise PatientNotFound() from None


def validate_bookable_slot(doctor: Doctor, start, *, exclude_appointment=None, patient=None):
    """Raise a DomainError unless `start` is a bookable slot. Used identically for new
    bookings and reschedules so the two paths can never drift apart."""
    now = clock.now()
    if start <= now:
        raise SlotInPast()
    min_start = now + timedelta(minutes=settings.BOOKING_MIN_LEAD_MINUTES)
    if start < min_start:
        raise SlotTooSoon(
            f"Appointments must be booked at least {settings.BOOKING_MIN_LEAD_MINUTES} minutes "
            "in advance.",
            extra={"earliest_bookable": min_start.astimezone(settings.CLINIC_TZ).isoformat()},
        )
    if start > now + timedelta(days=settings.BOOKING_MAX_ADVANCE_DAYS):
        raise SlotTooFarAhead(
            f"Appointments can be booked at most {settings.BOOKING_MAX_ADVANCE_DAYS} days ahead."
        )

    local_start = start.astimezone(settings.CLINIC_TZ)
    # aware datetimes compare/hash by instant, so tz differences don't matter here
    if start not in set(slot_starts_for_day(doctor, local_start.date())):
        raise OutsideWorkingHours(
            "That time is not an available slot. "
            + working_hours_summary(doctor, local_start.date())
        )

    taken = Appointment.objects.filter(doctor=doctor, start_time=start, status=ACTIVE)
    if exclude_appointment is not None:
        taken = taken.exclude(pk=exclude_appointment.pk)
    if taken.exists():
        raise SlotTaken()

    if patient is not None:
        clash = Appointment.objects.filter(patient=patient, start_time=start, status=ACTIVE)
        if exclude_appointment is not None:
            clash = clash.exclude(pk=exclude_appointment.pk)
        if clash.exists():
            raise PatientDoubleBooked()


def book_appointment(*, patient: Patient, doctor_id, start, actor) -> Appointment:
    doctor = get_active_doctor(doctor_id)
    with transaction.atomic():
        validate_bookable_slot(doctor, start, patient=patient)
        try:
            with transaction.atomic():  # savepoint: keep outer transaction usable after a conflict
                appointment = Appointment.objects.create(
                    doctor=doctor,
                    patient=patient,
                    start_time=start,
                    end_time=start + timedelta(minutes=doctor.slot_minutes),
                )
        except IntegrityError:
            raise SlotTaken() from None
        audit.record(
            actor,
            "appointment.book",
            "appointment",
            appointment.pk,
            doctor_id=doctor.pk,
            patient_id=str(patient.pk),
        )
    return appointment


def _lock(appointment_id) -> Appointment:
    try:
        return (
            Appointment.objects.select_for_update().select_related("doctor").get(pk=appointment_id)
        )
    except Appointment.DoesNotExist:
        raise Http404 from None


def cancel_appointment(*, appointment_id, actor, reason: str, reason_code: str) -> Appointment:
    with transaction.atomic():
        appointment = _lock(appointment_id)
        if appointment.status == Appointment.Status.CANCELLED:
            raise AlreadyCancelled()
        if appointment.start_time <= clock.now():
            raise AppointmentInPast()
        appointment.status = Appointment.Status.CANCELLED
        appointment.cancel_reason_code = reason_code
        appointment.cancel_note = reason
        appointment.cancelled_at = clock.now()
        appointment.cancelled_by = actor if getattr(actor, "pk", None) else None
        appointment.save()
        # The reason text is deliberately NOT written to the audit trail (may be sensitive).
        audit.record(
            actor, "appointment.cancel", "appointment", appointment.pk, reason_code=reason_code
        )
    return appointment


def reschedule_appointment(*, appointment_id, new_start, actor) -> Appointment:
    with transaction.atomic():
        appointment = _lock(appointment_id)
        if appointment.status == Appointment.Status.CANCELLED:
            raise AppointmentCancelled()
        if appointment.start_time <= clock.now():
            raise AppointmentInPast()
        if new_start == appointment.start_time:
            raise SameSlot()
        validate_bookable_slot(
            appointment.doctor,
            new_start,
            exclude_appointment=appointment,
            patient=appointment.patient,
        )
        old_start = appointment.start_time
        appointment.start_time = new_start
        appointment.end_time = new_start + timedelta(minutes=appointment.doctor.slot_minutes)
        appointment.reschedule_count += 1
        try:
            with transaction.atomic():
                appointment.save()
        except IntegrityError:
            raise SlotTaken() from None
        audit.record(
            actor,
            "appointment.reschedule",
            "appointment",
            appointment.pk,
            from_start=old_start.isoformat(),
            to_start=new_start.isoformat(),
        )
    return appointment


def available_slots(doctor: Doctor, day):
    """Bookable slots for `day`: on the grid, not booked, and respecting the lead-time rule."""
    now = clock.now()
    earliest = now + timedelta(minutes=settings.BOOKING_MIN_LEAD_MINUTES)
    lo, hi = clinic_day_bounds_utc(day)
    booked = set(
        Appointment.objects.filter(
            doctor=doctor, status=ACTIVE, start_time__gte=lo, start_time__lt=hi
        ).values_list("start_time", flat=True)
    )
    step = timedelta(minutes=doctor.slot_minutes)
    return [
        (s, s + step) for s in slot_starts_for_day(doctor, day) if s >= earliest and s not in booked
    ]
