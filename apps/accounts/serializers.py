from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Patient, phone_validator

User = get_user_model()


class ConsentMixin(serializers.Serializer):
    consent = serializers.BooleanField(
        write_only=True,
        help_text="Must be true: the patient has been shown and accepts the privacy notice.",
    )

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Consent to the privacy notice is required to proceed."
            )
        return value


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "guardian_name",
            "guardian_phone",
            "consent_given_at",
            "consent_notice_version",
            "created_at",
        ]
        read_only_fields = fields


class PatientCreateSerializer(ConsentMixin):
    """Staff-created patient (e.g. walk-in registering a booking by phone)."""

    full_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=16, validators=[phone_validator])
    email = serializers.EmailField(required=False, allow_blank=True)
    guardian_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    guardian_phone = serializers.CharField(
        max_length=16, required=False, allow_blank=True, validators=[phone_validator]
    )

    def create(self, validated_data):
        validated_data.pop("consent")
        return Patient.objects.create(
            consent_given_at=timezone.now(),
            consent_notice_version=settings.PRIVACY_NOTICE_VERSION,
            **validated_data,
        )


class RegisterSerializer(PatientCreateSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from None
        return value

    def create(self, validated_data):
        email = validated_data["email"].lower()
        password = validated_data.pop("password")
        validated_data.pop("consent")
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=email, email=email, password=password)
                return Patient.objects.create(
                    user=user,
                    consent_given_at=timezone.now(),
                    consent_notice_version=settings.PRIVACY_NOTICE_VERSION,
                    **{**validated_data, "email": email},
                )
        except IntegrityError:
            # Deliberately vague: do not confirm whether an email is already registered.
            raise serializers.ValidationError(
                {"email": ["Registration could not be completed with these details."]}
            ) from None
