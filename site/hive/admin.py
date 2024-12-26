from django.contrib import admin

from .models import SinglePromptChat,MoxieDevice,MoxieSchedule,HiveConfiguration,MentorBehavior

admin.site.register(SinglePromptChat)
admin.site.register(MoxieDevice)
admin.site.register(MoxieSchedule)
admin.site.register(HiveConfiguration)
admin.site.register(MentorBehavior)