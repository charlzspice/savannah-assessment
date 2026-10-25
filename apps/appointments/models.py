import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class AppointmentQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Object-level access control: staff see everything, patients only their own.
        Non-visible rows behave as non-existent (404, not 403) so ids can't be probed."""
        if user.is_staff:
            return self
        return self.filter(patient__user=user)


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked"
        CANCELLED = "cancelled"

    class CancelReason(models.TextChoices):
        PATIENT_REQUEST = "patient_request"
        DOCTOR_UNAVAILABLE = "doctor_unavailable"
        SCHEDULE_CLASH = "schedule_clash"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        "clinic.Doctor", on_delete=models.PROTECT, related_name="appointments"
    )
    patient = models.ForeignKey(
        "accounts.Patient", on_delete=models.PROTECT, related_name="appointments"
    )
    start_time = models.DateTimeField()  # stored in UTC
    end_time = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.BOOKED)

    cancel_reason_code = models.CharField(max_length=24, choices=CancelReason.choices, blank=True)
    # Free text can contain health information -> treated as sensitive: length-limited,
    # never logged, never copied into the audit trail.
    cancel_note = models.CharField(max_length=200, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reschedule_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppointmentQuerySet.as_manager()

    class Meta:
        ordering = ["start_time"]
        constraints = [
            # THE double-booking guarantee lives in the database, not in application code.
            # Partial: cancelled rows don't hold the slot, so cancelling frees it for free.
            models.UniqueConstraint(
                fields=["doctor", "start_time"],
                condition=Q(status="booked"),
                name="uniq_booked_slot_per_doctor",
            ),
            models.UniqueConstraint(
                fields=["patient", "start_time"],
                condition=Q(status="booked"),
                name="uniq_booked_slot_per_patient",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="appt_end_after_start"
            ),
        ]
        indexes = [
            models.Index(fields=["patient", "status", "start_time"]),
            models.Index(fields=["doctor", "start_time"]),
        ]

    def __str__(self):
        return f"Appointment<{self.id}>"
