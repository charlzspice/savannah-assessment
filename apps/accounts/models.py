import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    r"^\+?[0-9]{9,15}$", "Enter a phone number with 9-15 digits, optionally starting with +."
)


class Patient(models.Model):
    """Minimal patient record. Deliberately holds NO clinical data, national ID or diagnosis
    (data minimisation, DPA 2019). UUID primary key: ids are not guessable/enumerable."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient",
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    # Children's data gets special treatment under the DPA: record the guardian.
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    # Consent evidence: when, and against which version of the privacy notice.
    consent_given_at = models.DateTimeField()
    consent_notice_version = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    anonymised_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):  # never include PII in string representations (they end up in logs)
        return f"Patient<{self.id}>"
