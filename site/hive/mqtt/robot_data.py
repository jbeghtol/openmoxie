import json
import logging
import time
from django.db import connections
from django.db import transaction
from ..models import MoxieDevice, MoxieSchedule, MentorBehavior
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils import timezone

root_path = settings.BASE_DIR

logger = logging.getLogger(__name__)

def run_db_atomic(functor, *args, **kwargs):
    with connections['default'].cursor() as cursor:
        with transaction.atomic():
            return functor(*args, **kwargs)

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
            # Known only when cache record isnt empty
            if self._robot_map[robot_id]:
                logger.info(f'Device {robot_id} already known.')
                return
        logger.info(f'Device {robot_id} is LOADING.')
        run_db_atomic(self.init_from_db, robot_id)

    def db_release(self, robot_id):
        if robot_id in self._robot_map:
            logger.info(f'Releasing device data for {robot_id}')
            run_db_atomic(self.release_to_db, robot_id)
            del self._robot_map[robot_id]

    # Check if init after connection for this bot is needed, and remember it so we only init once
    def connect_init_needed(self, robot_id):
        needed = robot_id not in self._robot_map
        if needed:
            # set an empty record, so we don't try again
            self._robot_map[robot_id] = {}
        return needed
    
    def device_online(self, robot_id):
        return robot_id in self._robot_map
    
    def connected_list(self):
        return list(self._robot_map.keys())
    
    def init_from_db(self, robot_id):
        device, created = MoxieDevice.objects.get_or_create(device_id=robot_id)
        device.last_connect = timezone.now()
        if created:
            logger.info(f'Created new model for this device {robot_id}')
            schedule = MoxieSchedule.objects.get(name='default')
            if schedule:
                logger.info(f'Setting schedule to {schedule}')
                device.schedule = schedule
                self._robot_map[robot_id] = { "schedule": schedule.schedule }
            else:
                logger.warning('Failed to locate default schedule.')
        else:
            logger.info(f'Existing model for this device {robot_id}')
            self._robot_map[robot_id] = { "schedule": device.schedule.schedule if device.schedule else DEFAULT_SCHEDULE }
        device.save()

    def release_to_db(self, robot_id):
        device = MoxieDevice.objects.get(device_id=robot_id)
        if device:
            device.last_disconnect = timezone.now()
            device.save()

    def get_config(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        cfg = robot_rec.get("config", DEFAULT_ROBOT_CONFIG)
        logger.info(f'Providing config {cfg} to {robot_id}')
        return cfg

    def extract_mbh_atomic(self, robot_id):
        device = MoxieDevice.objects.get(device_id=robot_id)
        mbh_list = []
        for mbh in MentorBehavior.objects.filter(device=device).order_by('timestamp'):
            mbh_list.append(model_to_dict(mbh, exclude=['device']))
        return mbh_list

    def insert_mbh_atomic(self, robot_id, mbh):
        device = MoxieDevice.objects.get(device_id=robot_id)
        rec = MentorBehavior(device=device)
        rec.__dict__.update(mbh)
        rec.save()

    def add_mbh(self, robot_id, mbh):
        run_db_atomic(self.insert_mbh_atomic, robot_id, mbh)

    def get_mbh(self, robot_id):
        return run_db_atomic(self.extract_mbh_atomic, robot_id)

    def get_schedule(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        s = robot_rec.get("schedule", DEFAULT_SCHEDULE)
        logger.info(f'Providing schedule {s} to {robot_id}')
        return s


if __name__ == "__main__":
    data = RobotData()
    print(f"Default rb config: {data.get_config('fakedevice')}")
    print(f"Default schedule  {data.get_schedule('fakedevice')}")
