'''
ROBOT DATA - Manages data interfaces for Robots

The general design is to store 'active' robots data in memory.  We load
pertinent data from the database when robots connect, and unload them when
they disconnect, and provide various APIs to access data like schedule, config,
and state.
'''
import json
import logging
import deepmerge
from django.db import connections
from django.db import transaction
from ..models import HiveConfiguration, MoxieDevice, MoxieSchedule, MentorBehavior, PersistentData
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils import timezone
from .scheduler import expand_schedule
from .util import run_db_atomic, now_ms

logger = logging.getLogger(__name__)

# System default robot settings, which may be overridden by the database values
# Notes:
# - default_loglevel in {info, warning, error, fatal} - logging at warning reduces load and increase frame rate
DEFAULT_ROBOT_SETTINGS = {
    "props": {
      "touch_wake": "1",
      "wake_alarms": "1",
      "wake_button": "1",
      "doa_range": "80",
      "target_all": "1",
      "gcp_upload_disable": "1",
      "local_stt": "on",
      "max_enroll": "2",
      "audio_wake": "1",
      "cloud_schedule_reset_threshold": "5",
      "debug_whiteboard": "0",
      "brain_entrances_available": "1",
      "mqtt_files": "0",
      "file_sync_wait": "0",
      "default_loglevel": "warning"
    }
}

# System default robot configuration, which may be overridden by the database values
DEFAULT_ROBOT_CONFIG = { 
  "pairing_status": "paired",
  "audio_volume": "0.6",
  "screen_brightness": "1.0",
  "audio_wake_set": "off",
  "timezone_id": "America/Los_Angeles",
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
        global DEFAULT_SCHEDULE
        self._robot_map = {}
        db_default = MoxieSchedule.objects.filter(name="default").first()
        if db_default:
            logger.info("Using 'default' schedule from database as schedule fallback")
            DEFAULT_SCHEDULE = db_default.schedule
        else:
            logger.error("Missing 'default' schedule from database.")

    # Called when Robot connects to the MQTT network from a worker thread
    def db_connect(self, robot_id):
        if robot_id in self._robot_map:
            # Known only when cache record isnt empty
            if self._robot_map[robot_id]:
                logger.info(f'Device {robot_id} already known.')
                return
        logger.info(f'Device {robot_id} is LOADING.')
        run_db_atomic(self.init_from_db, robot_id)

    # Called when a Robot disconnects from the MQTT network from a worker thread
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
    
    # Check if a device is online
    def device_online(self, robot_id):
        return robot_id in self._robot_map
    
    # Get a list of online robots
    def connected_list(self):
        return list(self._robot_map.keys())
    
    # Build a configuration record for a robot
    def build_config(self, device, hive_cfg):
        # Robot config is base config and settings merged with robot config and settings
        # NOTE: Uses copies of everything, to avoid altering db records when merging in settings
        base_cfg = (hive_cfg.common_config if hive_cfg and hive_cfg.common_config else DEFAULT_ROBOT_CONFIG).copy()
        base_cfg["settings"] = hive_cfg.common_settings if hive_cfg and hive_cfg.common_settings else DEFAULT_ROBOT_SETTINGS
        robot_cfg = device.robot_config.copy() if device.robot_config else {}
        robot_cfg["settings"] = device.robot_settings if device.robot_settings else {}
        return deepmerge.always_merger.merge(base_cfg, robot_cfg)

    # Load/create records for a Robot
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
        # load our robot's persistent data
        persistent_data, persistent_data_created = PersistentData.objects.get_or_create(device=device, defaults={'data': {}})
        self._robot_map[robot_id]["persistent_data"] = persistent_data
        device.save()

    # Finalize device record on disconnect
    def release_to_db(self, robot_id):
        device = MoxieDevice.objects.get(device_id=robot_id)
        if device:
            device.last_disconnect = timezone.now()
            device.save()
        # save persistent data for the robot
        pdata = self._robot_map.get(robot_id, {}).get("persistent_data")
        if pdata:
            pdata.save()

    # Get the active configuration for a device from the database objects
    def get_config_for_device(self, device):
        curr_cfg = HiveConfiguration.objects.filter(name='default').first()
        return self.build_config(device, curr_cfg)
    
    # Update an active device config, and return if the device is connected and needs the config provided
    def config_update_live(self, device):
        if self.device_online(device.device_id):
            self._robot_map[device.device_id]["config"] = self.get_config_for_device(device)
            return True
        return False
    
    # Get the cached config record for a robot
    def get_config(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        cfg = robot_rec.get("config", DEFAULT_COMBINED_CONFIG)
        logger.debug(f'Providing config {cfg} to {robot_id}')
        return cfg

    # Create a data record to connect to a volley for processing
    def get_volley_data(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        data = { "config": robot_rec.get("config", DEFAULT_COMBINED_CONFIG),
                 "state": robot_rec.get("state", {})
                }
        # persist is linked to the data record of our model object
        prec = robot_rec.get("persistent_data")
        data["persist"] = prec.data if prec else {}
        return data

    # Save robot state data
    def put_state(self, robot_id, state):
        run_db_atomic(self.update_state_atomic, robot_id, state)
        rec = self._robot_map.get(robot_id)
        if rec:
            # only add to a non-empty (initialized) record
            rec["state"] = state

    def put_puppet_state(self, robot_id, state):
        rec = self._robot_map.get(robot_id)
        if rec:
            # only add to a live record
            rec["puppet_state"] = state

    def get_puppet_state(self, robot_id):
        rec = self._robot_map.get(robot_id)
        return rec.get("puppet_state") if rec else None
    
    # Update the device record with the state data
    def update_state_atomic(self, robot_id, state):
        device = MoxieDevice.objects.get(device_id=robot_id)
        if "battery_level" not in state and "battery_level" in device.state:
            # sometimes state is missing the battery key, use the previous one if it isnt included
            state["battery_level"] = device.state["battery_level"]
        device.state = state
        device.state_updated = timezone.now()
        device.save()

    # Get all the mentor behaviors for a specific robot, in most recent first order
    def extract_mbh_atomic(self, robot_id):
        device = MoxieDevice.objects.get(device_id=robot_id)
        mbh_list = []
        for mbh in MentorBehavior.objects.filter(device=device).order_by('-timestamp'):
            mbh_list.append(model_to_dict(mbh, exclude=['device', 'id']))
        return mbh_list

    # Add a new mentor behavior for a robot, called inside a lock
    def insert_mbh_atomic(self, robot_id, mbh):
        device = MoxieDevice.objects.get(device_id=robot_id)
        rec = MentorBehavior(device=device)
        rec.__dict__.update(mbh)
        rec.save()

    # Add a new mentor behavior
    def add_mbh(self, robot_id, mbh):
        run_db_atomic(self.insert_mbh_atomic, robot_id, mbh)

    # Add a set of completions for content IDs in a module
    def add_mbh_completion_bulk(self, robot_id, module_id, content_id_list):
        device = MoxieDevice.objects.get(device_id=robot_id)
        last_mbh = MentorBehavior.objects.filter(device=device).order_by('-timestamp').first()
        inst_id = last_mbh.instance_id if last_mbh else 1
        # Make sorting easy by giving them all unique timestamps, it seems weird to use future times
        # so go back 1s to start and add 1 each time
        rec_ts = now_ms() - 1000
        recs = []
        for cid in content_id_list:
            recs.append(MentorBehavior(device=device,
                                 instance_id=inst_id,
                                 action="COMPLETED",
                                 module_id=module_id,
                                 content_id=cid,
                                 content_day=last_mbh.content_day if last_mbh else "1",
                                 timestamp=rec_ts
                    ))
            inst_id += 1
            rec_ts += 1
        MentorBehavior.objects.bulk_create(recs)

    # Get mentor behaviors
    def get_mbh(self, robot_id):
        return run_db_atomic(self.extract_mbh_atomic, robot_id)

    # Get the current schedule for the robot, typically expanded when including a generate block
    def get_schedule(self, robot_id, expand=True):
        robot_rec = self._robot_map.get(robot_id, {})
        s = robot_rec.get("schedule", DEFAULT_SCHEDULE)
        if expand:
            # do any custom schedule automatic generation
            s = expand_schedule(s, robot_id)
        logger.debug(f'Providing schedule {s} to {robot_id}')
        return s


if __name__ == "__main__":
    data = RobotData()
    print(f"Default rb config: {data.get_config('fakedevice')}")
    print(f"Default schedule  {data.get_schedule('fakedevice')}")
