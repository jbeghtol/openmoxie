'''
MOXIE REMOTE CHAT - Handle Remote Chat protocol messages from Moxie

Remote Chat (RemoteChatRequest/Response) messages make up the bulk of the remote module
interface for Moxie.  Module/Content IDs that are remote, send inputs and get outputs
using these messages.

Moxie Remote Chat uses a "notify" tracking approach for context, meaning that Moxie notifies
the remote service everytime it says something.  This data is used to accumulate the true
history of the conversation and provides mostly seemless conversation context for the AI,
even when the user provides input in multiple speech windows before hearing a response.
'''
import traceback
from openai import OpenAI
import copy
import random
import re
import concurrent.futures
from django.template import Template, Context
from .ai_factory import create_openai
from ..models import SinglePromptChat
from ..automarkup import process as automarkup_process
from ..automarkup import initialize_rules as automarkup_initialize_rules
import logging
from datetime import datetime
from .global_responses import GlobalResponses
from .rchat import make_response,add_launch_or_exit,debug_response_string
from .volley import Volley

# Turn on to enable global commands in the cloud
_ENABLE_GLOBAL_COMMANDS = True
_LOG_ALL_RCR = False
_MAX_WORKER_THREADS = 5

logger = logging.getLogger(__name__)

'''
Base type of a module that has a chat session interaction on Moxie.  It
manages the history, rotating out records to keep tokens more lean.
'''
class ChatSession:
    def __init__(self, max_history=20):
        self._history = []
        self._max_history = max_history
        self._total_volleys = 0
        self._local_data = {}

    def add_history(self, role, message, history=None):
        if not history:
            history = self._history
            self._total_volleys += 1
        if history and history[-1].get("role") == role:
            # same role, append text
            history[-1]["content"] =  history[-1].get("content", '') + ' ' + message
        else:
            history.append({ "role": role, "content": message })
            if len(history) > self._max_history:
                history = history[-self._max_history:]

    def is_empty(self):
        return len(self._history) == 0
    
    def reset(self):
        self._history = []
        
    @property
    def local_data(self):
        return self._local_data
    
    def get_opener(self, msg='Welcome to open chat'):
        self.reset()
        return msg,self.overflow()

    def ingest_notify(self, rcr):
        # RULES - speech field is what 'assistant' said, but we should skip the [animation]
        # 'user' speech comes from extra_lines[].text when .context_type=='input'
        for line in rcr.get('extra_lines', []):
            if line['context_type'] == 'input':
                self.add_history('user', line['text'])
        speech = rcr.get('speech')
        if speech and 'animation:' not in speech:
            self.add_history('assistant', speech)

    def next_response(self, speech, context):
        logger.debug(f'Inference using history:\n{self._history}')
        return f"chat history {len(self._history)}", None

    def overflow(self):
        return False
    
    def handle_volley(self, volley:Volley):
        pass

'''
Our simple Single Prompt conversation.  It uses the ChatSession to manage the history
of the conversation and focuses on keeping the conversation within volley limits and
make inferences to OpenAI.
'''
class SingleContextChatSession(ChatSession):
    def __init__(self, 
                 max_history=20, 
                 max_volleys=9999,
                 prompt="You are a having a conversation with your friend. Make it interesting and keep the conversation moving forward. Your utterances are around 30-40 words long. Ask only one question per response and ask it at the end of your response.",
                 opener="Hi there!  Welcome to Open Moxie chat!",
                 model="gpt-3.5-turbo",
                 max_tokens=70,
                 temperature=0.5,
                 exit_line="Well, that was fun.  Let's move on."
                 ):
        super().__init__(max_history)
        self._max_volleys = max_volleys        
        self._context = [ { "role": "system", 
            "content": prompt
            } ]
        self._opener = opener
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._exit_line = exit_line
        self._auto_history = False
        self._exit_requested = False
        self._pre_filter = None
        self._post_filter = None
        self._prompt_template = Template(prompt)

    def set_filters(self, pre_filter=None, post_filter=None):
        self._pre_filter = pre_filter
        self._post_filter = post_filter

    # For web-based, we have no Moxie and no Notify channel, so auto-history is used
    def set_auto_history(self, val):
        self._auto_history = val
    
    # Check if we exceed max volleys for a conversation
    def overflow(self):
        return self._total_volleys >= self._max_volleys or self._exit_requested
    
    # Render an updated prompt context for this volley
    def make_volley_context(self, volley:Volley):
        return [ { "role": "system", 
                    "content": self._prompt_template.render(Context({'volley': volley}))
                    } ]
    
    # Handle a volley, using its request and populating the response
    def handle_volley(self, volley:Volley):
        volley.assign_local_data(self._local_data)
        try:
            # preprocess, if filter returns True, we are done
            if self._pre_filter:
                logger.debug("Running volley pre-filter")
                if self._pre_filter(volley, self):
                    return
            
            # Handle prompt vs next response
            cmd = volley.request.get('command')
            if cmd == "prompt" or (cmd == "reprompt" and self.is_empty()):
                text,overflow = self.get_opener()
            else:
                speech = "hm" if volley.request.get("command")=="reprompt" else volley.request["speech"]
                text,overflow = self.next_response(speech, self.make_volley_context(volley))
            volley.set_output(text, None)
            if overflow:
                volley.add_launch_or_exit()
            # postprocess the volley
            if self._post_filter:
                logger.debug("Running volley post-filter")
                self._post_filter(volley, self)
        except Exception as e:
            #stack = traceback.format_exc()
            err_text = f"Error handling volley: {e}"
            logger.error(err_text)
            volley.create_response() # flush any pre-exception response changes
            volley.set_output(err_text,err_text)

    # Get the next thing we should say, given the user speech and the history
    def next_response(self, speech, context):
        of = self.overflow()
        if self._auto_history:
            # accumulating automatically, no interruptions or aborts
            self.add_history('user', speech)
            history = self._history
        else:
            # clone, add new input, official history comes from notify
            history = copy.deepcopy(self._history)
            self.add_history('user', speech, history)
        try:
            client = create_openai()
            resp = client.chat.completions.create(
                        model=self._model,
                        messages=context + history,
                        max_tokens=self._max_tokens,
                        temperature=self._temperature
                    ).choices[0].message.content
            # detect <exit> request from AI
            self._exit_requested = self._exit_requested or '<exit>' in resp
            if self._exit_requested:
                logger.info("Exit tag detected in response.")
                of = True
            # remove any random xml like tags
            resp = re.sub(r'<.*?>', '', resp)
        except Exception as e:
            logger.warning(f'Exception attempting inference: {e}')
            resp = "Oh no.  I have run into a bug"
        if of:
            resp += " " + self._exit_line
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp, of
    
    # Prompt in this case is an opener line to say when we start the conversation module
    def get_opener(self):
        # Supports multiple random prompts separated by |, pick a random one
        opener = random.choice(self._opener.split('|'))
        resp,overflow = super().get_opener(msg=opener)
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp,overflow

# A database backed version, the way we normally load them
class SinglePromptDBChatSession(SingleContextChatSession):
    def __init__(self, pk):
        source = SinglePromptChat.objects.get(pk=pk)
        super().__init__(max_history=source.max_history, max_volleys=source.max_volleys, model=source.model, prompt=source.prompt, opener=source.opener, max_tokens=source.max_tokens, temperature=source.temperature)
        if source.code:
            try:
                loc = locals()
                exec(source.code, globals(), loc)
                self.set_filters(pre_filter=loc.get('pre_process'), post_filter=loc.get('post_process'))
            except Exception as e:
                logger.error(f"Error loading code for chat session: {e}")

'''
RemoteChat is the plugin to the MoxieServer that handles all remote module requests.  It
keeps track of the active remote module, creates new ones as needed, and ignores all data
from local modules.  It also manages auto-markup, which renders plaintext into a markup
language with animated gestures.
'''
class RemoteChat:
    _global_responses: GlobalResponses
    def __init__(self, server):
        self._server = server
        self._device_sessions = {}
        self._modules = { }
        self._modules_info = { "modules": [], "version": "openmoxie_v1" }
        self._worker_queue = concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKER_THREADS)
        self._automarkup_rules = automarkup_initialize_rules()
        self._global_responses = GlobalResponses()

    def register_module(self, module_id, content_id, cname):
        self._modules[f'{module_id}/{content_id}'] = cname

    # Gets the remote module info record to share remote modules with Moxie
    def get_modules_info(self):
        return self._modules_info
    
    # Update database backed records.  Query to get all the module/content IDs and update the modules schema and register the modules
    def update_from_database(self):
        new_modules = {}
        mod_map = {}
        for chat in SinglePromptChat.objects.all():
            # one module can support many content IDs, separated by | like openers
            cid_list = chat.content_id.split('|')
            for content_id in cid_list:
                new_modules[f'{chat.module_id}/{content_id}'] = { 'xtor': SinglePromptDBChatSession, 'params': { 'pk': chat.pk } }
                logger.debug(f'Registering {chat.module_id}/{content_id}')
                # Group content IDs under module IDs
                if chat.module_id in mod_map:
                    mod_map[chat.module_id].append(content_id)
                else:
                    mod_map[chat.module_id] = [ content_id ]
        # Models/content IDs into the module info schema - bare bones mandatory fields only
        mlist = []
        for mod in mod_map.keys():
            modinfo = { "info": { "id": mod }, "rules": "RANDOM", "source": "REMOTE_CHAT", "content_infos": [] }
            for cid in mod_map[mod]:
                modinfo["content_infos"].append({ "info": { "id": cid } })
            mlist.append(modinfo)
        self._modules_info["modules"] = mlist
        self._modules = new_modules
        self._global_responses.update_from_database()
    
    # Handle GLOBAL patterns, available inside (almost) any module
    def check_global(self, volley):
        return self._global_responses.check_global(volley) if _ENABLE_GLOBAL_COMMANDS else None
        
    def on_chat_complete(self, device_id, id, session):
        logger.info(f'Chat Session Complete: {id}')

    # Get the current or a new session for this device for this module/content ID pair
    def active_session_data(self, device_id):
        if device_id in self._device_sessions:
            return self._device_sessions[device_id]['session'].local_data
        return None
            
    # Get the current or a new session for this device for this module/content ID pair
    def get_session(self, device_id, id, maker) -> ChatSession:
        # each device has a single session only for now
        if device_id in self._device_sessions:
            if self._device_sessions[device_id]['id'] == id:
                return self._device_sessions[device_id]['session']
            else:
                self.on_chat_complete(device_id, id, self._device_sessions[device_id]['session'])

        # new session needed
        new_session = { 'id': id, 'session': maker['xtor'](**maker['params']) }
        self._device_sessions[device_id] = new_session
        return new_session['session']

    # Get's a chat session object for use in the web chat
    def get_web_session_for_module(self, device_id, module_id, content_id):
        id = module_id + '/' + content_id
        maker = self._modules.get(id)
        return self.get_session(device_id, id, maker) if maker else None

    def get_web_session_global_response(self, volley):
        #volley = Volley({ "speech": speech, "backend": "router", "event_id": "fake" })
        global_functor = self.check_global(volley)
        if global_functor:
            resp = global_functor()
            if isinstance(resp, str):
                return resp
            else:
                return debug_response_string(resp)
        return None

    # Markup text      
    def make_markup(self, text, mood_and_intensity = None):
        return automarkup_process(text, self._automarkup_rules, mood_and_intensity=mood_and_intensity)

    # Get the next response to a chat
    def create_session_response(self, device_id, sess:ChatSession, volley: Volley):
        sess.handle_volley(volley)
        if 'markup' not in volley.response['output']:
            # if we don't have markup, create it
            text = volley.response['output']['text']
            volley.set_output(text, self.make_markup(text))

        if _LOG_ALL_RCR:
            logger.info(f"RemoteChatResponse\n{volley.response}")
        self._server.send_command_to_bot_json(device_id, 'remote_chat', volley.response)
    
    # Produce / execute a global response
    def global_response(self, device_id, functor):
        resp = functor()
        output = resp.get('output')
        if output.get('text') and not output.get('markup'):
            # Run automarkup on any text-only responses
            output['markup'] = self.make_markup(output['text'])
        self._server.send_command_to_bot_json(device_id, 'remote_chat', resp)
        pass

    # Entry point where all RemoteChatRequests arrive
    def handle_request(self, device_id, rcr, volley_data):
        if _LOG_ALL_RCR:
            logger.info(f"RemoteChatRequest\n{rcr}")
        id = rcr.get('module_id', '') + '/' + rcr.get('content_id', '')
        cmd = rcr.get('command')

        # Create volley if needed
        #volley = Volley(rcr, robot_data=volley_data, local_data=self.active_session_data(device_id)) if cmd != 'notify' else None

        # check any global commands, and use their responses over anything else
        # global_functor = self.check_global(volley) if volley else None
        # if global_functor:
        #     logger.debug(f'Global response inside {id}')
        #     self._worker_queue.submit(self.global_response, device_id, global_functor)
        #     return

        maker = self._modules.get(id)
        if maker:
            # THIS IS THE PATH FOR REMOTE CONTENT - MODULE/CONTENT HOSTED IN OPENMOXIE
            logger.debug(f'Handling RCR:{cmd} for {id}') 
            sess = self.get_session(device_id, id, maker)
            if cmd == 'notify':
                sess.ingest_notify(rcr)
            else:
                volley = Volley(rcr, robot_data=volley_data, local_data=sess.local_data)
                if not self.handled_global(device_id, volley):
                    self._worker_queue.submit(self.create_session_response, device_id, sess, volley)
        else:
            # THIS IS THE PATH FOR MOXIE ON-BOARD CONTENT
            session_reset = False
            if device_id in self._device_sessions:
                session = self._device_sessions.pop(device_id, None)
                self.on_chat_complete(device_id, id, session)
                session_reset = True
            if cmd != 'notify':
                volley = Volley(rcr, robot_data=volley_data)
                if not self.handled_global(device_id, volley):
                    logger.debug(f'Ignoring request for other module: {id} SessionReset:{session_reset}')
                    # Rather than ignoring these, we return a generic FALLBACK response
                    fbline = "I'm sorry. Can  you repeat that?"
                    volley.set_output(fbline, fbline, output_type='FALLBACK')
                    self._server.send_command_to_bot_json(device_id, 'remote_chat', volley.response)
    
    def handled_global(self, device_id, volley):
        global_functor = self.check_global(volley)
        if global_functor:
            logger.debug(f'Global response inside {id}')
            self._worker_queue.submit(self.global_response, device_id, global_functor)
            return True
        return False
