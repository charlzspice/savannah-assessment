import io

import pytest
from django.core.management import call_command

from apps.accounts.models import Patient
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog

from .helpers import TUE, at, iso

pytestmark = pytest.mark.django_db

REG = {
    "email": "new.patient@example.test",
    "password": "a-long-Passw0rd!",
    "full_name": "New Patient",
    "phone": "+254711222333",
    "consent": True,
}


def test_register_login_book_end_to_end_with_jwt(api, doctor):
    c = api()
    assert c.post("/auth/register", REG, format="json").status_code == 201
    tok = c.post(
        "/auth/token", {"username": REG["email"], "password": REG["password"]}, format="json"
    )
    assert tok.status_code == 200
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok.json()['access']}")
    resp = c.post(
        "/appointments",
        {"doctor_id": doctor.pk, "start_time": iso(at(TUE, "09:00"))},
        format="json",
    )
    assert resp.status_code == 201


def test_registration_requires_explicit_consent_and_records_it(api):
    c = api()
    assert c.post("/auth/register", {**REG, "consent": False}, format="json").status_code == 400
    assert (
        c.post(
            "/auth/register", {k: v for k, v in REG.items() if k != "consent"}, format="json"
        ).status_code
        == 400
    )
    assert c.post("/auth/register", REG, format="json").status_code == 201
    p = Patient.objects.get(email=REG["email"])
    assert p.consent_given_at and p.consent_notice_version


def test_weak_password_rejected_and_duplicate_email_not_revealing(api):
    c = api()
    assert c.post("/auth/register", {**REG, "password": "short"}, format="json").status_code == 400
    assert c.post("/auth/register", REG, format="json").status_code == 201
    dup = c.post("/auth/register", REG, format="json")
    assert dup.status_code == 400 and "already" not in dup.content.decode().lower()


def test_staff_can_register_walk_in_patient_but_patients_cannot(api, staff, patient):
    body = {"full_name": "Walk In", "phone": "+254722000111", "consent": True}
    assert api(staff).post("/patients", body, format="json").status_code == 201
    assert api(patient.user).post("/patients", body, format="json").status_code == 403


def test_export_returns_everything_held_and_is_access_controlled(
    api, patient, other_patient, doctor
):
    c = api(patient.user)
    c.post(
        "/appointments",
        {"doctor_id": doctor.pk, "start_time": iso(at(TUE, "09:00"))},
        format="json",
    )
    resp = c.get(f"/patients/{patient.pk}/export")
    assert resp.status_code == 200
    assert (
        resp.json()["patient"]["full_name"] == "Alice Patient"
        and len(resp.json()["appointments"]) == 1
    )
    assert api(other_patient.user).get(f"/patients/{patient.pk}/export").status_code == 404
    assert AuditLog.objects.filter(action="patient.export").exists()


def test_anonymise_removes_identity_cancels_future_but_keeps_history(api, patient, doctor):
    api(patient.user).post(
        "/appointments",
        {"doctor_id": doctor.pk, "start_time": iso(at(TUE, "09:00"))},
        format="json",
    )
    call_command("anonymise_patient", str(patient.pk), stdout=io.StringIO())
    patient.refresh_from_db()
    assert patient.full_name == "Anonymised" and not patient.phone and not patient.email
    assert patient.user is None and patient.anonymised_at
    appt = Appointment.objects.get(patient=patient)
    assert appt.status == "cancelled"  # record kept, slot released
    assert (
        api()
        .get(f"/doctors/{doctor.pk}/availability", {"date": TUE})
        .json()["slots"][2]["start"][11:16]
        == "09:00"
    )


def test_errors_never_leak_internals(api):
    resp = api().get("/does-not-exist")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"


def test_health_endpoint(api):
    resp = api().get("/health")
    assert resp.status_code == 200 and resp.json()["status"] == "ok"
