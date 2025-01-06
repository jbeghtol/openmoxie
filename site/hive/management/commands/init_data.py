# init_data.py
import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from ...models import MoxieSchedule, SinglePromptChat

class Command(BaseCommand):
    help = 'Import data to bootstrap database with initial data.'

    def handle(self, *args, **options):

        with open(settings.BASE_DIR / 'data/default_schedules.json') as f:
            def_schedules = json.load(f)
        s_updated = 0
        for rec in def_schedules:
            try:
                def_sched = MoxieSchedule.objects.get(name=rec["name"])
                if def_sched.source_version < rec["source_version"]:
                    print(f'Updated schedule {def_sched.name} as source version has changed.')
                    def_sched.source_version = rec["source_version"]
                    def_sched.schedule = rec["schedule"]
                    def_sched.save()
                    s_updated += 1
            except MoxieSchedule.DoesNotExist:
                print(f'Creating missing schedule {rec["name"]} with version {rec["source_version"]}')
                MoxieSchedule.objects.create(name=rec["name"], schedule=rec["schedule"], source_version=rec["source_version"])
                s_updated += 1
        print(f'Default schedules checked.  Updated {s_updated} of {len(def_schedules)} factory schedules.')

        # Default free form chat, with no volley limit - talk forever
        def_chat, created = SinglePromptChat.objects.get_or_create(module_id='OPENMOXIE_CHAT', content_id='default')
        if created:
            def_chat.prompt="You are a robot named Moxie who comes from the Global Robotics Laboratory. You are having a conversation with a person who is your friend. Chat about a topic that the person finds interesting and fun. Share short facts and opinions about the topic, one fact or opinion at a time. You are curious and love learning what the person thinks."
            def_chat.opener="I love to chat.  What's on your mind?|Let's talk! What's a good topic?"
            def_chat.save()
            print("Creating default OPENMOXIE_CHAT")
        else:
            print("Default chat OPENMOXIE_CHAT already exists.")

        # Short free form chat, 20 max volleys - have a short chat and move on
        def_chat, created = SinglePromptChat.objects.get_or_create(module_id='OPENMOXIE_CHAT', content_id='short')
        if created:
            def_chat.prompt="You are a robot named Moxie who comes from the Global Robotics Laboratory. You are having a conversation with a person who is your friend. Chat about a topic that the person finds interesting and fun. Share short facts and opinions about the topic, one fact or opinion at a time. You are curious and love learning what the person thinks."
            def_chat.opener="I love to chat.  What's on your mind?|Let's talk! What's a good topic?"
            def_chat.max_volleys=20
            def_chat.save()
            print("Creating short OPENMOXIE_CHAT")
        else:
            print("Short chat OPENMOXIE_CHAT already exists.")

