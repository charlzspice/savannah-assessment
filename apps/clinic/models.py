from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Doctor(models.Model):
    """Public, non-sensitive professional profile (ids are safe to expose)."""

    full_name = models.CharField(max_length=120)
    specialty = models.CharField(max_length=80, blank=True)
    slot_minutes = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(5), MaxValueValidator(120)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.full_name


class WorkingSchedule(models.Model):
    """A block of working time on a weekday (clinic-local time). A doctor may have several
    blocks per day (e.g. a lunch break). Adding a Clinic FK later enables multi-site."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0
        TUESDAY = 1
        WEDNESDAY = 2
        THURSDAY = 3
        FRIDAY = 4
        SATURDAY = 5
        SUNDAY = 6

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["doctor_id", "weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")), name="schedule_start_before_end"
            ),
            models.UniqueConstraint(
                fields=["doctor", "weekday", "start_time"], name="uniq_schedule_block"
            ),
        ]

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("start_time must be before end_time.")
        overlaps = WorkingSchedule.objects.filter(
            doctor=self.doctor_id,
            weekday=self.weekday,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlaps.exists():
            raise ValidationError("This block overlaps an existing block for that weekday.")

    def __str__(self):
        span = f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        return f"{self.doctor} {self.get_weekday_display()} {span}"
