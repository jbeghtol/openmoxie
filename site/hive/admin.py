from django.contrib import admin

from .models import SinglePromptChat,MoxieDevice,MoxieSchedule

admin.site.register(SinglePromptChat)
admin.site.register(MoxieDevice)
admin.site.register(MoxieSchedule)
