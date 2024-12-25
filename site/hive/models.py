from enum import Enum
from django.db import models

class AIVendor(Enum):
    OPEN_AI = 1

class SinglePromptChat(models.Model):
    name = models.CharField(max_length=200)
    module_id = models.CharField(max_length=200)
    content_id = models.CharField(max_length=200)
    max_history = models.IntegerField(default=20)
    max_volleys = models.IntegerField(default=9999)
    opener = models.TextField()
    prompt = models.TextField()
    vendor = models.IntegerField(choices=[(tag.value, tag.name) for tag in AIVendor],default=AIVendor.OPEN_AI.value)
    model = models.CharField(max_length=200, default="gpt-3.5-turbo")
    max_tokens = models.IntegerField(default=70)
    temperature = models.FloatField(default=0.5)
    
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
    email = models.EmailField(null=True, blank=True)
    permit = models.IntegerField(choices=[(tag.value, tag.name) for tag in DevicePermit],default=DevicePermit.UNKNOWN.value)
    schedule = models.ForeignKey(MoxieSchedule, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.name if self.name else self.device_id

class MoxieLogs(models.Model):
    device = models.ForeignKey(MoxieDevice, on_delete=models.CASCADE)
    timestamp = models.TimeField()
    uid = models.IntegerField()
    tag = models.CharField(max_length=80)
    message = models.TextField()


class HiveConfiguration(models.Model):
    name = models.CharField(max_length=200)
    openai_api_key = models.TextField(null=True, blank=True, default='')
    external_host = models.CharField(max_length=255, null=True, blank=True, default='')
    allow_unverified_bots = models.BooleanField(default=False)

    def __str__(self):
        return self.name
