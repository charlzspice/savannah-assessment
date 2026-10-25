import pytest

from apps.appointments.models import Appointment

from .helpers import MON, SAT, TUE, at, iso

pytestmark = pytest.mark.django_db


def book(client, doctor, start, **extra):
    return client.post(
        "/appointments", {"doctor_id": doctor.pk, "start_time": iso(start), **extra}, format="json"
    )


def err(resp):
    return resp.json()["error"]["code"]


def test_book_success(api, patient, doctor):
    resp = book(api(patient.user), doctor, at(TUE, "09:00"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "booked"
    assert body["start_time"] == "2026-11-03T09:00:00+03:00"
    assert body["end_time"] == "2026-11-03T09:30:00+03:00"
    assert body["patient_id"] == str(patient.pk)


@pytest.mark.parametrize(
    "day,hhmm",
    [
        (TUE, "07:30"),
        (TUE, "12:00"),
        (TUE, "12:30"),
        (TUE, "17:00"),
        (TUE, "09:15"),
        (SAT, "09:00"),
    ],
    ids=["before-open", "lunch-start", "lunch", "after-close", "off-grid", "weekend"],
)
def test_rejects_outside_working_hours_or_off_grid(api, patient, doctor, day, hhmm):
    resp = book(api(patient.user), doctor, at(day, hhmm))
    assert resp.status_code == 422
    assert err(resp) == "outside_working_hours"
    assert "work" in resp.json()["error"]["message"]  # tells the user the actual hours


def test_last_slot_of_the_day_is_bookable(api, patient, doctor):
    assert book(api(patient.user), doctor, at(TUE, "16:30")).status_code == 201


def test_rejects_past(api, patient, doctor):
    resp = book(api(patient.user), doctor, at(MON, "07:00"))
    assert resp.status_code == 422 and err(resp) == "slot_in_past"


def test_rejects_within_one_hour_but_allows_exactly_one_hour(api, patient, doctor):
    c = api(patient.user)
    assert err(book(c, doctor, at(MON, "08:30"))) == "slot_too_soon"  # now is 08:00
    assert book(c, doctor, at(MON, "09:00")).status_code == 201  # exactly 60 minutes ahead


def test_rejects_too_far_ahead(api, patient, doctor):
    resp = book(api(patient.user), doctor, at("2027-06-01", "09:00"))
    assert resp.status_code == 422 and err(resp) == "slot_too_far_ahead"


def test_slot_already_taken_returns_409(api, patient, other_patient, doctor):
    assert book(api(patient.user), doctor, at(TUE, "10:00")).status_code == 201
    resp = book(api(other_patient.user), doctor, at(TUE, "10:00"))
    assert resp.status_code == 409 and err(resp) == "slot_taken"


def test_same_time_with_different_doctor_is_fine_for_different_patients(
    api, patient, other_patient, doctor, doctor2
):
    assert book(api(patient.user), doctor, at(TUE, "10:00")).status_code == 201
    assert book(api(other_patient.user), doctor2, at(TUE, "10:00")).status_code == 201


def test_patient_cannot_hold_two_appointments_at_same_time(api, patient, doctor, doctor2):
    c = api(patient.user)
    assert book(c, doctor, at(TUE, "10:00")).status_code == 201
    resp = book(c, doctor2, at(TUE, "10:00"))
    assert resp.status_code == 409 and err(resp) == "patient_double_booked"


def test_naive_datetime_rejected(api, patient, doctor):
    resp = api(patient.user).post(
        "/appointments",
        {"doctor_id": doctor.pk, "start_time": "2026-11-03T09:00:00"},
        format="json",
    )
    assert resp.status_code == 400 and err(resp) == "validation_error"
    assert "offset" in str(resp.json()["error"]["details"])


def test_utc_input_is_equivalent(api, patient, doctor):
    resp = api(patient.user).post(
        "/appointments",
        {"doctor_id": doctor.pk, "start_time": "2026-11-03T06:00:00Z"},
        format="json",
    )
    assert resp.status_code == 201  # 06:00Z == 09:00 EAT


def test_unknown_doctor_404(api, patient):
    resp = api(patient.user).post(
        "/appointments", {"doctor_id": 9999, "start_time": iso(at(TUE, "09:00"))}, format="json"
    )
    assert resp.status_code == 404 and err(resp) == "doctor_not_found"


def test_inactive_doctor_not_bookable(api, patient, doctor):
    doctor.is_active = False
    doctor.save()
    assert book(api(patient.user), doctor, at(TUE, "09:00")).status_code == 404


def test_requires_authentication(api, doctor):
    assert book(api(), doctor, at(TUE, "09:00")).status_code == 401


def test_patient_cannot_book_for_someone_else(api, patient, other_patient, doctor):
    resp = book(api(patient.user), doctor, at(TUE, "09:00"), patient_id=str(other_patient.pk))
    assert resp.status_code == 403


def test_staff_must_name_patient_and_can_book_for_them(api, staff, patient, doctor):
    c = api(staff)
    assert book(c, doctor, at(TUE, "09:00")).status_code == 400
    resp = book(c, doctor, at(TUE, "09:00"), patient_id=str(patient.pk))
    assert resp.status_code == 201 and resp.json()["patient_id"] == str(patient.pk)


def test_malformed_body_is_400_with_field_details(api, patient):
    resp = api(patient.user).post("/appointments", {"doctor_id": "x"}, format="json")
    body = resp.json()["error"]
    assert resp.status_code == 400 and body["code"] == "validation_error"
    assert {"doctor_id", "start_time"} <= set(body["details"])


def test_only_one_row_created_on_conflict(api, patient, other_patient, doctor):
    book(api(patient.user), doctor, at(TUE, "10:00"))
    book(api(other_patient.user), doctor, at(TUE, "10:00"))
    assert Appointment.objects.filter(doctor=doctor, status="booked").count() == 1
