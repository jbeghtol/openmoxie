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
from .protos.embodied.wifiapp.QRCommands_pb2 import QRCommand
from .zmq_stt_handler import STTHandler
from ..models import HiveConfiguration

_BASIC_FORMAT = '{1}'
_MOXIE_SERVICE_INSTANCE = None
_OPENAI_APIKEY=None

def now_ms():
    return time.time_ns() // 1_000_000

logger = logging.getLogger(__name__)


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
    def __init__(self, robot, rbdata, project_id, mqtt_host, mqtt_port, cert_required=True):
        self._robot = robot
        self._robot_data = rbdata
        self._mqtt_project_id = project_id
        self._mqtt_endpoint = mqtt_host
        self._port = mqtt_port
        self._cert_required = cert_required
        #self._mqtt_client_id = _IOT_CLIENT_ID_FORMAT.format(self._mqtt_project_id, self._robot.device_id)
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

    def connect(self, start = False):
        jwt_token = self._robot.create_jwt(self._mqtt_project_id)
        self._client.username_pw_set(username='unknown', password=jwt_token)
        logger.info(f"connecting to: {self._mqtt_endpoint}")
        self._client.connect(self._mqtt_endpoint, self._port, 60)
        if start:
            self.start()

    def add_connect_handler(self, callback):
        self._connect_handlers.append(callback)

    def add_zmq_handler(self, protoname, callback):
        self._zmq_handlers[protoname] = callback

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
        logger.info(f"Connected with result code {rc}")
        # The only two supported in IOT - commands for a wildcard of commands, config for our robot configuration
        client.subscribe('/devices/+/events/#')
        client.subscribe('/devices/+/state')
        # Subscriptions to monitor clients and broker logs
        client.subscribe('$SYS/broker/clients/#')
        client.subscribe('$SYS/broker/log/#')
        for ch in self._connect_handlers:
            ch(self, rc) 

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
            logger.warning(f"Error handling mqtt messsage: {e}")
    

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
            # else:
            #     logger.info(f'LOGMSG->{line}')

    def on_client_metrics(self, basetype, msg):
        self._client_metrics[basetype] = int(msg.payload.decode('utf-8'))

    # ALL EVENTS FROM-DEVICE ARRIVE HERE
    def on_device_event(self, device_id, eventname, msg):
        #logger.debug(f"Rx EVENT topic: {eventname}")
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
                self._remote_chat.handle_request(device_id, rcr)
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
                                                    { 'command': 'query_result', 'request_id': req_id, 
                                                    'license_values': [ 
                                                        { 'id': 'google_speech', 'license': self._google_service_account}
                                                        ]
                                                        })
            elif 'mentor_behavior' in csa:
                # MENTOR BEHAVIOR REPORT - Robot informing what user has done
                self._worker_queue.submit(self.ingest_mentor_behavior, device_id, csa['mentor_behavior'])

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
        self.send_command_to_bot_json(device_id, 'query_result', { 'command': 'query_result', 'request_id': req_id, 'schedule': schedule} )

    # NOTE: Called from worker thread pool
    def ingest_mentor_behavior(self, device_id, mbh):
        self._robot_data.add_mbh(device_id, mbh)

    # NOTE: Called from worker thread pool
    def provide_mentor_behaviors(self, req_id, device_id):
        mbh = self._robot_data.get_mbh(device_id)
        logger.info(f'Providing {len(mbh)} MBH records to {device_id}')
        self.send_command_to_bot_json(device_id, 'query_result', { 'command': 'query_result', 'request_id': req_id, 'mentor_behaviors': mbh} )

    # NOTE: Called from worker thread pool
    def on_device_connect(self, device_id, connected, ip_addr=None):
        if connected:
            logger.info(f'NEW CLIENT {device_id} from {ip_addr}')
            self._robot_data.db_connect(device_id)
            # Sleep to avoid sending sub/config before client is ready
            time.sleep(1.0)
            self.send_config_to_bot_json(device_id, self._robot_data.get_config(device_id))
            # subscripe to ZMQ STT
            sub = ProtoSubscribe()
            sub.protos.append('embodied.perception.audio.zmqSTTRequest')
            sub.timestamp = now_ms()
            logger.info(f'Subscribed to ZMQ STT')
            self.send_zmq_to_bot(device_id, sub)
        else:
            self._robot_data.db_release(device_id)
            logger.info(f'LOST CLIENT {device_id}')

    # Fallback, we missed the connect message but robot is connected
    def check_device_connect(self, device_id, info="Missing"):
        if self._robot_data.connect_init_needed(device_id):
            logger.info(f"Unconnected robot {device_id} location {info}.  Connecting now.")
            self._worker_queue.submit(self.on_device_connect, device_id, True, info)

    def on_device_state(self, device_id, msg):
        logger.debug(f"Rx STATE topic for device {device_id}")
        self.check_device_connect(device_id, "State")
        self._robot_data.put_state(device_id, json.loads(msg.payload))

    def send_config_to_bot_json(self, device_id, payload: dict):
        self._client.publish(f"/devices/{device_id}/config", payload=json.dumps(payload))

    def send_command_to_bot_json(self, device_id, command, payload: dict):
        self._client.publish(f"/devices/{device_id}/commands/{command}", payload=json.dumps(payload))

    def send_zmq_to_bot(self, device_id, msgobject):
        payload = (msgobject.DESCRIPTOR.full_name + ":").encode('utf-8') + msgobject.SerializeToString()
        self._client.publish(f"/devices/{device_id}/commands/zmq", payload=payload)

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

    def print_metrics(self):
        logger.info(f"Client Metrics: {self._client_metrics}")

    def start(self):
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()

    def get_web_session_for_module(self, device_id, module_id, content_id):
        sess = self._remote_chat.get_web_session_for_module(device_id, module_id, content_id)
        sess.set_auto_history(True)
        return sess
    
    def remote_chat(self):
        return self._remote_chat

    def robot_data(self):
        return self._robot_data

    def update_from_database(self):
        hive_config = HiveConfiguration.objects.filter(name="default").first()
        set_openai_key(hive_config.openai_api_key if hive_config else None)
        self._google_service_account = hive_config.google_api_key if hive_config else None
        self._remote_chat.update_from_database()

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

def cleanup_instance():
    global _MOXIE_SERVICE_INSTANCE
    if _MOXIE_SERVICE_INSTANCE:
        _MOXIE_SERVICE_INSTANCE._client.disconnect()
        _MOXIE_SERVICE_INSTANCE = None

def get_instance():
    global _MOXIE_SERVICE_INSTANCE
    return _MOXIE_SERVICE_INSTANCE

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
