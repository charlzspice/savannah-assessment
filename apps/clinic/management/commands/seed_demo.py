"""Idempotent demo data: 5 fictional doctors, schedules, and two demo logins.

SYNTHETIC DATA ONLY. Never load real patient data into the demo deployment.
Passwords come from DEMO_STAFF_PASSWORD / DEMO_PATIENT_PASSWORD; if unset a random one is
generated and printed once (so no credentials live in the repository).
"""

import os
import secrets
from datetime import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Patient
from apps.clinic.models import Doctor, WorkingSchedule

DOCTORS = [
    ("Dr. Amani Mwangi", "General Practice", [0, 1, 2, 3, 4], [(8, 12), (13, 17)]),
    ("Dr. Zawadi Otieno", "Paediatrics", [0, 1, 2, 3, 4], [(9, 13)]),
    ("Dr. Baraka Kiptoo", "Internal Medicine", [1, 2, 3, 4, 5], [(8, 12), (14, 17)]),
    ("Dr. Neema Wanjiru", "Gynaecology", [0, 2, 4], [(10, 16)]),
    ("Dr. Jelani Hassan", "Dermatology", [0, 1, 2, 3, 4], [(8, 11), (13, 16)]),
]


class Command(BaseCommand):
    help = "Create synthetic demo doctors, schedules and demo accounts (idempotent)."

    def handle(self, *args, **options):
        for name, specialty, days, blocks in DOCTORS:
            doctor, _ = Doctor.objects.get_or_create(
                full_name=name, defaults={"specialty": specialty, "slot_minutes": 30}
            )
            for weekday in days:
                for start_h, end_h in blocks:
                    WorkingSchedule.objects.get_or_create(
                        doctor=doctor,
                        weekday=weekday,
                        start_time=time(start_h),
                        defaults={"end_time": time(end_h)},
                    )

        User = get_user_model()
        self._account(User, "reception@demo.clinic.test", "DEMO_STAFF_PASSWORD", staff=True)
        user = self._account(User, "patient@demo.clinic.test", "DEMO_PATIENT_PASSWORD", staff=False)
        if user and not hasattr(user, "patient"):
            Patient.objects.create(
                user=user,
                full_name="Demo Patient",
                phone="+254700000000",
                email=user.email,
                consent_given_at=timezone.now(),
                consent_notice_version=settings.PRIVACY_NOTICE_VERSION,
            )
        self.stdout.write(self.style.SUCCESS("Demo data ready."))

    def _account(self, User, email, env_name, *, staff):
        user = User.objects.filter(username=email).first()
        if user:
            return user
        password = os.environ.get(env_name) or secrets.token_urlsafe(14)
        user = User.objects.create_user(
            username=email, email=email, password=password, is_staff=staff
        )
        if not os.environ.get(env_name):
            self.stdout.write(f"Generated password for {email}: {password}  (shown once)")
        return user
