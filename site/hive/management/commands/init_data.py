# init_data.py
import json
from django.core.management.base import BaseCommand
from ...models import MoxieSchedule
from ...mqtt.robot_data import RobotData

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
