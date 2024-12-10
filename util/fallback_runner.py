from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import chat_notify_request
from moxie_messages import chat_inference_request
from markup import alt_text
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

# Use this specific gpt3 model to generate fallbacks
CUSTOM_GPT3_MODEL = "davinci3"
#CUSTOM_GPT3_MODEL = None

FALLBACK_DEVICE_SETTINGS = {"props":{"gpt3":CUSTOM_GPT3_MODEL,"remote_transition":"1","debug":"1","mp_max_volleys":"25", "no_gpt_bias":"1"}}

# keys we need in the input
REQUIRED_KEYS = [ "chat_input", "chat_output", "module_id", "output_type", "user_id", "session_id", "instance_id" ]
# keys we add to the output
LOGGING_KEYS = [ "plain_output", "gpt3_speech","context", "faq_intent", "filter_intent", "lore_intent","source", "session_dir"]
URGENCY_LIST = ["normal", "casual", "immediate"]

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
FALLBACK_MAP = None
last_remote_response = None
last_payload = None

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
    global last_remote_response
    global last_payload

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
                last_payload = None
            else:
                outplain = payload["output"]["text"]
                last_remote_response = outplain
                last_payload = payload
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

def data_fallback_context(module_id):
    if FALLBACK_MAP:
        if module_id in FALLBACK_MAP:
            return FALLBACK_MAP[module_id]
        elif "default" in FALLBACK_MAP:
            return FALLBACK_MAP["default"]

    return "You are in the middle of an activity and have asked the user something. Respond to the child but remind them what we were doing and don't ask any questions."

def get_fallback_context(module_id):
    if args.interact:
        data = data_fallback_context(module_id)
        print(f"[Auto context - enter to accept or type one] -> {data}")
        user_context = input("Context: ")
        if user_context:
            return user_context
        return data
    else:
        return data_fallback_context(module_id)

def get_filter_info(payload):
    prefix = "UNSAFE " if payload["input"]["safety"]["is_unsafe"] else "OK "
    return prefix + str(payload["input"]["safety"]["intents"])

def get_faq_info(payload):
    return payload["nlp_intent"]["matched_intent"]

def get_lore_info(payload):
    if "lore_intents" in payload:
        return str(payload["lore_intents"])
    return ""

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

    starttime = round(time.time())
    csvlog = os.path.join(".", "log", f"fallback_output_{starttime}.csv")
    print(f"Writing csv summary to {csvlog}")

    last_session_instance = None
    with open(args.in_file, "r", encoding='utf-8-sig') as f, open(csvlog, "w") as csvf:
        reader = csv.DictReader(f)
        writer = None
        line_num = 0
        user_speech = ""
        fallback_handled = False
        fallback_count = 0
        check_required_keys(reader)

        for line in reader:
            # skip empties
            if not line["user_id"]:
                continue

            if "mentor_behavior_instance_id" in line:
                session_instance = line["user_id"] + "/" + line["session_id"] + "/" + line["mentor_behavior_instance_id"] + "/" + line["instance_id"]
            else:
                session_instance = line["user_id"] + "/" + line["session_id"] + "/" + line["instance_id"]
            # Create a new session each time we transition session_instance
            if session_instance != last_session_instance:
                last_session_instance = session_instance
                make_session(session_instance)
                fallback_count = 0

            user_speech = line["chat_input"]
            speech = alt_text(line["chat_output"])
            output_type = line["output_type"]
            module_id = line["module_id"]
            # dont show events as user speech
            if user_speech.startswith('eb-'):
                user_speech = ''

            # as long as we don't hit a fallback, keep building up the conversation history
            if output_type != "FALLBACK":
                if user_speech or speech:
                    mmsg = chat_notify_request(speech, session_uuid, session_auid, seq, module_id=module_id, user_speech=user_speech, topic=topic_from_args())
                    if user_speech:
                        log_and_print(f"User: {user_speech}")    
                    log_and_print(f"Moxie: {speech}")
                    log_and_publish(client, mmsg)
                    time.sleep(delay)
                    seq += 1
                # skip any empty things (events with no text in the response)
            else:
                fallback_count += 1
                log_and_print(f"[User: {user_speech}]")
                log_and_print(f"[Moxie: {speech}]")
                interactive_context_override = get_fallback_context(module_id)
                line["context"] = interactive_context_override
                log_and_print(f"Fallback-{fallback_count} Module: {module_id} Context: {interactive_context_override}")
                request_id = str(uuid.uuid4())
                mmsg = chat_inference_request(user_speech, session_uuid, session_auid,request_id,
                        topic=topic_from_args(), module_id=module_id, conversation_context=interactive_context, 
                        urgency=interactive_urgency, cc_override=interactive_context_override, setting_override=FALLBACK_DEVICE_SETTINGS)
                if client:
                    log_and_print(f"User: {user_speech}")
                    log_and_publish(client, mmsg)
                    with rcv:
                        rcv.wait()
                    line["gpt3_speech"] = last_remote_response
                    line["faq_intent"] = get_faq_info(last_payload)
                    line["filter_intent"] = get_filter_info(last_payload)
                    line["lore_intent"] = get_lore_info(last_payload)

            if not writer:
                writer = csv.DictWriter(csvf, list(line.keys()) + LOGGING_KEYS)
                writer.writeheader()
            line["plain_output"] = speech
            line["source"] = args.in_file
            line["session_dir"] = session_root
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


parser = argparse.ArgumentParser(description='Fallback contextual session runner')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--in_file", dest="in_file", metavar="in_file", type=str, action="store", help="CSV Input file with input sequences ending in fallbacks")
parser.add_argument("--fb_map", dest="fb_map", metavar="fb_map", type=str, action="store", help="JSON Input file with module names to fallback context")
parser.add_argument("--production", "--production", action="store_true", help="Use rc-production instead of rc-staging")
parser.add_argument("--nolog", "--nolog", action="store_true", help="Disable logging")
parser.add_argument("--interact", "--interact", action="store_true", help="Prompt for custom contexts at each fallback")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
args = parser.parse_args()

if args.fb_map:
    with open(args.fb_map) as f:
        FALLBACK_MAP = json.load(f)

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
