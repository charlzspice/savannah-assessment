import pytest

from apps.appointments.models import Appointment
from apps.audit.models import AuditLog

from .helpers import MON, TUE, WED, at, iso

pytestmark = pytest.mark.django_db


def make(client, doctor, start):
    r = client.post(
        "/appointments", {"doctor_id": doctor.pk, "start_time": iso(start)}, format="json"
    )
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def cancel(client, appt_id, **body):
    body.setdefault("reason", "Cannot make it")
    return client.patch(f"/appointments/{appt_id}/cancel", body, format="json")


def resched(client, appt_id, start):
    return client.patch(
        f"/appointments/{appt_id}/reschedule", {"start_time": iso(start)}, format="json"
    )


def code(resp):
    return resp.json()["error"]["code"]


# ---------- cancel ----------
def test_cancel_records_reason_and_frees_slot(api, patient, other_patient, doctor):
    c = api(patient.user)
    appt_id = make(c, doctor, at(TUE, "09:00"))
    resp = cancel(c, appt_id, reason="Travelling", reason_code="patient_request")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled" and body["cancel_note"] == "Travelling"
    assert body["cancel_reason_code"] == "patient_request" and body["cancelled_at"]
    # slot is bookable again - by someone else
    assert make(api(other_patient.user), doctor, at(TUE, "09:00"))


def test_cancel_twice_is_409(api, patient, doctor):
    c = api(patient.user)
    appt_id = make(c, doctor, at(TUE, "09:00"))
    assert cancel(c, appt_id).status_code == 200
    again = cancel(c, appt_id)
    assert again.status_code == 409 and code(again) == "already_cancelled"


def test_cancel_requires_reason(api, patient, doctor):
    c = api(patient.user)
    appt_id = make(c, doctor, at(TUE, "09:00"))
    resp = c.patch(f"/appointments/{appt_id}/cancel", {}, format="json")
    assert resp.status_code == 400 and "reason" in resp.json()["error"]["details"]
    assert cancel(c, appt_id, reason="x" * 201).status_code == 400  # length-limited


def test_cancel_unknown_appointment_404(api, patient):
    assert cancel(api(patient.user), "00000000-0000-0000-0000-000000000000").status_code == 404


def test_cannot_cancel_someone_elses_appointment(api, patient, other_patient, doctor):
    appt_id = make(api(patient.user), doctor, at(TUE, "09:00"))
    resp = cancel(api(other_patient.user), appt_id)
    assert resp.status_code == 404  # not 403: existence is not revealed
    assert Appointment.objects.get(pk=appt_id).status == "booked"


def test_staff_can_cancel_any_appointment(api, staff, patient, doctor):
    appt_id = make(api(patient.user), doctor, at(TUE, "09:00"))
    assert cancel(api(staff), appt_id, reason_code="doctor_unavailable").status_code == 200


def test_cannot_cancel_appointment_that_already_started(api, patient, doctor):
    appt = Appointment.objects.create(
        doctor=doctor, patient=patient, start_time=at(MON, "07:00"), end_time=at(MON, "07:30")
    )
    resp = cancel(api(patient.user), appt.pk)
    assert resp.status_code == 409 and code(resp) == "appointment_in_past"


# ---------- reschedule ----------
def test_reschedule_moves_appointment_and_frees_original(api, patient, other_patient, doctor):
    c = api(patient.user)
    appt_id = make(c, doctor, at(TUE, "09:00"))
    resp = resched(c, appt_id, at(WED, "10:00"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == appt_id and body["start_time"] == "2026-11-04T10:00:00+03:00"
    assert body["end_time"] == "2026-11-04T10:30:00+03:00" and body["reschedule_count"] == 1
    assert make(api(other_patient.user), doctor, at(TUE, "09:00"))  # original slot free again
    avail = api().get(f"/doctors/{doctor.pk}/availability", {"date": WED}).json()["slots"]
    assert "10:00" not in [s["start"][11:16] for s in avail]  # new slot is held


def test_reschedule_cancelled_appointment_is_409(api, patient, doctor):
    c = api(patient.user)
    appt_id = make(c, doctor, at(TUE, "09:00"))
    cancel(c, appt_id)
    resp = resched(c, appt_id, at(TUE, "10:00"))
    assert resp.status_code == 409 and code(resp) == "appointment_cancelled"


def test_reschedule_into_taken_slot_is_409_and_original_untouched(
    api, patient, other_patient, doctor
):
    a = make(api(patient.user), doctor, at(TUE, "09:00"))
    make(api(other_patient.user), doctor, at(TUE, "10:00"))
    resp = resched(api(patient.user), a, at(TUE, "10:00"))
    assert resp.status_code == 409 and code(resp) == "slot_taken"
    assert Appointment.objects.get(pk=a).start_time == at(TUE, "09:00")


@pytest.mark.parametrize(
    "day,hhmm,expected",
    [
        (TUE, "12:30", "outside_working_hours"),
        (MON, "08:30", "slot_too_soon"),
        (MON, "07:00", "slot_in_past"),
        ("2027-06-01", "09:00", "slot_too_far_ahead"),
        (TUE, "09:00", "same_slot"),
    ],
)
def test_reschedule_validated_like_a_fresh_booking(api, patient, doctor, day, hhmm, expected):
    c = api(patient.user)
    appt_id = make(c, doctor, at(TUE, "09:00"))
    resp = resched(c, appt_id, at(day, hhmm))
    assert resp.status_code == 422 and code(resp) == expected


def test_reschedule_to_overlap_own_other_booking_blocked(api, patient, doctor, doctor2):
    c = api(patient.user)
    make(c, doctor2, at(TUE, "11:00"))
    a = make(c, doctor, at(TUE, "09:00"))
    resp = resched(c, a, at(TUE, "11:00"))
    assert resp.status_code == 409 and code(resp) == "patient_double_booked"


def test_cannot_reschedule_someone_elses_appointment(api, patient, other_patient, doctor):
    a = make(api(patient.user), doctor, at(TUE, "09:00"))
    assert resched(api(other_patient.user), a, at(TUE, "10:00")).status_code == 404


def test_audit_trail_has_ids_and_codes_but_never_free_text(api, patient, doctor):
    c = api(patient.user)
    a = make(c, doctor, at(TUE, "09:00"))
    resched(c, a, at(TUE, "10:00"))
    cancel(c, a, reason="chemotherapy clash SENSITIVE-TEXT", reason_code="schedule_clash")
    actions = list(AuditLog.objects.order_by("created_at").values_list("action", flat=True))
    assert actions == ["appointment.book", "appointment.reschedule", "appointment.cancel"]
    blob = str(list(AuditLog.objects.values("metadata")))
    assert "SENSITIVE-TEXT" not in blob and "Alice" not in blob
