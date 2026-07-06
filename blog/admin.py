from django.contrib import admin
from . import models

# Register your models here.
admin.site.register([
    models.Profile,
    models.Day,
    models.LessonHour,
    models.Class,
    models.Classroom,
    models.Educator,
    models.Lesson,
    models.Schedule,
    models.Data,
    models.Constraint,
])
