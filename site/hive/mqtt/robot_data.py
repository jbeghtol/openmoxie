import json
import logging
import deepmerge
from django.db import connections
from django.db import transaction
from ..models import HiveConfiguration, MoxieDevice, MoxieSchedule, MentorBehavior
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils import timezone
from .scheduler import expand_schedule
from .util import run_db_atomic

logger = logging.getLogger(__name__)


DEFAULT_ROBOT_SETTINGS = {
    "props": {
      "touch_wake": "1",
      "wake_alarms": "1",
      "doa_range": "80",
      "target_all": "1",
      "gcp_upload_disable": "1",
      "local_stt": "on",
      "max_enroll": "0",
      "audio_wake": "1",
      "audio_wake_set": "off",
      "cloud_schedule_reset_threshold": "5",
      "debug_whiteboard": "1",
      "brain_entrances_available": "1"
    }
}

DEFAULT_ROBOT_CONFIG = { 
  "pairing_status": "paired",
  "audio_volume": "0.6",
  "screen_brightness": "1.0",
  "audio_wake_set": "off",
  "child_pii": {
      "nickname": "Pat",
      "input_speed": 0.0
  }
}

# We always pass combined to robot as a default if none is loaded (it should be loaded)
DEFAULT_COMBINED_CONFIG = DEFAULT_ROBOT_CONFIG.copy()
DEFAULT_COMBINED_CONFIG["settings"] = DEFAULT_ROBOT_SETTINGS

DEFAULT_SCHEDULE = {}

class RobotData:
    def __init__(self):
        global DEFAULT_SCHEDULE, DEFAULT_ROBOT_CONFIG, DEFAULT_ROBOT_SETTINGS
        self._robot_map = {}
        with open(settings.BASE_DIR / 'data/default_data_schedule.json') as f:
            DEFAULT_SCHEDULE = json.load(f)
        DEFAULT_ROBOT_CONFIG['settings'] = DEFAULT_ROBOT_SETTINGS


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
    
    def build_config(self, device, hive_cfg):
        # Robot config is base config and settings merged with robot config and settings
        # NOTE: Uses copies of everything, to avoid altering db records when merging in settings
        base_cfg = (hive_cfg.common_config if hive_cfg and hive_cfg.common_config else DEFAULT_ROBOT_CONFIG).copy()
        base_cfg["settings"] = hive_cfg.common_settings if hive_cfg and hive_cfg.common_settings else DEFAULT_ROBOT_SETTINGS
        robot_cfg = device.robot_config.copy() if device.robot_config else {}
        robot_cfg["settings"] = device.robot_settings if device.robot_settings else {}
        return deepmerge.always_merger.merge(base_cfg, robot_cfg)

    def init_from_db(self, robot_id):
        device, created = MoxieDevice.objects.get_or_create(device_id=robot_id)
        curr_cfg = HiveConfiguration.objects.filter(name='default').first()
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
        # build our config
        self._robot_map[robot_id]["config"] = self.build_config(device, curr_cfg)
        device.save()

    def release_to_db(self, robot_id):
        device = MoxieDevice.objects.get(device_id=robot_id)
        if device:
            device.last_disconnect = timezone.now()
            device.save()

    def get_config_for_device(self, device):
        curr_cfg = HiveConfiguration.objects.filter(name='default').first()
        return self.build_config(device, curr_cfg)
    
    def get_config(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        cfg = robot_rec.get("config", DEFAULT_COMBINED_CONFIG)
        logger.info(f'Providing config {cfg} to {robot_id}')
        return cfg

    def put_state(self, robot_id, state):
        run_db_atomic(self.update_state_atomic, robot_id, state)
        rec = self._robot_map.get(robot_id)
        if rec:
            # only add to a non-empty (initialized) record
            rec["state"] = state

    def update_state_atomic(self, robot_id, state):
        device = MoxieDevice.objects.get(device_id=robot_id)
        device.state = state
        device.state_updated = timezone.now()
        device.save()

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
        # do any custom schedule automatic generation
        s = expand_schedule(s, robot_id)
        logger.info(f'Providing schedule {s} to {robot_id}')
        return s


if __name__ == "__main__":
    data = RobotData()
    print(f"Default rb config: {data.get_config('fakedevice')}")
    print(f"Default schedule  {data.get_schedule('fakedevice')}")
