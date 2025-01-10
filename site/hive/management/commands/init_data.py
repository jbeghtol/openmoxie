# init_data.py
import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from ...models import MoxieSchedule, SinglePromptChat

class Command(BaseCommand):
    help = 'Import data to bootstrap database with initial data.'

    def handle(self, *args, **options):

        # Update any needed factory default schedules
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

        # Update any needed factory default conversations
        with open(settings.BASE_DIR / 'data/default_conversations.json') as f:
            def_conversations = json.load(f)
        c_updated = 0
        for rec in def_conversations:
            try:
                def_chat = SinglePromptChat.objects.get(module_id=rec["module_id"], content_id=rec["content_id"])
                if def_chat.source_version < rec["source_version"]:
                    print(f'Updated conversation {def_chat.module_id}/{def_chat.content_id} as source version has changed.')
                    def_chat.__dict__.update(rec)
                    def_chat.save()
                    c_updated += 1
            except SinglePromptChat.DoesNotExist:
                print(f'Creating missing conversation {rec["module_id"]}/{rec["content_id"]} with version {rec["source_version"]}')
                def_chat = SinglePromptChat.objects.create(module_id=rec["module_id"], content_id=rec["content_id"])
                def_chat.__dict__.update(rec)
                def_chat.save()
                c_updated += 1
        print(f'Default conversations checked.  Updated {c_updated} of {len(def_conversations)} factory conversations.')
