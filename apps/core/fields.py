from datetime import UTC

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers


class AwareDateTimeField(serializers.DateTimeField):
    """Input: ISO-8601 *with* a UTC offset (e.g. 2026-11-03T09:00:00+03:00).
    Naive times are rejected rather than guessed - guessing the zone of a medical appointment
    is how people turn up three hours early. Internally normalised to UTC."""

    def enforce_timezone(self, value):
        if timezone.is_naive(value):
            raise serializers.ValidationError(
                "Datetime must include a UTC offset, e.g. 2026-11-03T09:00:00+03:00."
            )
        return value.astimezone(UTC)


class ClinicDateTimeField(serializers.DateTimeField):
    """Output: rendered in clinic-local time so clients see the time patients actually attend."""

    def to_representation(self, value):
        return value.astimezone(settings.CLINIC_TZ).isoformat() if value else None
