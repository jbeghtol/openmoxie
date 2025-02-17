'''
MOXIE SERVER - Primary service handler for Moxie
'''
import concurrent
import paho.mqtt.client as mqtt
import json
import time
import re
import logging
import base64
import ssl
from .ai_factory import set_openai_key
from .robot_credentials import RobotCredentials
from .robot_data import RobotData
from .moxie_remote_chat import RemoteChat
from .protos.embodied.logging.Log_pb2 import ProtoSubscribe
from .protos.embodied.logging.Cloud2_pb2 import ServiceConfiguration2
from .protos.embodied.wifiapp.QRCommands_pb2 import StartPairingQR
from .zmq_stt_handler import STTHandler
from ..models import HiveConfiguration

_BASIC_FORMAT = '{1}'
_MOXIE_SERVICE_INSTANCE = None
_OPENAI_APIKEY=None

def now_ms():
    return time.time_ns() // 1_000_000

logger = logging.getLogger(__name__)

'''
MoxieServer provides cloud services to client Moxies.  Because this is MQTT, services are
provided using TOPICS.  With the exception of the ZMQ, all topics communicate using JSON
message paylods.  Moxie Server notably:
- Subscribes to the event, state, and log topics produced by ALL moxie devices
- Sends responses to device command topics to provide services and control Moxies
- Listens to system topics from mosquitto MQTT to detect devices connecting and disconnecting

As implemented there is a singleton MoxieService created using the instance creation method
near the end of this file.  It connects to the MQTT broker, which cooredinates all exchanges
of topics between Moxie's and MoxieServer.
'''
class MoxieServer:
    _robot : any
    _remote_chat : any
    _client : any
    _mqtt_client_id: str
    _mqtt_project_id: str
    _cert_required: bool
    _topic_handlers: dict
    _zmq_handlers: dict
    _client_metrics: dict
    _google_service_account: str
    _robot_data: RobotData
    _remote_chat: RemoteChat
    def __init__(self, robot, rbdata, project_id, mqtt_host, mqtt_port, cert_required=True):
        self._robot = robot
        self._robot_data = rbdata
        self._mqtt_project_id = project_id
        self._mqtt_endpoint = mqtt_host
        self._port = mqtt_port
        self._cert_required = cert_required
        self._mqtt_client_id = _BASIC_FORMAT.format(self._mqtt_project_id, self._robot.device_id)
        logger.info(f"Creating client with id: {self._mqtt_client_id}")
        self._client = mqtt.Client(client_id=self._mqtt_client_id, transport="tcp")
        if self._cert_required:
            self._client.tls_set()
        else:
            self._client.tls_set(cert_reqs=ssl.CERT_NONE)
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        self._topic_handlers = None
        self._connect_handlers = []
        self._remote_chat = RemoteChat(self)
        self._zmq_handlers = {}
        self._client_metrics = {}
        self._connect_pattern = r"connected from (.*) as (d_[a-f0-9-]+)"
        self._disconnect_pattern = r"Client (d_[a-f0-9-]+) (closed its connection|disconnected)"
        self._worker_queue = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.update_from_database()

    # Connect to the broker - the jwt stuff left in place, but isn't required
    def connect(self, start = False):
        jwt_token = self._robot.create_jwt(self._mqtt_project_id)
        self._client.username_pw_set(username='unknown', password=jwt_token)
        logger.info(f"connecting to: {self._mqtt_endpoint}")
        self._client.connect(self._mqtt_endpoint, self._port, 60)
        if start:
            self.start()

    # For any external monitoring of connections to the broker
    def add_connect_handler(self, callback):
        self._connect_handlers.append(callback)

    # Bind a listener to a specific proto on the ZMQ topic
    def add_zmq_handler(self, protoname, callback):
        self._zmq_handlers[protoname] = callback

    # This is left-over client code, supervisor doesn't get a config
    def add_config_handler(self, callback):
        self.add_command_handler("config", callback)

    # This is left-over client code, supervisor doesn't rx commands
    def add_command_handler(self, topic, callback):
        if not self._topic_handlers:
            self._topic_handlers = dict()
            self._topic_handlers[topic] = [ callback ]
        elif topic in self._topic_handlers:
            self._topic_handlers[topic].append(callback)
        else:
            self._topic_handlers[topic] = [ callback ]

    # Callback when we connect to the mqtt broker, subscribe to everything we care about
    def on_connect(self, client, userdata, flags, rc):
        logger.info(f"Connected with result code {rc}")
        # The only two supported in IOT - commands for a wildcard of commands, config for our robot configuration
        client.subscribe('/devices/+/events/#')
        client.subscribe('/devices/+/state')
        # Subscriptions to monitor clients and broker logs
        client.subscribe('$SYS/broker/clients/#')
        client.subscribe('$SYS/broker/log/#')
        for ch in self._connect_handlers:
            ch(self, rc) 

    # Entry point for ALL incoming messages, extract params about source and route
    def on_message(self, client, userdata, msg):
        try:
            dec = msg.topic.split('/')
            fromdevice = dec[2]
            basetype = dec[3]
            if basetype == "events":
                self.on_device_event(fromdevice, dec[4], msg)
            elif basetype == "state":
                self.on_device_state(fromdevice, msg)
            elif fromdevice == "clients":
                self.on_client_metrics(basetype, msg)
            elif fromdevice == "log":
                self.on_sys_log_message(basetype, msg)
            else:
                logger.debug(f"Rx UNK topic: {dec}")
        except Exception as e:
            logging.exception("Error handling mqtt messsage:")
    

    # Handle messages FROM mosquitto syslog topic, looking for connect/disconnects
    def on_sys_log_message(self, basetype, msg):
        if basetype == "N": # Notifications
            line = msg.payload.decode('utf-8')
            match = re.search(self._connect_pattern, line)
            match2 = None if match else re.search(self._disconnect_pattern, line)
            if match:
                if self._robot_data.connect_init_needed(match.group(2)):
                    self._worker_queue.submit(self.on_device_connect, match.group(2), True, match.group(1))
            elif match2:
                self._worker_queue.submit(self.on_device_connect, match2.group(1), False)

    # Handles metrics from mosquitto
    def on_client_metrics(self, basetype, msg):
        self._client_metrics[basetype] = int(msg.payload.decode('utf-8'))

    # ALL EVENTS FROM-DEVICE ARRIVE HERE
    def on_device_event(self, device_id, eventname, msg):
        # Check the connection in case we missed this device connecting
        self.check_device_connect(device_id, "Event")
        if eventname == "remote-chat" or eventname == "remote-chat-staging":
            rcr = json.loads(msg.payload)
            if rcr.get('backend') == "data" and rcr.get('query',{}).get('query') == "modules":
                # REMOTE MODULES REQUEST
                req_id = rcr.get('event_id')
                # Let the remote chat module provide the modules data
                rc_modules = self._remote_chat.get_modules_info()
                logger.debug(f"Tx modules to: remote_chat: {rc_modules}")
                self.send_command_to_bot_json(device_id, 'remote_chat', { 'command': 'remote_chat', 'result': 0, 'event_id': req_id, 'query_data': rc_modules} )
            elif rcr.get('backend') == "router":
                # REMOTE CHAT CONVERSATION ENDPOINT
                self._remote_chat.handle_request(device_id, rcr, self._robot_data.get_volley_data(device_id))
        elif eventname == "client-service-activity-log":
            # Topic originally for reporting activities, but extended with subtopics
            csa = json.loads(msg.payload)
            if csa.get("subtopic") == "query":
                if csa.get("query") == "schedule":
                    # SCHEDULE REQUEST - Robot asking what schedule to follow this session
                    logger.debug("Rx Schedule request.")
                    req_id = csa.get('request_id')
                    self._worker_queue.submit(self.provide_schedule, req_id, device_id)
                elif csa.get("query") == "mentor_behaviors":
                    # MENTOR BEHAVIOR REQUEST - Robot asking what user has done before
                    logger.debug("Rx MBH request.")
                    req_id = csa.get('request_id')
                    self._worker_queue.submit(self.provide_mentor_behaviors, req_id, device_id)
                elif csa.get("query") == "license":
                    # ROBOT IS ASKING FOR ANY LICENSES IT CAN USE (e.g. google speech)
                    req_id = csa.get('request_id')
                    if self._google_service_account:
                        logger.debug(f"Providing google speech credentials to {device_id}")
                        self.send_command_to_bot_json(device_id, 'query_result', 
                                                    { 'command': 'query_result', 'request_id': req_id, 'query': 'license',
                                                    'license_values': [ 
                                                        { 'id': 'google_speech', 'license': self._google_service_account}
                                                        ]
                                                        })
            elif 'mentor_behavior' in csa:
                # MENTOR BEHAVIOR REPORT - Robot informing what user has done
                self._worker_queue.submit(self.ingest_mentor_behavior, device_id, csa['mentor_behavior'])
            elif csa.get("subtopic") == "telehealth":
                # ROBOT TELEHEALTH INTERFACE
                logger.info(f'Rx TELEHEALTH: {csa.get("message")}')
                th_state = csa["message"].get("state")
                if th_state:
                    self._robot_data.put_puppet_state(device_id, th_state)

        elif eventname == "zmq":
            # ZMQ BRIDGE INCOMING
            colon_index = msg.payload.find(b':')
            protoname = msg.payload[:colon_index].decode('utf-8')
            protodata = msg.payload[colon_index + 1:]
            handler = self._zmq_handlers.get(protoname)
            if handler:
                handler.handle_zmq(device_id, protoname, protodata)
            # else:
            #     logger.debug(f'Unhandled RX ProtoBuf {protoname} over ZMQ Bridge')
        elif eventname == "device-logs":
            # These are per-client log messages
            logrec = json.loads(msg.payload)
            logger.debug(f'{device_id}[{logrec.get("tag")}] - {logrec.get("message")}')

    # NOTE: Called from worker thread pool
    def provide_schedule(self, req_id, device_id):
        schedule = self._robot_data.get_schedule(device_id)
        self.send_command_to_bot_json(device_id, 'query_result', { 'command': 'query_result', 'query': 'schedule', 'request_id': req_id, 'schedule': schedule} )

    # NOTE: Called from worker thread pool
    def ingest_mentor_behavior(self, device_id, mbh):
        self._robot_data.add_mbh(device_id, mbh)

    # NOTE: Called from worker thread pool
    def ingest_robot_state(self, device_id, statedata):
        self._robot_data.put_state(device_id, statedata)

    # NOTE: Called from worker thread pool
    def provide_mentor_behaviors(self, req_id, device_id):
        mbh = self._robot_data.get_mbh(device_id)
        logger.info(f'Providing {len(mbh)} MBH records to {device_id}')
        self.send_command_to_bot_json(device_id, 'query_result', { 'command': 'query_result', 'query': 'mentor_behaviors', 'request_id': req_id, 'mentor_behaviors': mbh} )

    # NOTE: Called from worker thread pool
    def on_device_connect(self, device_id, connected, ip_addr=None):
        if connected:
            logger.info(f'Moxie CONNECTED {device_id} from {ip_addr}')
            self._robot_data.db_connect(device_id)
            # Sleep to avoid sending sub/config before client is ready
            time.sleep(1.0)
            self.send_config_to_bot_json(device_id, self._robot_data.get_config(device_id))
            # subscripe to ZMQ STT
            sub = ProtoSubscribe()
            sub.protos.append('embodied.perception.audio.zmqSTTRequest')
            sub.timestamp = now_ms()
            logger.debug(f'Subscribed to ZMQ STT')
            self.send_zmq_to_bot(device_id, sub)
        else:
            self._robot_data.db_release(device_id)
            logger.info(f'Moxie DISCONNECTED {device_id}')

    # Fallback, we missed the connect message but robot is connected
    def check_device_connect(self, device_id, info="Missing"):
        if self._robot_data.connect_init_needed(device_id):
            logger.info(f"Unconnected robot {device_id} location {info}.  Connecting now.")
            self._worker_queue.submit(self.on_device_connect, device_id, True, info)

    # Moxie reporting its own state information
    def on_device_state(self, device_id, msg):
        logger.debug(f"Rx STATE topic for device {device_id}")
        self.check_device_connect(device_id, "State")
        self._worker_queue.submit(self.ingest_robot_state, device_id, json.loads(msg.payload))

    # Callback when a moxie config has changed and may need to be provided
    def handle_config_updated(self, device):
        # Update if connected
        if self._robot_data.config_update_live(device):
            logger.info(f'Moxie device {device.device_id} updated, sending updated config.')
            self.send_config_to_bot_json(device.device_id, self._robot_data.get_config(device.device_id))
        else:
            logger.info(f'Moxie device {device.device_id} updated, but device offline')

    # For Robots using wake_button_enabled, wake them from screen off
    def send_wakeup_to_bot(self, device_id):
        if self._robot_data.device_online(device_id):
            self.send_command_to_bot_json(device_id, 'wakeup', {'command': 'wakeup'})
            return True
        return False

    # Send Moxie its configuration data
    def send_config_to_bot_json(self, device_id, payload: dict):
        self._client.publish(f"/devices/{device_id}/config", payload=json.dumps(payload))

    # Send a Command (JSON) to Moxie
    def send_command_to_bot_json(self, device_id, command, payload: dict):
        self._client.publish(f"/devices/{device_id}/commands/{command}", payload=json.dumps(payload))

    # Send a binary ZMQ message to Moxie
    def send_zmq_to_bot(self, device_id, msgobject):
        payload = (msgobject.DESCRIPTOR.full_name + ":").encode('utf-8') + msgobject.SerializeToString()
        self._client.publish(f"/devices/{device_id}/commands/zmq", payload=payload)

    # Send Telehealth message to Moxie
    def send_telehealth(self, device_id, msg):
        self.send_command_to_bot_json(device_id, "telehealth", payload={ "command": "telehealth", "message": msg })

    # Send Telehealth - PLAY message to Moxie
    def send_telehealth_speech(self, device_id, speech:str, mood:str, intensity:float):
        markup = self._remote_chat.make_markup(speech, (mood, intensity))
        tmsg = { "action": "PLAY_OUTPUT", "output": { "text": speech, "markup": markup } }
        self.send_telehealth(device_id, tmsg)

    # Send Telehealth - INTERRUPT Moxie speaking
    def send_telehealth_interrupt(self, device_id):
        tmsg = { "action": "INTERRUPT" }
        self.send_telehealth(device_id, tmsg)

    def long_topic(self, topic_name):
        return "/devices/" + self._robot.device_id + "/events/" + topic_name

    def publish_as_json(self, topic, payload: dict):
        self._client.publish(self.long_topic(topic), payload=json.dumps(payload))

    def publish_canned(self, canned_data):
        if "topic" in canned_data:
            self.publish_as_json(canned_data["topic"], payload=canned_data["payload"])
        elif "subtopic" in canned_data["payload"]:
            self.publish_as_json("client-service-activity-log", payload=canned_data["payload"])
        else:
            logger.warning(f"Warning! Invalid canned message: {canned_data}")

    # Print out client metrics, called periodically in the background
    def print_metrics(self):
        logger.info(f"Client Metrics: {self._client_metrics}")

    # Start client connection loop
    def start(self):
        self._client.loop_start()

    # Stop client connection loop
    def stop(self):
        self._client.loop_stop()

    # Get's a chat session object for use in the web chat
    def get_web_session_for_module(self, device_id, module_id, content_id):
        sess = self._remote_chat.get_web_session_for_module(device_id, module_id, content_id)
        sess.set_auto_history(True)
        return sess
    
    # Check global commands for interactive web
    def get_web_session_global_response(self, speech):
        return self._remote_chat.get_web_session_global_response(speech)
    
    # Accessor to remote chat
    def remote_chat(self):
        return self._remote_chat

    # Accessor to robot data
    def robot_data(self):
        return self._robot_data

    # Reload records from the database
    def update_from_database(self):
        hive_config = HiveConfiguration.objects.filter(name="default").first()
        set_openai_key(hive_config.openai_api_key if hive_config else None)
        self._google_service_account = hive_config.google_api_key if hive_config else None
        self._remote_chat.update_from_database()

    # Get the endppint / moxie relocate QR code to move a Moxie to this service
    def get_endpoint_qr_data(self):
        hiveconfig = HiveConfiguration.objects.filter(name="default").first()
        scfg = ServiceConfiguration2()
        scfg.gcp_project = self._mqtt_project_id
        scfg.mqtt_host = hiveconfig.external_host if hiveconfig and hiveconfig.external_host else self._mqtt_endpoint
        scfg.override_port = self._port
        scfg.disable_verify = not self._cert_required
        # Serialize to bytes, then bytes to base64 string
        scfg_base64 = base64.b64encode(scfg.SerializeToString()).decode('utf-8')
        # Now make QR debug object, just in JSON
        qr = { "debug": { "command": "om", "param": scfg_base64}}
        return json.dumps(qr)

    # Get a QR code for wifi credentials to show to Moxie
    def get_wifi_qr_data(self, ssid, password, band_id, hidden):
        wificreds = StartPairingQR()
        wificreds.wifi_only = True
        wificreds.ssid = ssid
        wificreds.password = password
        wificreds.is_hidden = hidden
        wificreds.band_select = int(band_id)
        # Pairing codes have two char header PA followed by a base64 coded serialized pairing proto
        wifi_base64 = "PA" + base64.b64encode(wificreds.SerializeToString()).decode('utf-8')
        return wifi_base64

# Instance method, disconnect and destroy
def cleanup_instance():
    global _MOXIE_SERVICE_INSTANCE
    if _MOXIE_SERVICE_INSTANCE:
        _MOXIE_SERVICE_INSTANCE._client.disconnect()
        _MOXIE_SERVICE_INSTANCE = None

# Instance method, accessor
def get_instance():
    global _MOXIE_SERVICE_INSTANCE
    return _MOXIE_SERVICE_INSTANCE

# Instance method, create singleton service
def create_service_instance(project_id, host, port, cert_required=True):
    global _MOXIE_SERVICE_INSTANCE
    if not _MOXIE_SERVICE_INSTANCE:
        creds = RobotCredentials(True)
        rbdata = RobotData()
        _MOXIE_SERVICE_INSTANCE = MoxieServer(creds, rbdata, project_id, host, port, cert_required)
        _MOXIE_SERVICE_INSTANCE.add_zmq_handler('embodied.perception.audio.zmqSTTRequest', STTHandler(_MOXIE_SERVICE_INSTANCE))
        _MOXIE_SERVICE_INSTANCE.connect(start=True)
    
    return _MOXIE_SERVICE_INSTANCE
    
if __name__ == "__main__":
    c = create_service_instance("openmoxie", "duranaki.com", 8883)
    while True:
        time.sleep(60)
        c.print_metrics()
