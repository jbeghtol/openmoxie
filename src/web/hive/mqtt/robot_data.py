import json
from django.db import connections
from django.db import transaction
from ..models import MoxieDevice, MoxieSchedule

def run_db_atomic(functor, *args, **kwargs):
    with connections['default'].cursor() as cursor:
        with transaction.atomic():
            print(f'DB TRANS {functor}')
            functor(*args, **kwargs)
            pass

DEFAULT_ROBOT_CONFIG = { 
  "paired_status": "paired",
  "audio_volume": "0.6",
  "screen_brightness": "1.0",
  "audio_wake_set": "off"
}
DEFAULT_MODULES = {}
DEFAULT_MBH = []
DEFAULT_SCHEDULE = {}

class RobotData:
    def __init__(self):
        global DEFAULT_MODULES
        global DEFAULT_SCHEDULE
        self._robot_map = {}
        with open('default_data_modules.json') as f:
            DEFAULT_MODULES = json.load(f)
        with open('default_data_schedule.json') as f:
            DEFAULT_SCHEDULE = json.load(f)
        with open('default_data_settings.json') as f:
            DEFAULT_ROBOT_CONFIG['settings'] = json.load(f)


    def db_connect(self, robot_id):
        if robot_id in self._robot_map:
            print(f'Device {robot_id} already known.')
        else:
            print(f'Device {robot_id} is NEW.')
            #self.init_from_db(robot_id)
            run_db_atomic(self.init_from_db, robot_id)

    def db_release(self, robot_id):
        if robot_id in self._robot_map:
            print(f'Releasing device data for {robot_id}')
            del self._robot_map[robot_id]

    def init_from_db(self, robot_id):
        print('Init from DB')
        device, created = MoxieDevice.objects.get_or_create(device_id=robot_id)
        print('Init from DB2')
        if created:
            print(f'Created new model for this device {robot_id}')
            schedule = MoxieSchedule.objects.get(name='default')
            if schedule:
                print(f'Setting schedule to {schedule}')
                device.schedule = schedule
                device.save()
                self._robot_map[robot_id] = { "schedule": schedule.schedule }
        else:
            print(f'Existing model for this device {robot_id}')
            self._robot_map[robot_id] = { "schedule": device.schedule.schedule }
        pass        

    def get_config(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        return robot_rec.get("config", DEFAULT_ROBOT_CONFIG)

    def get_modules(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        return robot_rec.get("modules", DEFAULT_MODULES)

    def get_mbh(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        return robot_rec.get("mentor_behaviors", DEFAULT_MBH)

    def get_schedule(self, robot_id):
        robot_rec = self._robot_map.get(robot_id, {})
        return robot_rec.get("schedule", DEFAULT_SCHEDULE)


if __name__ == "__main__":
    data = RobotData()
    print(f"Default rb config: {data.get_config('fakedevice')}")
    print(f"Default modules  {data.get_modules('fakedevice')}")
    print(f"Default schedule  {data.get_schedule('fakedevice')}")
