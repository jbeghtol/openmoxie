# init_data.py
import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from ...models import MoxieSchedule, SinglePromptChat
from ...mqtt.robot_data import RobotData
import os

class Command(BaseCommand):
    help = 'Import data to bootstrap database with initial data.'

    def handle(self, *args, **options):
        rdata = RobotData()
        print("Initializing core database records.")
        # Check that we have a default schedule
        def_sched, created = MoxieSchedule.objects.get_or_create(name='default', schedule=rdata.get_schedule(robot_id='noid'))
        if created:
            print("Creating default schedule from json source.")
        else:
            print("Default schedule already exists.")

        def_chat, created = SinglePromptChat.objects.get_or_create(module_id='OPENMOXIE_CHAT', content_id='default')
        if created:
            def_chat.prompt="You are a having a conversation with your friend. Make it interesting and keep the conversation moving forward. Your utterances are around 30-40 words long. Ask only one question per response and ask it at the end of your response."
            def_chat.opener="Hi there!  Welcome to Open Moxie chat!"
            def_chat.save()
            print("Creating default OPENMOXIE_CHAT")
        else:
            print("Default chat OPENMOXIE_CHAT already exists.")

        # if env is set, attempt to create SU
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if username and email and password:
            User = get_user_model()
            if not User.objects.filter(username=username).exists():
                print('Creating superuser...')
                User.objects.create_superuser(username, email, password)
            else:
                print('Superuser already exists.')
        else:
            print('Superuser credentials not provided.')