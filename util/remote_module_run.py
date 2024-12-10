from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from cere_worker import CereWorker
from moxie_messages import chat_notify_request
from moxie_messages import chat_remote_module_request
from multiprocessing import Condition
from markup import alt_text
import sys
import os
import time
import json
import argparse
import uuid
import threading
import pathlib

URGENCY_LIST = ["normal", "casual", "immediate"]

request_id = None
ignored_id = None
request_start = None
session_uuid = ""
session_auid = ""
is_connected = False
interactive_module_id = "AB"
interactive_content_id = "bumblebee"
interactive_prompt_override = None
interactive_context = None
interactive_urgency = "normal"
last_user_speech = ""
log_json = None
log_text = None
pending_launch = None

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

def on_chat_response(command, payload):
    global seq
    global request_id
    global request_time
    global ignored_id
    global pending_launch

    eve = payload.get("event_id")
    if eve and eve == request_id:
        hide_notify = request_id == ignored_id
        ignore_prefix = "(Ignored) " if hide_notify else ""
        if log_json:
            print(json.dumps(payload, indent=4), file=log_json, flush=True)
        if payload["result"] == 9 and payload["fallback"]:
            log_and_print(f"{ignore_prefix}Moxie: [animation:thinking]")
        else:
            if payload["result"] not in (0, 9):
                rst = payload["result"]
                log_and_print(f"{ignore_prefix}Moxie: [error {rst}]")
            else:
                try:
                    outplain = alt_text(payload["output"]["markup"])
                except:
                    outplain = "No-Output"
                if 'response_action' in payload:
                    ra = payload["response_action"]
                    if "action" in ra:
                        if ra["action"] == "launch":
                            pending_launch = ( ra["module_id"], ra["content_id"] if "content_id" in ra else "")
                            respact = f'[{payload["response_action"]["action"]} -> {pending_launch}]'
                        elif ra["action"] == "launch_if_confirmed":
                            pending_if = ( ra["module_id"], ra["content_id"] if "content_id" in ra else "")
                            respact = f'[{payload["response_action"]["action"]} -> {pending_if}]'
                        elif ra["action"] == "execute":
                            pending_if = ( ra["function_id"], ra["function_args"] if "function_args" in ra else "")
                            respact = f'[{payload["response_action"]["action"]} -> {pending_if}]'
                        else:
                            respact = f'[{payload["response_action"]["action"]} -> Unsupported action]'
                    else:
                        respact = ""
                    # show, but don't actually launch
                    if hide_notify:
                        pending_launch = None
                else:
                    respact = ""    
                inperplex = ""
                outperplex = ""
                if args.perplex:
                    try:
                        inperplex = "[in-perplexity=" + str(payload["input"]["perplexity"]) + "]"
                        outperplex = "[out-perplexity=" + str(payload["output"]["perplexity"]) + "]"
                    except:
                        pass
                cont_text = " [...]" if payload["result"] == 9 else ""
                if args.time:
                    cont_text += f' ({int((time.time() - request_time)*1000)} ms)';
                log_and_print(f"{ignore_prefix}Moxie: {inperplex} {outplain} {respact}{cont_text}")
                if not hide_notify:
                    if cereworker:
                        cereworker.queue_markup(outplain)
                    # for interactive clients, we need to let them know we played the response
                    chunk_ids = [ payload["chunk_num"] ] if "chunk_num" in payload else []
                    mmsg = chat_notify_request(outplain, session_uuid, session_auid, seq, topic=topic_from_args(), module_id=interactive_module_id, content_id=interactive_content_id, source_event_id=payload["event_id"], chunk_ids=chunk_ids)
                    log_and_publish(c, mmsg)
                    seq += 1

            if payload["result"] != 9:
                # clear the request, done listening for it
                request_id = None
                with rcv:
                    rcv.notify_all()
    elif eve:
        print(f'Warning: Received response for event {eve} we were no longer looking for.')
    elif payload.get("result", 0) != 0:
        print(f'Warning: Received response with error result {payload["result"]}')

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

def run_transcript(client, delay=1.0):
    global request_id
    global request_time
    global session_uuid
    global session_auid
    global interactive_context
    global interactive_context_override
    global interactive_prompt_override
    global interactive_urgency
    global seq

    make_session()
    with open(args.in_file, "r") as f:
        line_num = 0
        pending_user_speech = ""
        for line in f:
            ss = line.split(':', 1)
            if len(ss) < 2:
                continue
            speaker = ss[0].strip()
            speech = ss[1].strip()
            if speaker.startswith("U"):
                if len(pending_user_speech) == 0:
                    pending_user_speech += " "
                pending_user_speech += speech
            elif speaker.startswith("M"):
                mmsg = chat_notify_request(speech, session_uuid, session_auid, seq, user_speech=pending_user_speech, topic=topic_from_args())
                if client:
                    if pending_user_speech:
                        log_and_print(f"User: {pending_user_speech}")    
                    log_and_print(f"Moxie: {speech}")
                    log_and_publish(client, mmsg)
                else:
                    print(mmsg)
                time.sleep(delay)
                pending_user_speech = ""
                seq += 1
            elif speaker.startswith("C"):
                interactive_context = speech
                interactive_context_override = None
                log_and_print(f"Context Update: {interactive_context}")
                continue
            elif speaker.startswith("T"):
                interactive_context = "custom"
                interactive_context_override = speech
                log_and_print(f"Context Custom Update: {interactive_context_override}")
                continue
            elif speaker.startswith("R"):
                urg = speech
                if urg not in URGENCY_LIST:
                    log_and_print(f"Pick an urgency in {URGENCY_LIST}")
                else:
                    interactive_urgency = urg
                    log_and_print(f"Urgency updated for context: {interactive_context}, urgency={interactive_urgency}")
                continue
            else:
                continue

    request_id = str(uuid.uuid4())
    mmsg = chat_inference_request(pending_user_speech, session_uuid, session_auid,request_id,topic=topic_from_args(), module_id=interactive_module_id, urgency=interactive_urgency, content_id=interactive_content_id) 
    request_time = time.time()
    if client:
        log_and_print(f"User: {pending_user_speech}")
        log_and_publish(client, mmsg)
        with rcv:
            rcv.wait()
    else:
        print(mmsg)
    pass

def on_config(topic, payload):
    pass

def run_thread_proc(name):
    run_transcript(c)

def on_connect(client, rc):
    global is_connected
    global runner_thread
    is_connected = True
    if args.in_file:
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
    global ignored_id
    global request_time
    global interactive_context
    global interactive_context_override
    global interactive_prompt_override
    global interactive_module_id
    global interactive_content_id
    global interactive_urgency
    global last_user_speech
    global seq
    global pending_launch

    # auto-launch
    if args.launch and pending_launch:
        speech = f"+{pending_launch[0]} {pending_launch[1]}"
        pending_launch = None
    else:
        speech = input("Say something: ")
    command = "continue"
    request_blocked = False
    if speech.startswith("+"):
        # +context, prompt to new context
        if len(speech) > 1:
            # update context, then prompt
            interactive_module_id = speech[1:].split(' ')[0]
            interactive_content_id = speech[1:].split(' ')[1]
            interactive_urgency = "normal"
            interactive_context_override = None
            command = "prompt"
        else:
            command = "reprompt"
        speech = ""
        last_user_speech = ""
        log_and_print(f"Requesting {command} for remote module: {interactive_module_id}, content_id={interactive_content_id}")
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
    elif speech.startswith("!"):
        # ![speech], ignored speech input
        if len(speech) > 1:
            request_blocked = True
            speech = speech[1:]
            log_only(f"(Ignored) User: {speech}")
            last_user_speech = ""
        else:
            log_and_print(f"Invalid, ! without speech following")
            return
    elif speech.startswith("="):
        # =[speech], accepted speech, ignored responses (user speech in multiple volleys)
        if len(speech) > 1:
            request_blocked = True
            speech = speech[1:]
            last_user_speech = speech
            log_only(f"(Interrupt) User: {last_user_speech}")
        else:
            log_and_print(f"Invalid, ! without speech following")
            return
    else:
        last_user_speech = speech
        log_only(f"User: {last_user_speech}")

    request_id = str(uuid.uuid4())
    if request_blocked:
        ignored_id = request_id
    mmsg = chat_remote_module_request(speech, session_uuid, session_auid,request_id, topic=topic_from_args(), 
        command=command, module_id=interactive_module_id, content_id=interactive_content_id, urgency=interactive_urgency, stream_response=args.stream)
    request_time = time.time()
    if interactive_prompt_override:
        mmsg["payload"]["prompt_context"] = { "text": interactive_prompt_override }
        interactive_prompt_override = None
        
    with rcv:
        log_and_publish(c, mmsg)
        if last_user_speech:
            mmsg = chat_notify_request('[animation:curious]', session_uuid, session_auid, seq, module_id=interactive_module_id, content_id=interactive_content_id, user_speech=last_user_speech, topic=topic_from_args(), source_event_id=request_id)
            log_and_publish(c, mmsg)
            log_and_print(f"Moxie: [animation:curious]")

        rcv.wait()

parser = argparse.ArgumentParser(description='Transcript or Interface Chat Test')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--in_file", dest="in_file", metavar="in_file", type=str, action="store", help="Transcript file to read, if not provided chat will be interactive")
parser.add_argument("--production", "--production", action="store_true", help="Use rc-production instead of rc-staging")
parser.add_argument("--nolog", "--nolog", action="store_true", help="Disable logging")
parser.add_argument("--tts", dest="tts", metavar="tts", type=str, action="store", help="Path to cereproc tts app")
parser.add_argument("--player", dest="wavplay", metavar="wavplay", type=str, action="store")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
parser.add_argument("--perplex", "--perplex", action="store_true", help="Log perplexity")
parser.add_argument("--stream", "--stream", action="store_true", help="Stream responses")
parser.add_argument("--time", "--time", action="store_true", help="Print response times")
parser.add_argument("--launch", "--launch", action="store_true", help="Automatically transition on launch commands")
args = parser.parse_args()

creds = RobotCredentials()
c = MoxieClient(creds, endpoint=args.iot) if args.iot else MoxieClient(creds)
c.add_connect_handler(on_connect)
c.add_config_handler(on_config)
c.add_command_handler("remote_chat", on_chat_response)
c.connect(start=True)

if not args.in_file:
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

    print("Connected to interactive chat.\n- Use +[module_id content_id] to prompt into a new conversation context, or + by itself to reprompt.\n- Use =[speech] to input accepted speech ignoring responses (self-interrupted speech)\n- Use ![speech] to post speech client won't accept.\n- Use -[urgency] to update the urgency\n- Use /[moxie speech] add moxie speech to history.\n- Type anything else to speak")
    make_session()
    while True:
        prompt_and_send()
else:
    # Transcript runner, we wait for our thread, then for it to complete
    while not runner_thread:
        time.sleep(0.5)
    runner_thread.join()

c.stop()
