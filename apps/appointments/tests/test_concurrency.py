"""Proves double-booking is impossible under real concurrency (needs PostgreSQL)."""

import threading

import pytest
from django.db import IntegrityError, connection, connections, transaction

from apps.appointments import services
from apps.appointments.models import Appointment
from apps.core.exceptions import SlotTaken

from .helpers import TUE, at

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="needs PostgreSQL row/constraint semantics"
    ),
]


def test_parallel_bookings_for_one_slot_yield_exactly_one_winner(doctor, make_patient):
    patients = [make_patient(f"P{i}") for i in range(8)]
    start = at(TUE, "09:00")
    barrier = threading.Barrier(len(patients))
    results = []

    def attempt(p):
        try:
            barrier.wait()
            services.book_appointment(patient=p, doctor_id=doctor.pk, start=start, actor=p.user)
            results.append("ok")
        except SlotTaken:
            results.append("taken")
        except Exception as exc:  # noqa: BLE001
            results.append(f"unexpected:{exc!r}")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=(p,)) for p in patients]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert results.count("ok") == 1, results
    assert results.count("taken") == len(patients) - 1, results
    assert Appointment.objects.filter(doctor=doctor, start_time=start, status="booked").count() == 1


def test_database_itself_refuses_a_second_booked_row(doctor, patient, other_patient):
    """Even code that bypasses the service layer cannot create a double booking."""
    start = at(TUE, "10:00")
    Appointment.objects.create(
        doctor=doctor, patient=patient, start_time=start, end_time=at(TUE, "10:30")
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Appointment.objects.create(
            doctor=doctor, patient=other_patient, start_time=start, end_time=at(TUE, "10:30")
        )
    # ...but a cancelled row does not hold the slot
    Appointment.objects.filter(doctor=doctor).update(status="cancelled")
    Appointment.objects.create(
        doctor=doctor, patient=other_patient, start_time=start, end_time=at(TUE, "10:30")
    )
