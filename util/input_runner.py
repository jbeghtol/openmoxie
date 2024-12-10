from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import chat_notify_request
from moxie_messages import chat_inference_request
from moxie_messages import chat_remote_module_request
from multiprocessing import Condition
import sys
import os
import time
import json
import argparse
import uuid
import threading
import pathlib
import csv

REQUIRED_KEYS = ["user_speech"]
LOGGING_KEYS = ["faq_intent", "filter_intent", "lore_intent", "gpt3_speech", "source" ]
URGENCY_LIST = ["normal", "casual", "immediate"]
RUNNER_DEVICE_SETTINGS = None


request_id = ""
session_uuid = ""
session_auid = ""
session_root = None
is_connected = False
interactive_context = "self_low"
interactive_context_override = None
interactive_prompt_override = None
interactive_urgency = "normal"
last_user_speech = ""
log_json = None
log_text = None
last_remote_response = None
last_faq = None
last_filter = None
last_lore = None
last_source = None

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

def get_filter_info(payload):
    try:
        prefix = "UNSAFE " if payload["input"]["safety"]["is_unsafe"] else "OK "
        return prefix + str(payload["input"]["safety"]["intents"])
    except:
        return "Err"

def get_faq_info(payload):
    nlpint = payload.get("nlp_intent", {})
    if "matched_intent" in nlpint:
        return nlpint["matched_intent"]
    return None

def get_lore_info(payload):
    if "lore_intents" in payload:
        return str(payload["lore_intents"])
    return ""

def on_chat_response(command, payload):
    global seq
    global last_remote_response
    global last_faq
    global last_filter
    global last_lore
    global last_source

    if payload.get("event_id") == request_id:
        if log_json:
            print(json.dumps(payload, indent=4), file=log_json)
        if payload["result"] == 9:
            log_and_print(f"Moxie: [animation:thinking]")
        else:
            if payload["result"] != 0:
                rst = payload["result"]
                log_and_print(f"Moxie: [error {rst}]")
                last_remote_response = "error"
            else:
                outplain = payload["output"]["text"]
                last_remote_response = outplain
                last_filter = get_filter_info(payload)
                last_faq = get_faq_info(payload)
                last_lore = get_lore_info(payload)
                last_source = payload["output"]["source"]
                try:
                    respact = "[" + payload["response_action"]["action"] + " -> " + payload["response_action"]["module_id"] + "]"
                except:
                    respact = ""
                log_and_print(f"Moxie: {outplain} {respact}")
                # if not args.in_file:
                #     mmsg = chat_notify_request(outplain, session_uuid, session_auid, seq, user_speech=last_user_speech, topic=topic_from_args())
                #     log_and_publish(c, mmsg)
                #     seq += 1

            with rcv:
                if args.debug:
                    print("-- Notifying response ready!")
                rcv.notify_all()

def make_session(session_instance):
    global session_uuid
    global session_auid
    global log_text
    global log_json
    global session_root
    # make session uuid
    session_uuid = str(uuid.uuid4())
    # get user id from credentials
    session_auid = creds.get_user_id()
    if args.nolog:
        print(f"Creating new session {session_uuid} with no logging")
    else:
        session_root = os.path.join(".", "log", session_uuid)
        print(f"Creating new session for {session_instance}, logging to {session_root}")
        pathlib.Path(session_root).mkdir(parents=True, exist_ok=True)
        log_text = open(os.path.join(session_root, "script.txt"), "w")
        log_json = open(os.path.join(session_root, "events.json"), "w")


def topic_from_args():
    topic = "remote-chat-staging"
    if args.production:
        topic = "remote-chat"
    return topic


def check_required_keys(reader):
    for key in REQUIRED_KEYS:
        if not key in reader.fieldnames:
            raise Exception(f"Could not find required header field {key} from fields " + str(reader.fieldnames))

def run_transcript(client, delay=1.0):
    global request_id
    global session_uuid
    global session_auid
    global interactive_context
    global interactive_context_override
    global interactive_prompt_override
    global interactive_urgency
    global seq
    global RUNNER_DEVICE_SETTINGS

    starttime = round(time.time())
    csvlog = os.path.join(".", "log", f"input_results_{starttime}.csv")
    print(f"Writing csv summary to {csvlog}")

    if args.prompt:
        with open(args.prompt, "r") as promptf:
            interactive_context = "custom"
            interactive_context_override = promptf.read()
            print(f"Loaded custom prompt from {args.prompt}")
            RUNNER_DEVICE_SETTINGS = {"props":{"gpt3":"gptturbo","remote_transition":"1","safety": "0"}}

    last_session_instance = None
    with open(args.in_file, "r", encoding='utf-8-sig') as f, open(csvlog, "w") as csvf:
        reader = csv.DictReader(f)
        writer = None
        line_num = 0
        user_speech = ""
        last_output_type = "NORMAL"
        fallback_handled = False
        fallback_count = 0
        make_session("input_runner_combined")
        check_required_keys(reader)

        for line in reader:
            line_num += 1
            # skip empties
            if not line["user_speech"]:
                continue

            user_speech = line["user_speech"]
            request_id = str(uuid.uuid4())
            if args.langflow:
                mmsg = chat_remote_module_request(user_speech, str(uuid.uuid4()), session_auid,request_id,command='start',topic=topic_from_args(), module_id=args.langflow, setting_override=RUNNER_DEVICE_SETTINGS) 
            else:
                mmsg = chat_inference_request(user_speech, str(uuid.uuid4()), session_auid,request_id,command='start',topic=topic_from_args(), conversation_context=interactive_context, urgency=interactive_urgency, cc_override=interactive_context_override, setting_override=RUNNER_DEVICE_SETTINGS) 
            #mmsg["payload"]["allow_multiple"] = False
            log_and_print(f"User: {user_speech}")
            log_and_publish(client, mmsg)
            with rcv:
                if args.debug:
                    print("-- Waiting for response")
                rcv.wait()
                if args.debug:
                    print("-- Wait complete")
            if not writer:
                writer = csv.DictWriter(csvf, list(line.keys()) + LOGGING_KEYS)
                writer.writeheader()
            line["gpt3_speech"] = last_remote_response
            line["faq_intent"] = last_faq
            line["filter_intent"] = last_filter
            line["source"] = last_source
            line["lore_intent"] = last_lore
            writer.writerow(line)
            csvf.flush()




def on_config(topic, payload):
    pass

def run_thread_proc(name):
    run_transcript(c)

def on_connect(client, rc):
    global is_connected
    global runner_thread
    is_connected = True
    if args.in_file:
        if runner_thread:
            print(f"Runner thread already started.")
        else:
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


parser = argparse.ArgumentParser(description='Input runner')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--in_file", dest="in_file", metavar="in_file", type=str, action="store", help="CSV Input file with inputs")
parser.add_argument("--langflow", dest="langflow", metavar="langflow", type=str, action="store", help="Module ID for langflow conversation")
parser.add_argument("--prompt", dest="prompt", metavar="prompt", type=str, action="store", help="Text of a gpt prompt")
parser.add_argument("--production", "--production", action="store_true", help="Use rc-production instead of rc-staging")
parser.add_argument("--nolog", "--nolog", action="store_true", help="Disable logging")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
parser.add_argument("--debug", "--debug", action="store_true", help="Enable debug logging")
args = parser.parse_args()

if not args.in_file:
    print("Input file is required")
    os._exit(os.EX_OK)

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
