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

