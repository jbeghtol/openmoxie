import json
import logging
from django.db import connections
from django.db import transaction
from ..models import MoxieDevice, MoxieSchedule
from django.conf import settings

root_path = settings.BASE_DIR

logger = logging.getLogger(__name__)

def run_db_atomic(functor, *args, **kwargs):
    with connections['default'].cursor() as cursor:
        with transaction.atomic():
            functor(*args, **kwargs)
            pass

DEFAULT_ROBOT_CONFIG = { 
  "paired_status": "paired",
  "audio_volume": "0.6",
  "screen_brightness": "1.0",
  "audio_wake_set": "off"
}

DEFAULT_MBH = []
DEFAULT_SCHEDULE = {}

class RobotData:
    def __init__(self):
        global DEFAULT_SCHEDULE
        self._robot_map = {}
        with open(settings.BASE_DIR / 'data/default_data_schedule.json') as f:
            DEFAULT_SCHEDULE = json.load(f)
        with open(settings.BASE_DIR / 'data/default_data_settings.json') as f:
            DEFAULT_ROBOT_CONFIG['settings'] = json.load(f)


    def db_connect(self, robot_id):
        if robot_id in self._robot_map:
            logger.info(f'Device {robot_id} already known.')
        else:
            logger.info(f'Device {robot_id} is NEW.')
            #self.init_from_db(robot_id)
            run_db_atomic(self.init_from_db, robot_id)

    def db_release(self, robot_id):
        if robot_id in self._robot_map:
            logger.info(f'Releasing device data for {robot_id}')
            del self._robot_map[robot_id]

    # Check if init after connection for this bot is needed, and remember it so we only init once
    def connect_init_needed(self, robot_id):
        needed = robot_id not in self._robot_map
        if needed:
            # set an empty record, so we don't try again
            self._robot_map[robot_id] = {}
        return needed
    
    def init_from_db(self, robot_id):
        device, created = MoxieDevice.objects.get_or_create(device_id=robot_id)
        if created:
            logger.info(f'Created new model for this device {robot_id}')
            schedule = MoxieSchedule.objects.get(name='default')
            if schedule:
                logger.info(f'Setting schedule to {schedule}')
                device.schedule = schedule
                device.save()
                self._robot_map[robot_id] = { "schedule": schedule.schedule }
            else:
                logger.warning('Failed to locate default schedule.')
        else:
            logger.info(f'Existing model for this device {robot_id}')
            self._robot_map[robot_id] = { "schedule": device.schedule.schedule if device.schedule else DEFAULT_SCHEDULE }
        pass        

    def get_config(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        cfg = robot_rec.get("config", DEFAULT_ROBOT_CONFIG)
        logger.info(f'Providing config {cfg} to {robot_id}')
        return cfg

    def get_mbh(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        return robot_rec.get("mentor_behaviors", DEFAULT_MBH)

    def get_schedule(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        s = robot_rec.get("schedule", DEFAULT_SCHEDULE)
        logger.info(f'Providing schedule {s} to {robot_id}')
        return s


if __name__ == "__main__":
    data = RobotData()
    print(f"Default rb config: {data.get_config('fakedevice')}")
    print(f"Default schedule  {data.get_schedule('fakedevice')}")
