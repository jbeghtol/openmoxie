import time

#GPT3_MODEL = "davincisafe"
#GPT3_MODEL = "curie"
GPT3_MODEL = "gpt-3.5-turbo"
#GPT3_MODEL = "davinci3"
#GPT3_MODEL = "chatgpt"

# Remote chat interface API version to use
API_VERSION=9

#DEFAULT_RUNNING_MODULE = "SUPERCHAT_FIRSTWEEK"
DEFAULT_RUNNING_MODULE = "AB"
DEFAULT_RUNNING_CONTENT = "bumblebee"

DEVICE_SETTINGS = {"props":{"group":"0","gpt3":GPT3_MODEL,"remote_transition":"1","debug":"1","rb_menu_topic":"moximusprime","context_key":"abcd","mp_max_volleys":"25"}}

# These modules will be restricted access (no launch)
RESTRICTED_MODULES = []
#RESTRICTED_MODULES = [ "OCEANEXPLORER" ]

CANNED_QUERY_REMOTE_CHAT_CONTEXTS = {
    "topic": "remote-chat-staging", 
    "payload": { "event_id": "test_query_uuid", "backend": "data", "api_version": API_VERSION, "query": { "query": "contexts" }, "allow_multiple": True }
}

CANNED_QUERY_REMOTE_CHAT_FOLLOWUPS = {
    "topic": "remote-chat-staging", 
    "payload": { "event_id": "test_query_uuid", "backend": "data", "api_version": API_VERSION, "query": { "query": "followups" }, "allow_multiple": True }
}

CANNED_QUERY_REMOTE_CHAT_MODULES = {
    "topic": "remote-chat-staging", 
    "payload": { "event_id": "test_query_uuid", "backend": "data", "api_version": API_VERSION, "query": { "query": "modules" }, "allow_multiple": True }
}

CANNED_QUERY_CONTEXT_INDEX = {
    "payload": { "subtopic": "query", "request_id": "test_query_uuid", "query": "contexts" }
}

CANNED_QUERY_LICENSES = {
    "payload": {"timestamp":"1678559110206","subtopic":"query","query":"license","request_id":"LicenseUpdate"}
}

CANNED_QUERY_SCHEDULE = {
    "payload": {"timestamp":"1678559110206","subtopic":"query","query":"schedule","api_version": 1, "schedule_id": "gen_opt_in", "request_id":"ScheduleTest"}
}

CANNED_QUERY_REMOTE_CHAT_NOTIFY = {
    "topic": "remote-chat-staging", 
    "payload": { "event_id": "test_query_uuid", "backend": "data", "api_version": API_VERSION, "query": { "query": "contexts" } }
}

CANNED_QUERY_MENTOR_BEHAVIORS = {
    "payload": {"subtopic":"query", "query": "mentor_behaviors","request_id": "MentorBehaviors"}
}

def now_ms():
    return round(time.time() * 1000)

def chat_notify_request(moxie_speech, session_id, user_id, sequence, topic="remote-chat-staging", user_speech="", api_version=API_VERSION,
    user_age=7, module_id=DEFAULT_RUNNING_MODULE, content_id=DEFAULT_RUNNING_CONTENT, chunk_ids=[], source_event_id=None
):
    extra = {"text":user_speech,"context_type":"input"} if user_speech else {"text": "eb-event","context_type":"event"}
    payload = {"timestamp": now_ms(), "command":"notify", "sequence":sequence,
        "extra_lines":[extra],
        "speech": moxie_speech,
        "backend":"router",
        "session_id": session_id,
        "api_version": api_version,
        "module_id": module_id,
        "content_id": content_id,
        "user_id": user_id,
        "user_age": user_age,
        "settings": DEVICE_SETTINGS,
        "software_version":"22.11.1900","module_name":"robotbrain"}
    if source_event_id:
        payload["source_event_id"] = source_event_id
    if chunk_ids:
        payload["response_chunks"] = chunk_ids
    return { "topic": topic, "payload": payload }

def chat_inference_request(
    user_speech, session_id, user_id, event_id, command="continue", topic="remote-chat-staging", api_version=API_VERSION, 
    user_age=7, module_id=DEFAULT_RUNNING_MODULE, conversation_context="self_low", urgency="normal", cc_override=None, 
    gpt3_override=None, setting_override=None, stream_response=False
):
    extra = {"text":user_speech,"context_type":"input"} if user_speech else {"text": "eb-event","context_type":"event"}
    payload = {"timestamp": now_ms(), "command": command, "event_id":event_id,
        "extra_lines":[extra],
        "speech": user_speech,
        "backend":"router",
        "session_id": session_id,
        "api_version": api_version,
        "module_id": module_id,
        "content_id": "fallback",
        "user_id": user_id,
        "user_age": user_age,
        "settings": setting_override if setting_override else DEVICE_SETTINGS,
        "recommend": {
            "urgency": urgency,
            "exits": [
            {
                "module_id": "ENROLLCONVO",
                "module_name": "something to do together!",
            }
            ],
            "restricted_modules": RESTRICTED_MODULES
        },
        "stream_response": stream_response,
        "allow_multiple": True,
        "conversation_context": {
            "id": conversation_context
        },
        "software_version":"22.11.1900","module_name":"robotbrain"}
    if cc_override:
        payload["conversation_context"]["text"] = cc_override
        payload["context"] = cc_override
    if gpt3_override and not setting_override:
        payload["settings"]["props"]["gpt3"] = gpt3_override
 
    return { "topic": topic, "payload": payload }

def chat_remote_module_request(
    user_speech, session_id, user_id, event_id, command="continue", topic="remote-chat-staging", api_version=API_VERSION,
    user_age=7, module_id=DEFAULT_RUNNING_MODULE, urgency="normal", content_id=DEFAULT_RUNNING_CONTENT, gpt3_override=None, 
    setting_override=None, stream_response=False
):
    extra = {"text":user_speech,"context_type":"input"} if user_speech else {"text": "eb-event","context_type":"event"}
    payload = {"timestamp": now_ms(), "command": command, "event_id":event_id,
        "extra_lines":[extra],
        "speech": user_speech,
        "backend":"router",
        "session_id": session_id,
        "api_version": api_version,
        "module_id": module_id,
        "content_id": content_id,
        "user_id": user_id,
        "user_age": user_age,
        "settings": setting_override if setting_override else DEVICE_SETTINGS,
        "recommend": {
            "urgency": urgency,
            "exits": [
            {
                "module_id": "ENROLLCONVO",
                "module_name": "something to do together!",
            }
            ],
            "restricted_modules": RESTRICTED_MODULES
        },
        "allow_multiple": True,
        "no_llm": False,
        "stream_response": stream_response,
        "software_version":"22.11.1900","module_name":"robotbrain"}
    if gpt3_override and not setting_override:
        payload["settings"]["props"]["gpt3"] = gpt3_override
 
    return { "topic": topic, "payload": payload }

def chat_remote_simple_request(
    user_speech, session_id, user_id, event_id, command="continue", topic="remote-chat-staging", api_version=API_VERSION,
    user_age=7, module_id=DEFAULT_RUNNING_MODULE, urgency="normal", content_id=DEFAULT_RUNNING_CONTENT, gpt3_override=None, 
    setting_override=None, stream_response=False
):
    extra = {"text":user_speech,"context_type":"input"} if user_speech else {"text": "eb-event","context_type":"event"}
    payload = {"timestamp": now_ms(), "command": command, "event_id":event_id,
        # "extra_lines":[extra],
        "speech": user_speech,
        "backend":"newo",
        "session_id": session_id,
        "api_version": api_version,
        # "module_id": module_id,
        # "content_id": content_id,
        "user_id": user_id,
        "user_age": user_age,
        "settings": {
            "props": {
                "actor_name": "Justin",
                "lm_timeout": 120
            }
        },
        # "recommend": {
        #     "urgency": urgency,
        #     "exits": [
        #     {
        #         "module_id": "ENROLLCONVO",
        #         "module_name": "something to do together!",
        #     }
        #     ],
        #     "restricted_modules": RESTRICTED_MODULES
        # },
        # "allow_multiple": True,
        # "stream_response": stream_response,
        "software_version":"22.11.1900","module_name":"robotbrain"}
    if gpt3_override and not setting_override:
        payload["settings"]["props"]["gpt3"] = gpt3_override
 
    return { "topic": topic, "payload": payload }

def chat_autotag_request(input_speech, session_id, user_id, event_id, topic="remote-chat-staging", api_version=API_VERSION, user_age=7, module_id=DEFAULT_RUNNING_MODULE):
    payload = {"timestamp": now_ms(), "event_id":event_id,
        "speech": input_speech,
        "backend":"autotag",
        "session_id": session_id,
        "api_version": api_version,
        "module_id": module_id,
        "user_id": user_id,
        "user_age": user_age,
        "settings": DEVICE_SETTINGS,
        "software_version":"22.11.1900","module_name":"robotbrain"}
    return { "topic": topic, "payload": payload }

def chat_memory_request(session_id, user_id, event_id, topic="remote-chat-staging", api_version=API_VERSION, user_age=7):
    payload = {"timestamp": now_ms(), "event_id":event_id,
        "backend":"memory",
        "session_id": session_id,
        "api_version": api_version,
        "user_id": user_id,
        "user_age": user_age,
        "settings": DEVICE_SETTINGS,
        "software_version":"22.11.1900","module_name":"robotbrain"}
    return { "topic": topic, "payload": payload }

def chat_raw_request(user_speech, session_id, user_id, event_id, topic="remote-chat-staging", api_version=API_VERSION, user_age=7, gpt3_override=None,  setting_override=None):
    payload = {"timestamp": now_ms(), "event_id":event_id,
        "backend":"raw",
        "speech": user_speech,
        "session_id": session_id,
        "api_version": api_version,
        "user_id": user_id,
        "user_age": user_age,
        "settings": setting_override if setting_override else DEVICE_SETTINGS,
        "software_version":"22.11.1900","module_name":"robotbrain"}

    if gpt3_override and not setting_override:
        payload["settings"]["props"]["gpt3"] = gpt3_override

    return { "topic": topic, "payload": payload }

