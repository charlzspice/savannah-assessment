"""Pure slot arithmetic: which start times exist for a doctor on a day.

Slots are *derived* from WorkingSchedule rather than stored, so a schedule change takes effect
immediately and there is no slot table to keep in sync. Booked slots are simply Appointment rows.
Kenya (EAT, UTC+3) has no DST, but we still do wall-clock arithmetic in the clinic timezone.
"""

from datetime import date, datetime, timedelta

from django.conf import settings


def clinic_day_bounds_utc(day: date):
    start = datetime.combine(day, datetime.min.time(), tzinfo=settings.CLINIC_TZ)
    return start, start + timedelta(days=1)


def slot_starts_for_day(doctor, day: date) -> list[datetime]:
    """All slot start times (tz-aware, clinic tz) the doctor works on `day`, ascending."""
    tz = settings.CLINIC_TZ
    step = timedelta(minutes=doctor.slot_minutes)
    starts = []
    for block in doctor.schedules.filter(weekday=day.weekday()).order_by("start_time"):
        cursor = datetime.combine(day, block.start_time, tzinfo=tz)
        block_end = datetime.combine(day, block.end_time, tzinfo=tz)
        while cursor + step <= block_end:
            starts.append(cursor)
            cursor += step
    return starts


def working_hours_summary(doctor, day: date) -> str:
    blocks = doctor.schedules.filter(weekday=day.weekday()).order_by("start_time")
    if not blocks:
        return f"{doctor.full_name} does not work on {day:%A}s."
    spans = ", ".join(f"{b.start_time:%H:%M}-{b.end_time:%H:%M}" for b in blocks)
    return (
        f"{doctor.full_name} works {spans} on {day:%A}s "
        f"({doctor.slot_minutes}-minute slots, {settings.CLINIC_TIMEZONE_NAME} time)."
    )
