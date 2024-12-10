from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import chat_notify_request
from moxie_messages import chat_inference_request
from moxie_messages import CANNED_QUERY_REMOTE_CHAT_CONTEXTS
from multiprocessing import Condition
import sys
import os
import time
import json
import argparse
import uuid
import threading
import pathlib

URGENCY_LIST = ["normal", "casual", "immediate"]

request_id = ""
session_uuid = ""
session_auid = ""
is_connected = False
interactive_context = "self_low"
interactive_context_override = None
interactive_urgency = "normal"
last_user_speech = ""
log_json = None
log_text = None
all_contexts = None
all_contexts_version = None
seq = 1

# cv for interactive chat
rcv = Condition()
runner_thread = None

def log_and_publish(cli, msg):
    if log_json:
        print(json.dumps(msg, indent=4), file=log_json, flush=True)
    cli.publish_canned(msg)

def log_only(msg):
    if log_text:
        print(msg, file=log_text, flush=True)

def log_and_print(msg):
    log_only(msg)
    print(msg)

def on_chat_response(command, payload):
    global seq
    global all_contexts
    global all_contexts_version

    if payload.get("event_id") == "test_query_uuid":
        all_contexts = payload["query_data"]["contexts"]
        all_contexts_version = payload["query_data"]["version"]
        with rcv:
            rcv.notify_all()
    elif payload.get("event_id") == request_id:
        if log_json:
            print(json.dumps(payload, indent=4), file=log_json)
        if payload["result"] == 9:
            log_and_print(f"Moxie: [animation:thinking]")
        else:
            if payload["result"] != 0:
                rst = payload["result"]
                log_and_print(f"Moxie: [error {rst}]")
            else:
                outplain = payload["output"]["text"]
                try:
                    respact = "[" + payload["response_action"]["action"] + " -> " + payload["response_action"]["module_id"] + "]"
                except:
                    respact = ""
                log_and_print(f"Moxie: {outplain} {respact}")
                # for interactive clients, we need to let them know we played the response
                mmsg = chat_notify_request(outplain, session_uuid, session_auid, seq, user_speech=last_user_speech, topic=topic_from_args())
                log_and_publish(c, mmsg)
                seq += 1
            with rcv:
                rcv.notify_all()

def make_session():
    global session_uuid
    global session_auid
    global log_text
    global log_json
    # make session uuid
    session_uuid = str(uuid.uuid4())
    # get user id from credentials
    session_auid = creds.get_user_id()
    if args.nolog:
        print(f"Creating new session {session_uuid} with no logging")
    else:
        session_root = os.path.join(".", "log", session_uuid)
        print(f"Creating new session, logging to {session_root}")
        pathlib.Path(session_root).mkdir(parents=True, exist_ok=True)
        log_text = open(os.path.join(session_root, "script.txt"), "w")
        log_json = open(os.path.join(session_root, "events.json"), "w")

def topic_from_args():
    topic = "remote-chat-staging"
    if args.production:
        topic = "remote-chat"
    return topic

def on_config(topic, payload):
    pass

def prompt_and_log(context):
    global request_id
    request_id = str(uuid.uuid4())
    mmsg = chat_inference_request("", session_uuid, session_auid, request_id, topic=topic_from_args(), command="prompt", conversation_context=context)
    with rcv:
        log_and_print(f"Requesting prompt for context: {context}")
        log_and_publish(c, mmsg)
        rcv.wait()

def run_thread_proc(name):
    request = CANNED_QUERY_REMOTE_CHAT_CONTEXTS
    request["topic"] = topic_from_args()
    if args.api_version:
        api_ver = int(args.api_version)
        request["payload"]["api_version"] = api_ver
    else:
        api_ver = request["payload"]["api_version"]
    endp = request["topic"]
    print(f"Querying from {endp} using api_version={api_ver}")
    c.publish_canned(request)
    with rcv:
        rcv.wait()
    if all_contexts: 
        clist = all_contexts["conversation_contexts"]
        ccsize = len(clist)
        print(f"Received {ccsize} contexts!")
        make_session()
        for cc in clist:
            context_id = cc["context"]["id"]
            prompt_and_log(context_id)
            time.sleep(1.0)

def on_connect(client, rc):
    global is_connected
    global runner_thread
    is_connected = True
    print(f"Connected - Running Prompt Test")
    runner_thread = threading.Thread(target=run_thread_proc, args=("Prompt Runner",))
    runner_thread.start()

    
parser = argparse.ArgumentParser(description='Test Remote Chat Prompts')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--production", "--production", action="store_true", help="Use rc-production instead of rc-staging")
parser.add_argument("--nolog", "--nolog", action="store_true", help="Disable logging")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
args = parser.parse_args()

creds = RobotCredentials()
c = MoxieClient(creds, endpoint=args.iot) if args.iot else MoxieClient(creds)
c.add_connect_handler(on_connect)
c.add_config_handler(on_config)
c.add_command_handler("remote_chat", on_chat_response)
c.connect(start=True)

# Transcript runner, we wait for our thread, then for it to complete
while not runner_thread:
    time.sleep(0.5)
runner_thread.join()

c.stop()
