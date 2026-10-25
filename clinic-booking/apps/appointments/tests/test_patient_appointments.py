import pytest

from apps.appointments.models import Appointment

from .helpers import MON, TUE, WED, at, iso

pytestmark = pytest.mark.django_db


def make(client, doctor, start):
    r = client.post(
        "/appointments", {"doctor_id": doctor.pk, "start_time": iso(start)}, format="json"
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_upcoming_sorted_by_date_excluding_cancelled_and_past(api, patient, doctor, doctor2):
    c = api(patient.user)
    late = make(c, doctor, at(WED, "11:00"))
    early = make(c, doctor2, at(TUE, "09:00"))
    cancelled = make(c, doctor, at(TUE, "15:00"))
    c.patch(f"/appointments/{cancelled}/cancel", {"reason": "Not needed"}, format="json")
    Appointment.objects.create(  # already in the past relative to the pinned clock
        doctor=doctor, patient=patient, start_time=at(MON, "07:00"), end_time=at(MON, "07:30")
    )
    resp = c.get(f"/patients/{patient.pk}/appointments")
    assert resp.status_code == 200
    assert [a["id"] for a in resp.json()] == [early, late]


def test_other_patient_gets_404_staff_gets_200(api, patient, other_patient, staff, doctor):
    make(api(patient.user), doctor, at(TUE, "09:00"))
    url = f"/patients/{patient.pk}/appointments"
    assert api(other_patient.user).get(url).status_code == 404
    assert api(staff).get(url).status_code == 200
    assert api().get(url).status_code == 401


def test_empty_list(api, patient):
    assert api(patient.user).get(f"/patients/{patient.pk}/appointments").json() == []
