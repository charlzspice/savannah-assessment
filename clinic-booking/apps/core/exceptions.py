"""Domain errors and the uniform error envelope.

Every non-2xx response has the shape:
    {"error": {"code": "<machine_code>", "message": "<human text>", "details": {...}}}

Status code policy:
    400  malformed input (missing fields, bad types/format)
    401/403  authentication / authorisation
    404  resource does not exist (or is not visible to the caller)
    409  request is well-formed but conflicts with current state (slot taken, already cancelled)
    422  well-formed but violates a business rule (outside hours, in the past, too soon)
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class DomainError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "domain_error"

    def __init__(self, message=None, *, extra=None):
        super().__init__(detail=message, code=self.default_code)
        self.extra = extra or {}


class DoctorNotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "doctor_not_found"
    default_detail = "Doctor not found."


class PatientNotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "patient_not_found"
    default_detail = "Patient not found."


class OutsideWorkingHours(DomainError):
    default_code = "outside_working_hours"
    default_detail = "The requested time is outside the doctor's working hours."


class SlotInPast(DomainError):
    default_code = "slot_in_past"
    default_detail = "Appointments cannot be booked in the past."


class SlotTooSoon(DomainError):
    default_code = "slot_too_soon"
    default_detail = "Appointments must be booked at least the minimum lead time in advance."


class SlotTooFarAhead(DomainError):
    default_code = "slot_too_far_ahead"
    default_detail = "The requested time is too far in the future to book."


class DateInPast(DomainError):
    default_code = "date_in_past"
    default_detail = "The requested date is in the past."


class SlotTaken(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "slot_taken"
    default_detail = "That slot is no longer available."


class PatientDoubleBooked(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "patient_double_booked"
    default_detail = "The patient already has an appointment at that time."


class AlreadyCancelled(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "already_cancelled"
    default_detail = "This appointment has already been cancelled."


class AppointmentCancelled(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "appointment_cancelled"
    default_detail = "A cancelled appointment cannot be rescheduled. Please book a new one."


class AppointmentInPast(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "appointment_in_past"
    default_detail = "This appointment has already started or passed and can no longer be changed."


class SameSlot(DomainError):
    default_code = "same_slot"
    default_detail = "The new time is the same as the current appointment time."


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None  # unhandled -> Django's 500 handler (JSON, no internals leaked)

    if isinstance(exc, DomainError):
        body = {"code": exc.default_code, "message": str(exc.detail), "details": exc.extra}
    elif response.status_code == 400:
        body = {
            "code": "validation_error",
            "message": "The request was invalid. See 'details' for the fields to fix.",
            "details": response.data,
        }
    else:
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        body = {
            "code": getattr(exc, "default_code", "error"),
            "message": str(detail or exc),
            "details": {},
        }
    response.data = {"error": body}
    return response
