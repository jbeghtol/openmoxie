from enum import Enum
from django.db import models

class SinglePromptChat(models.Model):
    name = models.CharField(max_length=200)
    module_id = models.CharField(max_length=200)
    content_id = models.CharField(max_length=200)
    max_history = models.IntegerField(default=20)
    max_volleys = models.IntegerField(default=9999)
    opener = models.TextField()
    prompt = models.TextField()

    def __str__(self):
        return self.name
    
class MoxieSchedule(models.Model):
    name = models.CharField(max_length=200)
    schedule = models.JSONField()

    def __str__(self):
        return self.name

class DevicePermit(Enum):
    UNKNOWN = 1
    PENDING = 2
    ALLOWED = 3

class MoxieDevice(models.Model):
    device_id = models.CharField(max_length=200)
    email = models.EmailField(null=True)
    permit = models.IntegerField(choices=[(tag.value, tag.name) for tag in DevicePermit])
    schedule = models.ForeignKey(MoxieSchedule, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.device_id

class MoxieLogs(models.Model):
    device = models.ForeignKey(MoxieSchedule, on_delete=models.CASCADE)
    timestamp = models.TimeField()
    uid = models.IntegerField()
    tag = models.CharField(max_length=80)
    message = models.TextField()
