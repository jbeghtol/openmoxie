from robot_credentials import RobotCredentials, STORE_PATH
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
import random
import requests
import datetime
import pickle

CHAT_TIMEOUT = 7.0

RANDOM_RESPONSES = ["i don't have a lot to say about that", "that really makes me think", "a great topic to get us started"]

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
last_worker_version = ""
last_outplain = ""
seq = 1

# cv for interactive chat
rcv = Condition()
runner_thread = None
SLACK_TOKEN = os.environ.get('SLACK_TOKEN', None)
AGENT_NAME = os.environ['USER']
CHANNEL_MONITOR = "CS9QVG339" # build_server
CHANNEL_ALERT = "CS9QVG339" # devops
ATTN_SUFFIX = "<@UM2U68FDW>" # @justin

CACHE_FILEPATH = os.path.join(STORE_PATH, "checkin.bin")

TRANSCRIPT = []

def send_slack(msg: str, channel_id: str):
    if not SLACK_TOKEN:
        return

    data = {
        "token": SLACK_TOKEN,
        "channel": channel_id,
        "text": msg
    }
    r = requests.post("https://slack.com/api/chat.postMessage", data=data)
    if r.status_code == 200 and r.json()["ok"]:
        print(f"Slack successfully sent to channel '{channel_id}': {msg}")
    else:
        print(f"FAILED to send Slack to channel '{channel_id}': {msg}")

def log_and_publish(cli, msg):
    if log_json:
        print(json.dumps(msg, indent=4), file=log_json, flush=True)
    cli.publish_canned(msg)

def log_only(msg):
    global TRANSCRIPT
    TRANSCRIPT.append(msg)
    if log_text:
        print(msg, file=log_text, flush=True)

def log_and_print(msg):
    log_only(msg)
    print(msg)

def handle_failure(msg):
    topic = topic_from_args()
    log_and_print("FAILURE: " + msg)
    msg = f"[{AGENT_NAME}] :warning: Remote Chat [{topic}] Checkin FAILED! {ATTN_SUFFIX}"
    for line in TRANSCRIPT:
        msg += f"\n> {line}"
    send_slack(msg, CHANNEL_ALERT)

def handle_success(msg, result = None, show_transcript = False):
    topic = topic_from_args()
    log_and_print("SUCCESS: " + msg)
    msg = f"[{AGENT_NAME}] :white_check_mark: Remote Chat [{topic}] Checkin Successful! {msg}"
    if show_transcript:
        for line in TRANSCRIPT:
            msg += f"\n> {line}"
    send_slack(msg, CHANNEL_MONITOR)
    delta_msg = compare_last_success(result)
    if delta_msg and args.delta:
        send_slack(delta_msg, CHANNEL_ALERT)

def compare_last_success(record):
    # read the last one
    if os.path.isfile(CACHE_FILEPATH):
        with open(CACHE_FILEPATH, "rb") as f:
            last_success_record = pickle.load(f)
    else:
        last_success_record = None

    # write the current one
    with open(CACHE_FILEPATH, "wb") as f:
        pickle.dump(record, f)

    has_changes = False
    if last_success_record:
        result_msg = f"[{AGENT_NAME}] :arrow_up: Remote chat has updated! "
        if last_success_record["worker_version"] != record["worker_version"]:
            result_msg += " Worker from `" + last_success_record["worker_version"][:7] + "` to `" + record["worker_version"][:7] + "`."
            has_changes = True
        if last_success_record["context_version"] != record["context_version"]:
            result_msg += " Context store from `" + last_success_record["context_version"] + "` to `" + record["context_version"] + "`."
            has_changes = True

        removed_set = last_success_record["context_id_set"].difference(record["context_id_set"])
        if len(removed_set) > 0:
            result_msg += " Removed contexts: `" + ",".join(removed_set) + "`."
            has_changes = True
        added_set = record["context_id_set"].difference(last_success_record["context_id_set"])
        if len(added_set) > 0:
            result_msg += " New contexts: `" + ",".join(added_set) + "`."
            has_changes = True

    return result_msg if has_changes else None

def on_chat_response(command, payload):
    global seq
    global all_contexts
    global last_worker_version
    global all_contexts_version
    global last_outplain

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
                last_worker_version = payload.get("worker_image", last_worker_version)
                last_outplain = outplain
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

def prompt_and_log(context, command="prompt", user_speech=""):
    global request_id
    request_id = str(uuid.uuid4())
    mmsg = chat_inference_request(user_speech, session_uuid, session_auid, request_id, topic=topic_from_args(), command=command, conversation_context=context)
    with rcv:
        if not user_speech:
            log_and_print(f"Requesting prompt for context: {context}, context store version: {all_contexts_version}")
        else:
            log_and_print(f"User: {user_speech}")
        log_and_publish(c, mmsg)
        if not rcv.wait(CHAT_TIMEOUT):
            handle_failure("Timed out requesting prompt")
            return False
        return True

def run_thread_proc(name):
    request = CANNED_QUERY_REMOTE_CHAT_CONTEXTS
    request["topic"] = topic_from_args()
    if args.api_version:
        api_ver = int(args.api_version)
        request["payload"]["api_version"] = api_ver
    else:
        api_ver = request["payload"]["api_version"]
    endp = request["topic"]
    with rcv:
        log_and_print(f"Querying from {endp} using api_version={api_ver}")
        start = datetime.datetime.now()
        c.publish_canned(request)
        if not rcv.wait(CHAT_TIMEOUT):
            handle_failure("Timed out querying chat contexts.")
            return
        query_s = (datetime.datetime.now() - start).total_seconds()
    if not all_contexts:
        handle_failure("Received no chat contexts")
        return

    clist = all_contexts["conversation_contexts"]
    context_id = random.choice(clist)["context"]["id"]
    print(f"Validation will use conversation {context_id} from context store version {all_contexts_version}")
    make_session()

    # get the initial prompt
    start = datetime.datetime.now()
    if not prompt_and_log(context_id):
        return
    prompt_s = (datetime.datetime.now() - start).total_seconds()

    # sleep while user hears thinks
    time.sleep(3.0)

    # play a random user response and get an inference
    start = datetime.datetime.now()
    if not prompt_and_log(context_id, command="continue", user_speech=random.choice(RANDOM_RESPONSES)):
        return
    infer_s = (datetime.datetime.now() - start).total_seconds()

    c_id_list = set([ ci["context"]["id"] for ci in clist ])
    result_record = { "context_version": all_contexts_version, "worker_version": last_worker_version, "context_id_set": c_id_list  }
    handle_success(f"Context:`{context_id}` V:`{all_contexts_version}` Worker:`{last_worker_version[:7]}` Query:`{query_s}` Prompt:`{prompt_s}` Infer:`{infer_s}`", result=result_record)

def on_connect(client, rc):
    global is_connected
    global runner_thread
    is_connected = True
    print(f"Connected - Running Watchdog checkin test")
    runner_thread = threading.Thread(target=run_thread_proc, args=("Watchdog Runner",))
    runner_thread.start()

    
parser = argparse.ArgumentParser(description='Remote Chat Checkin')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--production", "--production", action="store_true", help="Use rc-production instead of rc-staging")
parser.add_argument("--nolog", "--nolog", action="store_true", help="Disable logging")
parser.add_argument("--delta", "--delta", action="store_true", help="Report deltas since last checkin")
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
