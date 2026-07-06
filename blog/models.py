from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    institute_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user.username} ({self.user.first_name} - {self.institute_name})"

class Day(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=1)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

class LessonHour(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    start_time = models.TimeField()
    finish_time = models.TimeField()
    sequence = models.IntegerField(default=1)
    is_break = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    def __str__(self):
        result = f"{self.start_time} - {self.finish_time}"
        if self.is_break:
            result += " (Istirahat)"
        return result

class Class(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)
    sequence = models.IntegerField(default=1)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

class Classroom(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)
    class_capacity = models.IntegerField(default=0)
    is_same_time_shareable = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

class Educator(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

class Lesson(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)
    time_slot = models.IntegerField(default=1)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

class Schedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    name = models.CharField(max_length=255)
    status = models.CharField(choices=[
        ('draft', 'Draf'),
        ('done', 'Selesai'),
    ], default='draft')

    def __str__(self):
        return f"{self.name}"

class Data(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='+')
    entity = models.CharField(choices=[
        ('hari', 'Hari'),
        ('jam_pembelajaran', 'Jam Pembelajaran'),
        ('kelas', 'Kelas'),
        ('ruang_kelas', 'Ruang Kelas'),
        ('pengajar', 'Pengajar'),
        ('pelajaran', 'Pelajaran'),
    ])
    entity_id = models.IntegerField()

    def __str__(self):
        return f"{self.schedule.name} | {self.entity} (id: {self.entity_id})"

class Constraint(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='+')
    data1 = models.ForeignKey(Data, on_delete=models.CASCADE, related_name='+')
    data2 = models.ForeignKey(Data, on_delete=models.CASCADE, related_name='+')
    is_capable = models.BooleanField()

    def __str__(self):
        return f"{self.schedule.name} | {self.data1.entity} (id: {self.data1.entity_id}) & {self.data2.entity} (id: {self.data2.entity_id}) - " + ("Bersedia" if self.is_capable else "Tidak Bersedia")

class ScheduleData(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='+')
    class_id = models.ForeignKey(Class, on_delete=models.RESTRICT, related_name='+')
    day_id = models.ForeignKey(Day, on_delete=models.RESTRICT, related_name='+')
    lesson_hour_id = models.ForeignKey(LessonHour, on_delete=models.RESTRICT, related_name='+')
