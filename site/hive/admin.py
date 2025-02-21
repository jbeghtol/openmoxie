from django.contrib import admin

from .models import PersistentData, SinglePromptChat,MoxieDevice,MoxieSchedule,HiveConfiguration,MentorBehavior,GlobalResponse

admin.site.register(SinglePromptChat)
admin.site.register(MoxieDevice)
admin.site.register(MoxieSchedule)
admin.site.register(HiveConfiguration)
admin.site.register(MentorBehavior)
admin.site.register(GlobalResponse)
admin.site.register(PersistentData)