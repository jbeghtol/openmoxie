from enum import Enum
from django.db import models
from django.core.validators import validate_comma_separated_integer_list

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
    source_version = models.IntegerField(default=1)
    
    def __str__(self):
        return self.name
    
class MoxieSchedule(models.Model):
    name = models.CharField(max_length=200)
    schedule = models.JSONField()
    source_version = models.IntegerField(default=1)
    
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
    last_connect = models.DateTimeField(null=True, blank=True)
    last_disconnect = models.DateTimeField(null=True, blank=True)
    state = models.JSONField(null=True, blank=True)
    state_updated = models.DateTimeField(null=True, blank=True)
    robot_config = models.JSONField(null=True, blank=True)
    robot_settings = models.JSONField(null=True, blank=True)

    def is_paired(self):
        if self.robot_config:
            return not (self.robot_config.get('pairing_status') == 'unpairing')
        return True

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
    google_api_key = models.TextField(null=True, blank=True, default='')
    common_config = models.JSONField(null=True, blank=True)
    common_settings = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name

class MentorBehavior(models.Model):
    device = models.ForeignKey(MoxieDevice, on_delete=models.CASCADE)
    # Fields for MBH
    module_id = models.CharField(max_length=80, null=True, blank=True)
    content_id = models.CharField(max_length=80, null=True, blank=True)
    content_day = models.CharField(max_length=80, null=True, blank=True)
    timestamp = models.BigIntegerField()
    action = models.CharField(max_length=80, null=True, blank=True)
    instance_id = models.BigIntegerField()
    ended_reason = models.CharField(max_length=80, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['device', 'timestamp'], name='device_timestamp_idx'),
        ]

    def __str__(self):
        return f'{self.timestamp}-{self.device}-{self.module_id}/{self.content_id}-{self.action}'


class GlobalAction(Enum):
    RESPONSE = 1
    LAUNCH = 2
    CONFIRM_LAUNCH = 3
    METHOD = 4

class GlobalResponse(models.Model):
    name = models.TextField()      # common name
    pattern = models.TextField()   # regex pattern to match speech
    entity_groups = models.CharField(max_length=255, validators=[validate_comma_separated_integer_list], null=True, blank=True)
    action = models.IntegerField(choices=[(tag.value, tag.name) for tag in GlobalAction],default=GlobalAction.RESPONSE.value)
    response_text = models.TextField(null=True, blank=True)  # plaintext response
    response_markup = models.TextField(null=True, blank=True)  # markup override response
    module_id = models.CharField(max_length=80, null=True, blank=True)  # for launches, module ID to target
    content_id = models.CharField(max_length=80, null=True, blank=True) # for launches, content ID to target
    code = models.TextField(null=True, blank=True) # Python code for METHOD, w/ def get_response(request, response, entities):
    sort_key = models.IntegerField(default=1) # in case ordering matters, they order desc so high goes first

    def __str__(self):
        return self.name