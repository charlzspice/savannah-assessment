from django.conf import settings
from django.urls import path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts import views as accounts
from apps.appointments import views as appts
from apps.core import views as core

UUID = r"[0-9a-fA-F-]{36}"

urlpatterns = [
    re_path(r"^health/?$", core.health, name="health"),
    # Auth
    re_path(r"^auth/register/?$", accounts.RegisterView.as_view(), name="register"),
    re_path(r"^auth/token/?$", accounts.LoginView.as_view(), name="token"),
    re_path(r"^auth/token/refresh/?$", TokenRefreshView.as_view(), name="token-refresh"),
    # Doctors
    re_path(r"^doctors/?$", appts.DoctorListView.as_view(), name="doctor-list"),
    re_path(
        r"^doctors/(?P<doctor_id>\d+)/availability/?$",
        appts.DoctorAvailabilityView.as_view(),
        name="doctor-availability",
    ),
    # Appointments
    re_path(r"^appointments/?$", appts.AppointmentCreateView.as_view(), name="appointment-create"),
    re_path(
        rf"^appointments/(?P<appointment_id>{UUID})/?$",
        appts.AppointmentDetailView.as_view(),
        name="appointment-detail",
    ),
    re_path(
        rf"^appointments/(?P<appointment_id>{UUID})/cancel/?$",
        appts.AppointmentCancelView.as_view(),
        name="appointment-cancel",
    ),
    re_path(
        rf"^appointments/(?P<appointment_id>{UUID})/reschedule/?$",
        appts.AppointmentRescheduleView.as_view(),
        name="appointment-reschedule",
    ),
    # Patients
    re_path(r"^patients/?$", accounts.PatientCreateView.as_view(), name="patient-create"),
    re_path(
        rf"^patients/(?P<patient_id>{UUID})/appointments/?$",
        appts.PatientAppointmentsView.as_view(),
        name="patient-appointments",
    ),
    re_path(
        rf"^patients/(?P<patient_id>{UUID})/export/?$",
        accounts.PatientExportView.as_view(),
        name="patient-export",
    ),
]

if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path(
            "schema/",
            SpectacularAPIView.as_view(permission_classes=[], authentication_classes=[]),
            name="schema",
        ),
        path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]

handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
