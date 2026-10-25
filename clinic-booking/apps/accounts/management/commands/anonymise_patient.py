"""Erasure request handling (DPA 2019 right to erasure).

Clinical/appointment history may have to be retained by law, so we *anonymise* instead of
deleting: identity is removed, future appointments are cancelled, the login is deleted.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Patient
from apps.appointments.models import Appointment
from apps.audit import service as audit
from apps.core import clock


class Command(BaseCommand):
    help = "Anonymise a patient's personal data by patient id."

    def add_arguments(self, parser):
        parser.add_argument("patient_id")

    @transaction.atomic
    def handle(self, *args, patient_id, **options):
        try:
            patient = Patient.objects.select_for_update().get(pk=patient_id)
        except (Patient.DoesNotExist, ValueError):
            raise CommandError("Patient not found.") from None
        if patient.anonymised_at:
            raise CommandError("Patient is already anonymised.")

        now = clock.now()
        future = Appointment.objects.filter(
            patient=patient, status=Appointment.Status.BOOKED, start_time__gt=now
        )
        cancelled = future.update(
            status=Appointment.Status.CANCELLED,
            cancel_reason_code=Appointment.CancelReason.OTHER,
            cancel_note="Patient data erased",
            cancelled_at=now,
        )
        user = patient.user
        patient.full_name = "Anonymised"
        patient.phone = patient.email = patient.guardian_name = patient.guardian_phone = ""
        patient.user = None
        patient.anonymised_at = now
        patient.save()
        if user:
            user.delete()
        audit.record(None, "patient.anonymise", "patient", patient.pk, cancelled_future=cancelled)
        self.stdout.write(
            self.style.SUCCESS(f"Anonymised patient {patient.pk}; cancelled {cancelled}.")
        )
