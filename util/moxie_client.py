import paho.mqtt.client as mqtt
import json
import base64
import os
import time
from datetime import datetime, timedelta, timezone
from robot_credentials import RobotCredentials
from moxie_messages import CANNED_QUERY_REMOTE_CHAT_CONTEXTS, CANNED_QUERY_CONTEXT_INDEX

_IOT_CLIENT_ID_FORMAT = 'projects/{0}/locations/us-central1/registries/devices/devices/{1}'
_BASIC_FORMAT = '{1}'
_google_mqtt_endpoint = 'mqtt.googleapis.com'

class Endpoint:
    def __init__(self, project_id, mqtt_host=_google_mqtt_endpoint, port=443):
        self.project_id = project_id
        self.mqtt_host = mqtt_host
        self.mqtt_port = port

# Named IOT endpoints
IOT_ENDPOINTS = { 
    'staging': Endpoint('device-registry-staging-245022'),
    'production': Endpoint('device-registry-production-495'),
    'dev': Endpoint('device-registry-develop-454763'),
    'staging2': Endpoint('staging', 'mqtt-staging.embodied.com'),
    'production2': Endpoint('production', 'mqtt.embodied.com'),
    'dev2': Endpoint('develop', 'mqtt-develop.embodied.com'),
    'hk': Endpoint('hk', 'mqtt-hk.embodied.com'),
    'openmoxie': Endpoint('openmoxie', 'duranaki.com', 8883)
}

class MoxieClient:

    _robot : any
    _client : any
    _mqtt_client_id: str
    _mqtt_project_id: str
    _topic_handlers: dict
    def __init__(self, robot, endpoint="openmoxie"):
        self._robot = robot
        self._mqtt_project_id = IOT_ENDPOINTS.get(endpoint).project_id
        self._mqtt_endpoint = IOT_ENDPOINTS.get(endpoint).mqtt_host
        self._port = IOT_ENDPOINTS.get(endpoint).mqtt_port
        #self._mqtt_client_id = _IOT_CLIENT_ID_FORMAT.format(self._mqtt_project_id, self._robot.device_id)
        self._mqtt_client_id = _BASIC_FORMAT.format(self._mqtt_project_id, self._robot.device_id)
        print("creating client with id: ", self._mqtt_client_id)
        self._client = mqtt.Client(client_id=self._mqtt_client_id, transport="tcp")
        self._client.tls_set()
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        self._topic_handlers = None
        self._connect_handlers = []

    def connect(self, start = False):
        jwt_token = self._robot.create_jwt(self._mqtt_project_id)
        self._client.username_pw_set(username='unknown', password=jwt_token)
        print("connecting to: ", self._mqtt_endpoint)
        self._client.connect(self._mqtt_endpoint, self._port, 60)
        if start:
            self.start()

    def add_connect_handler(self, callback):
        self._connect_handlers.append(callback)

    def add_config_handler(self, callback):
        self.add_command_handler("config", callback)

    def add_command_handler(self, topic, callback):
        if not self._topic_handlers:
            self._topic_handlers = dict()
            self._topic_handlers[topic] = [ callback ]
        elif topic in self._topic_handlers:
            self._topic_handlers[topic].append(callback)
        else:
            self._topic_handlers[topic] = [ callback ]

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # The only two supported in IOT - commands for a wildcard of commands, config for our robot configuration
        client.subscribe('/devices/' + self._robot.device_id + '/commands/#')
        client.subscribe('/devices/' + self._robot.device_id + '/config')
        for ch in self._connect_handlers:
            ch(self, rc) 
        self.publish_state({})

    def on_message(self, client, userdata, msg):
        handled = False
        if "config" in msg.topic:
            if "config" in self._topic_handlers:
                if msg.payload:
                    for handler in self._topic_handlers["config"]:
                        handler("config", json.loads(msg.payload))
                handled = True
            if not handled:
                print("No handler for topic: " + msg.topic)
        else: # commands
            try:
                payload = json.loads(msg.payload)
                if "command" in payload:
                    command = payload["command"]
                    if command and command in self._topic_handlers:
                        for handler in self._topic_handlers[command]:
                            handler(command, payload)
                        handled = True
                    if command and "*" in self._topic_handlers:
                        for handler in self._topic_handlers["*"]:
                            handler(command, payload)
                        handled = True
                    if not handled:
                        print("No handler for command: " + command)
                else:
                    print(f"Payload without command? {payload}")
            except:
                #print("Skipping binary payload from: " + msg.topic)
                pass


    def long_topic(self, topic_name):
        return "/devices/" + self._robot.device_id + "/events/" + topic_name

    def state_topic(self):
        return "/devices/" + self._robot.device_id + "/state"

    def publish_state(self, payload: dict):
        self._client.publish(self.state_topic(), payload=json.dumps(payload))

    def publish_as_json(self, topic, payload: dict):
        self._client.publish(self.long_topic(topic), payload=json.dumps(payload))

    def publish_subtopic_as_json(self, payload: dict):
        dict["topic"] = "client-service-activity-log"
        self._client.publish(self.long_topic(topic), payload=json.dumps(payload))

    def publish_canned(self, canned_data):
        if "topic" in canned_data:
            self.publish_as_json(canned_data["topic"], payload=canned_data["payload"])
        elif "subtopic" in canned_data["payload"]:
            self.publish_as_json("client-service-activity-log", payload=canned_data["payload"])
        else:
            print(f"Warning! Invalid canned message: {canned_data}")

    def start(self):
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()

