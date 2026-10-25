from datetime import time

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Patient
from apps.appointments.tests.helpers import FIXED_NOW
from apps.clinic.models import Doctor, WorkingSchedule

User = get_user_model()


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr("apps.core.clock.now", lambda: FIXED_NOW)
    return FIXED_NOW


def _make_doctor(name, blocks=((8, 12), (13, 17)), weekdays=(0, 1, 2, 3, 4)):
    doctor = Doctor.objects.create(full_name=name, specialty="General")
    for wd in weekdays:
        for start, end in blocks:
            WorkingSchedule.objects.create(
                doctor=doctor, weekday=wd, start_time=time(start), end_time=time(end)
            )
    return doctor


@pytest.fixture
def doctor(db):
    return _make_doctor("Dr. Test One")


@pytest.fixture
def doctor2(db):
    return _make_doctor("Dr. Test Two")


@pytest.fixture
def make_patient(db):
    counter = {"n": 0}

    def _make(name="Pat Tient"):
        counter["n"] += 1
        email = f"patient{counter['n']}@example.test"
        user = User.objects.create_user(username=email, email=email, password="x" * 12)
        patient = Patient.objects.create(
            user=user,
            full_name=name,
            phone="+254700000001",
            email=email,
            consent_given_at=timezone.now(),
            consent_notice_version="test",
        )
        return patient

    return _make


@pytest.fixture
def patient(make_patient):
    return make_patient("Alice Patient")


@pytest.fixture
def other_patient(make_patient):
    return make_patient("Bob Other")


@pytest.fixture
def staff(db):
    return User.objects.create_user(username="staff@example.test", password="x" * 12, is_staff=True)


@pytest.fixture
def api():
    def _client(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return _client
