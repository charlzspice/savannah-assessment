import pytest

from .helpers import MON, SAT, TUE, WED, at, iso

pytestmark = pytest.mark.django_db


def avail(client, doctor_id, date):
    return client.get(f"/doctors/{doctor_id}/availability", {"date": date})


def starts(resp):
    return [s["start"][11:16] for s in resp.json()["slots"]]


def test_full_day_has_16_half_hour_slots_and_is_public(api, doctor):
    resp = avail(api(), doctor.pk, TUE)  # unauthenticated on purpose
    assert resp.status_code == 200
    s = starts(resp)
    assert (
        len(s) == 16
        and s[0] == "08:00"
        and "12:00" not in s
        and s[8] == "13:00"
        and s[-1] == "16:30"
    )
    assert resp.json()["timezone"] == "Africa/Nairobi"


def test_booked_slot_disappears_and_cancel_brings_it_back(api, patient, doctor):
    c = api(patient.user)
    appt = c.post(
        "/appointments",
        {"doctor_id": doctor.pk, "start_time": iso(at(TUE, "09:00"))},
        format="json",
    ).json()
    assert "09:00" not in starts(avail(api(), doctor.pk, TUE))
    c.patch(f"/appointments/{appt['id']}/cancel", {"reason": "Cannot attend"}, format="json")
    assert "09:00" in starts(avail(api(), doctor.pk, TUE))


def test_today_hides_past_and_within_lead_time(api, doctor):
    s = starts(avail(api(), doctor.pk, MON))  # now = 08:00, lead 60min -> first bookable 09:00
    assert s[0] == "09:00" and len(s) == 14


def test_non_working_day_is_empty_not_error(api, doctor):
    resp = avail(api(), doctor.pk, SAT)
    assert resp.status_code == 200 and resp.json()["slots"] == []


def test_availability_response_contains_no_patient_data(api, patient, doctor):
    api(patient.user).post(
        "/appointments",
        {"doctor_id": doctor.pk, "start_time": iso(at(WED, "09:00"))},
        format="json",
    )
    text = avail(api(), doctor.pk, WED).content.decode()
    assert str(patient.pk) not in text and "Alice" not in text


@pytest.mark.parametrize(
    "params,status,code",
    [
        ({}, 400, "validation_error"),
        ({"date": "02-11-2026"}, 400, "validation_error"),
        ({"date": "2026-10-01"}, 422, "date_in_past"),
        ({"date": "2027-12-01"}, 422, "slot_too_far_ahead"),
    ],
)
def test_bad_dates(api, doctor, params, status, code):
    resp = api().get(f"/doctors/{doctor.pk}/availability", params)
    assert resp.status_code == status and resp.json()["error"]["code"] == code


def test_unknown_doctor(api):
    assert avail(api(), 12345, TUE).status_code == 404


def test_trailing_slash_tolerated(api, doctor):
    assert api().get(f"/doctors/{doctor.pk}/availability/", {"date": TUE}).status_code == 200
