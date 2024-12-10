import os
import pathlib
import json
import base64
import uuid
from datetime import datetime, timedelta, timezone

from jwt import (
    JWT,
    jwk_from_dict,
    jwk_from_pem,
)
from jwt.utils import get_int_from_datetime

STORE_PATH = os.path.join(pathlib.Path.home(), ".moxie_mqtt")
ID_FILE = os.path.join(STORE_PATH, "id.json")
ID_ENV_FILE = os.path.join(STORE_PATH, "id.env")
DEVICE_ID_FILE = os.path.join(STORE_PATH, "uuid.txt")
DEVICE_KEY_FILE = os.path.join(STORE_PATH, "RS256.key")
USER_ID_FILE = os.path.join(STORE_PATH, "user_uuid.txt")

class RobotCredentials:
    """
    Data class for managing Moxie credentials.  Stores local data to $HOME/.moxie_mqtt.  Will
    automatically attempt to create id/key files and pull them from Moxie over ADB if needed.
    After bootstrapping, will leave an id.env file with env vars to use these in another env.
    """
    device_uuid: str

    def __init__(self, fake_monitor=False):
        if fake_monitor:
            self._fake_monitor = True
            self.device_uuid = "supervisor"
            return
        else:
            self._fake_monitor = False
        if not os.path.isfile(DEVICE_ID_FILE) or not os.path.isfile(DEVICE_KEY_FILE):
            # No identity, try to extract one from an ID file or ENV var
            moxie_env_creds = os.getenv('MOXIE_CREDENTIALS')
            if not os.path.isfile(ID_FILE) and moxie_env_creds:
                print("Credentials file does not exist.  Attempting to bootstrap one from environment.")
                pathlib.Path(STORE_PATH).mkdir(parents=True, exist_ok=True)
                # creds are a big base64 string with JSON inside it
                with open(ID_FILE, "wb") as of:
                    of.write(base64.b64decode(moxie_env_creds))

            if not os.path.isfile(ID_FILE):
                print("Credentials file does not exist.  Attempting to bootstrap one from Moxie.")
                pathlib.Path(STORE_PATH).mkdir(parents=True, exist_ok=True)
                self.bootstrap_keys()
            else:
                print("Extracting from credentials ID file.")
                with open(ID_FILE) as f:
                    json_data = json.load(f)
                    with open(DEVICE_ID_FILE, "w") as df:
                        df.write(json_data["device_id"])
                    with open(DEVICE_KEY_FILE, "wb") as kf:
                        kf.write(base64.b64decode(json_data["private_key"]))
                print("Keys and device ID extracted from id.json")
        elif not os.path.isfile(ID_FILE):
            print("ID Credentials file does not exist.  Attempting to bootstrap one from keys.")
            self.bootstrap_keys(has_keys=True)

        if os.path.isfile(DEVICE_ID_FILE) and os.path.isfile(DEVICE_KEY_FILE):
            with open(DEVICE_ID_FILE) as df:
                self.device_uuid = df.read()
        else:
            raise Exception("Could not establish Moxie Credentials.  No files, id files, or id environment var.")

    @property
    def device_id(self) -> str:
        return "d_" + self.device_uuid

    @property
    def key_file(self) -> str:
        return DEVICE_KEY_FILE

    def create_jwt(self, project_id) -> str:
        if self._fake_monitor:
            return "supervisor"
        with open(self.key_file, 'rb') as fh:
            signing_key = jwk_from_pem(fh.read())
            message = {
                'aud': project_id,
                'iat': get_int_from_datetime(datetime.now(timezone.utc)),
                'exp': get_int_from_datetime(datetime.now(timezone.utc) + timedelta(hours=1)),
            }
            return JWT().encode(message, signing_key, alg='RS256')

    def bootstrap_keys(self, has_keys = False):
        if not has_keys:
            print("Bootstrapping keys from Moxie over ADB")
            os.system(f"adb pull /sdcard/EmbodiedStaticData/PERSISTENT_DATA/uuid.txt \"{STORE_PATH}\"")
            os.system(f"adb pull /sdcard/EmbodiedStaticData/PERSISTENT_DATA/rightpoint/RS256.key \"{STORE_PATH}\"")
        if os.path.isfile(DEVICE_ID_FILE) and os.path.isfile(DEVICE_KEY_FILE):
            with open(DEVICE_ID_FILE, 'r') as df:
                bs_device_id = df.read()
            with open(DEVICE_KEY_FILE, 'rb') as fh:
                pemdata = fh.read()
                pkey = base64.b64encode(pemdata).decode('utf-8')
                output = { "device_id": bs_device_id, "private_key": pkey }
                with open(ID_FILE, "w") as idout:
                    json.dump(output, idout)
                with open(ID_ENV_FILE, "w") as eo:
                    serial = base64.b64encode(json.dumps(output).encode()).decode('utf-8')
                    print(f"export MOXIE_CREDENTIALS={serial}", file=eo)

    def get_user_id(self):
        if os.path.isfile(USER_ID_FILE):
            with open(USER_ID_FILE, 'r') as df:
                user_id = df.read()
                if user_id:
                    return user_id
        # any missing or empty, remake
        new_user_id = str(uuid.uuid4())
        with open(USER_ID_FILE, "w") as uf:
            uf.write(new_user_id)
            return new_user_id

if __name__ == "__main__":
    creds = RobotCredentials()
    print(f"Current credentials for robot {creds.device_id}")
