from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from cere_worker import CereWorker
from moxie_messages import chat_notify_request
from moxie_messages import chat_inference_request
from moxie_messages import chat_autotag_request
from multiprocessing import Condition
import sys
import os
import time
import json
import argparse
import uuid
import threading
import pathlib

#CUSTOM_GPT3_MODEL = "chatgpt"
#CUSTOM_GPT3_MODEL = "davinci3"
CUSTOM_GPT3_MODEL = None
URGENCY_LIST = ["normal", "casual", "immediate"]

request_id = ""
session_uuid = ""
session_auid = ""
is_connected = False
interactive_context = "self_low"
interactive_context_override = None
interactive_prompt_override = None
interactive_urgency = "normal"
last_user_speech = ""
log_json = None
log_text = None

seq = 1

cereworker = None

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

def on_any_command(command, payload):
    pass

def on_chat_response(command, payload):
    global seq

    if payload.get("event_id") == request_id:
        if log_json:
            print(json.dumps(payload, indent=4), file=log_json)
        if payload["result"] == 9:
            log_and_print(f"Moxie: [animation:thinking]")
        else:
            if payload["result"] != 0:
                rst = payload["result"]
                log_and_print(f"Moxie: [error {rst}]")
            else:
                try:
                    outplain = str(payload["input"])
                except:
                    try:
                        outplain = str(payload["output"])
                    except:
                        outplain = "No-Output"
                log_and_print(f"Tags: {outplain}")

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

def run_thread_proc(name):
    run_transcript(c)

def on_connect(client, rc):
    global is_connected
    global runner_thread
    is_connected = True
    if False:
        print(f"Running transcript against remote chat.")
        runner_thread = threading.Thread(target=run_thread_proc, args=("Transcript Runner",))
        runner_thread.start()

def notify_moxie_speech(client, moxie_speech):
    global seq
    mmsg = chat_notify_request(moxie_speech, session_uuid, session_auid, seq, user_speech="", topic=topic_from_args())
    if client:
        log_and_print(f"Moxie: {moxie_speech}")
        log_and_publish(client, mmsg)
    time.sleep(1.0)
    pass

def prompt_and_send():
    global request_id
    global interactive_context
    global interactive_context_override
    global interactive_prompt_override
    global interactive_urgency
    global last_user_speech

    speech = input("Say something: ")
    last_user_speech = speech
    log_only(f"User: {last_user_speech}")
    request_id = str(uuid.uuid4())
    mmsg = chat_autotag_request(speech, session_uuid, session_auid, request_id, topic=topic_from_args())

    with rcv:
        log_and_publish(c, mmsg)
        rcv.wait()

parser = argparse.ArgumentParser(description='Transcript or Interface Chat Test')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--production", "--production", action="store_true", help="Use rc-production instead of rc-staging")
parser.add_argument("--nolog", "--nolog", action="store_true", help="Disable logging")
parser.add_argument("--tts", dest="tts", metavar="tts", type=str, action="store", help="Path to cereproc tts app")
parser.add_argument("--player", dest="wavplay", metavar="wavplay", type=str, action="store")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
args = parser.parse_args()

creds = RobotCredentials()
c = MoxieClient(creds, endpoint=args.iot) if args.iot else MoxieClient(creds)
c.add_connect_handler(on_connect)
c.add_config_handler(on_config)
c.add_command_handler("remote_chat", on_chat_response)
c.add_command_handler("*", on_any_command)
c.connect(start=True)

if True:
    # Interactive chat - we loop for ever trying to chat
    print("Waiting to connect...")
    cw = 0
    while not is_connected and cw < 10:
        time.sleep(0.5)
        cw += 1
    if not is_connected:
        print("Gave up trying to connect.")
        os._exit(os.EX_OK)
    if args.tts:
        cereworker = CereWorker(args.tts, "afplay" if not args.wavplay else args.wavplay)
        cereworker.start()

    print("Auto-tagging mode\n- Type anything else to speak")
    make_session()
    while True:
        prompt_and_send()
else:
    # Transcript runner, we wait for our thread, then for it to complete
    while not runner_thread:
        time.sleep(0.5)
    runner_thread.join()

c.stop()
