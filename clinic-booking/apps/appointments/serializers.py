from rest_framework import serializers

from apps.core.fields import AwareDateTimeField, ClinicDateTimeField

from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    doctor_id = serializers.IntegerField(read_only=True)
    doctor_name = serializers.CharField(source="doctor.full_name", read_only=True)
    patient_id = serializers.UUIDField(read_only=True)
    start_time = ClinicDateTimeField(read_only=True)
    end_time = ClinicDateTimeField(read_only=True)
    cancelled_at = ClinicDateTimeField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "doctor_id",
            "doctor_name",
            "patient_id",
            "start_time",
            "end_time",
            "status",
            "cancel_reason_code",
            "cancel_note",
            "cancelled_at",
            "reschedule_count",
            "created_at",
        ]
        read_only_fields = fields


class BookAppointmentSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField(min_value=1)
    start_time = AwareDateTimeField()
    patient_id = serializers.UUIDField(
        required=False, help_text="Staff only. Patients always book for themselves."
    )


class CancelAppointmentSerializer(serializers.Serializer):
    reason = serializers.CharField(
        min_length=3,
        max_length=200,
        trim_whitespace=True,
        help_text="Why it is cancelled. Keep it short; do not include medical details.",
    )
    reason_code = serializers.ChoiceField(
        choices=Appointment.CancelReason.choices,
        default=Appointment.CancelReason.OTHER,
        required=False,
    )


class RescheduleAppointmentSerializer(serializers.Serializer):
    start_time = AwareDateTimeField()


class AvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField(input_formats=["%Y-%m-%d"])
