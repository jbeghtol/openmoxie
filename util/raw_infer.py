from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from cere_worker import CereWorker
from moxie_messages import chat_notify_request
from moxie_messages import chat_raw_request
from multiprocessing import Condition
import sys
import os
import time
import json
import argparse
import uuid
import threading
import pathlib

CUSTOM_GPT3_MODEL = "chatgpt"
#CUSTOM_GPT3_MODEL = "gpt-4"
CUSTOM_SETTINGS = {"props":{"group":"0","gpt3":CUSTOM_GPT3_MODEL,"remote_transition":"1","debug":"1","rb_menu_topic":"moximusprime","mp_max_volleys":"25"}}

#CUSTOM_GPT3_MODEL = "davinci3"
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
                outplain = payload["output"]["text"]
                try:
                    respact = "[" + payload["response_action"]["action"] + " -> " + payload["response_action"]["module_id"] + "]"
                except:
                    respact = ""
                log_and_print(f"Moxie: {outplain} {respact}")
                if True:
                    if cereworker:
                        cereworker.queue_markup(outplain)
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
    command = "continue"

    if speech.startswith("+"):
        # +context, prompt to new context
        if len(speech) > 1:
            # update context, then prompt
            interactive_context = speech[1:]
            interactive_urgency = "normal"
            interactive_context_override = None
            command = "prompt"
        else:
            command = "reprompt"
        speech = ""
        last_user_speech = ""
        log_and_print(f"Requesting {command} for context: {interactive_context}, urgency={interactive_urgency}")
    elif speech.startswith("-"):
        urg = speech[1:]
        if urg not in URGENCY_LIST:
            log_and_print(f"Pick an urgency in {URGENCY_LIST}")
        else:
            interactive_urgency = urg
            log_and_print(f"Urgency updated for context: {interactive_context}, urgency={interactive_urgency}")
        return
    elif speech.startswith("/"):
        if len(speech) > 1:
            # update context, then prompt
            moxie_speech = speech[1:]
            #Inject notify with moxie speech
            notify_moxie_speech(c, moxie_speech)
        else:
            log_and_print(f"Invalid, / without moxie speech.")
        return
    elif speech.startswith("="):
        #TODO: Only prompt if ends with ! and remove the !
        req_prompt = speech.endswith("!")
        if req_prompt:
            speech = speech[:-1]
        # =[context_text], prompt to new raw context context
        if len(speech) > 1:
            # update context, then prompt
            interactive_context_override = speech[1:]
            interactive_urgency = "normal"
            interactive_context = "custom"
            if not req_prompt:
                log_and_print(f"Updated context (no prompt): {interactive_context} as text: {interactive_context_override}")
                return
            command = "prompt"
            log_and_print(f"Updated context: {interactive_context} as text: {interactive_context_override}")
        else:
            log_and_print(f"Invalid, = without context text.")
            return
        speech = ""
        last_user_speech = ""
        log_and_print(f"Requesting {command} for context: {interactive_context}, urgency={interactive_urgency}")
    elif speech.startswith("!"):
        # ![context_text], prompt context custom
        if len(speech) > 1:
            # update context, then prompt
            interactive_prompt_override = speech[1:]
            interactive_urgency = "normal"
            command = "prompt"
            log_and_print(f"Updated prompt context: as text: {interactive_prompt_override}")
        else:
            log_and_print(f"Invalid, = without prompt context text.")
            return
        speech = ""
        last_user_speech = ""
        log_and_print(f"Requesting {command} for context: {interactive_context}, urgency={interactive_urgency}")
    else:
        last_user_speech = speech
        log_only(f"User: {last_user_speech}")

    request_id = str(uuid.uuid4())
    mmsg = chat_raw_request(speech, session_uuid, session_auid,request_id, topic=topic_from_args(), setting_override=CUSTOM_SETTINGS)

    if interactive_prompt_override:
        mmsg["payload"]["prompt_context"] = { "text": interactive_prompt_override }
        interactive_prompt_override = None
        
    with rcv:
        log_and_publish(c, mmsg)
        rcv.wait()

parser = argparse.ArgumentParser(description='RAW GPT Chat Test')
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

    print("Connected to interactive chat.\n- Type anything to query GPTx")
    make_session()
    while True:
        prompt_and_send()
else:
    # Transcript runner, we wait for our thread, then for it to complete
    while not runner_thread:
        time.sleep(0.5)
    runner_thread.join()

c.stop()
