"""Single source of 'now' so tests can pin time deterministically."""

from django.utils import timezone


def now():
    return timezone.now()
