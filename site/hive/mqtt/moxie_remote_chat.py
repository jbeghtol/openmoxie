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
from openai import OpenAI
import copy
import random
import concurrent.futures
from .ai_factory import create_openai
from ..models import SinglePromptChat
from ..automarkup import process as automarkup_process
from ..automarkup import initialize_rules as automarkup_initialize_rules
import logging
from datetime import datetime

# Turn on to enable global commands in the cloud
_DEMO_GLOBAL_COMMANDS = False

def get_current_time():
    now = datetime.now()
    current_time = now.strftime("The time is %I %M %p")
    return current_time

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

    def reset(self):
        self._history = []
        
    def get_prompt(self, msg='Welcome to open chat'):
        self.reset()
        return msg

    def ingest_notify(self, rcr):
        # RULES - speech field is what 'assistant' said, but we should skip the [animation]
        # 'user' speech comes from extra_lines[].text when .context_type=='input'
        for line in rcr.get('extra_lines', []):
            if line['context_type'] == 'input':
                self.add_history('user', line['text'])
        speech = rcr.get('speech')
        if speech and 'animation:' not in speech:
            self.add_history('assistant', speech)

    def next_response(self, speech):
        logger.debug(f'Inference using history:\n{self._history}')
        return f"chat history {len(self._history)}", None

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

    # For web-based, we have no Moxie and no Notify channel, so auto-history is used
    def set_auto_history(self, val):
        self._auto_history = val
    
    # Check if we exceed max volleys for a conversation
    def overflow(self):
        return self._total_volleys >= self._max_volleys
    
    # Get the next thing we should say, given the user speech and the history
    def next_response(self, speech):
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
                        messages=self._context + history,
                        max_tokens=self._max_tokens,
                        temperature=self._temperature
                    ).choices[0].message.content
        except Exception as e:
            logger.warning(f'Exception attempting inference: {e}')
            resp = "Oh no.  I have run into a bug"
        if of:
            resp += " " + self._exit_line
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp, of
    
    # Prompt in this case is an opener line to say when we start the conversation module
    def get_prompt(self):
        # Supports multiple random prompts separated by |, pick a random one
        opener = random.choice(self._opener.split('|'))
        resp = super().get_prompt(msg=opener)
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp

# A database backed version, the way we normally load them
class SinglePromptDBChatSession(SingleContextChatSession):
    def __init__(self, pk):
        source = SinglePromptChat.objects.get(pk=pk)
        super().__init__(max_history=source.max_history, max_volleys=source.max_volleys, prompt=source.prompt, opener=source.opener, max_tokens=source.max_tokens, temperature=source.temperature)

'''
RemoteChat is the plugin to the MoxieServer that handles all remote module requests.  It
keeps track of the active remote module, creates new ones as needed, and ignores all data
from local modules.  It also manages auto-markup, which renders plaintext into a markup
language with animated gestures.
'''
class RemoteChat:
    def __init__(self, server):
        self._server = server
        self._device_sessions = {}
        self._modules = { }
        self._modules_info = { "modules": [], "version": "openmoxie_v1" }
        self._worker_queue = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self._automarkup_rules = automarkup_initialize_rules()

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
            new_modules[f'{chat.module_id}/{chat.content_id}'] = { 'xtor': SinglePromptDBChatSession, 'params': { 'pk': chat.pk } }
            logger.debug(f'Registering {chat.module_id}/{chat.content_id}')
            # Group content IDs under module IDs
            if chat.module_id in mod_map:
                mod_map[chat.module_id].append(chat.content_id)
            else:
                mod_map[chat.module_id] = [ chat.content_id ]
        # Models/content IDs into the module info schema - bare bones mandatory fields only
        mlist = []
        for mod in mod_map.keys():
            modinfo = { "info": { "id": mod }, "rules": "RANDOM", "source": "REMOTE_CHAT", "content_infos": [] }
            for cid in mod_map[mod]:
                modinfo["content_infos"].append({ "info": { "id": cid } })
            mlist.append(modinfo)
        self._modules_info["modules"] = mlist
        self._modules = new_modules
    
    # For code-demonstration purposes.  These are global speech phrases that take priority over both
    # remote chat responses AND local responses on the robot.  If enabled, these should work almost
    # everywhere when robot is in session.  We use GLOBAL_COMMAND output type, which is the highest.
    def check_global(self, rcr):
        if not _DEMO_GLOBAL_COMMANDS:
            return None
        
        if rcr["speech"]:
            if rcr["speech"].lower() == "time":
                # Play the time if the user says only 'time'
                resp = self.make_response(rcr, output_type='GLOBAL_COMMAND')
                resp['output']['text'] = get_current_time()
                resp['output']['markup'] = self.make_markup(resp['output']['text'])
                return resp
            if rcr["speech"].lower() == "short":
                # Launch into the short chat if user says only 'short'
                resp = self.make_response(rcr, output_type='GLOBAL_COMMAND')
                resp['output']['text'] = "You like short?"
                resp['output']['markup'] = self.make_markup(resp['output']['text'])
                self.add_response_action(resp, "launch", output_type='GLOBAL_COMMAND', module_id='OPENMOXIE_CHAT', content_id="short")
                return resp
            if rcr["speech"].lower() == "confirm":
                # Launch into the short chat if user says only 'confirm' and then agrees
                resp = self.make_response(rcr, output_type='GLOBAL_COMMAND')
                resp['output']['text'] = "You like short?" # Line won't play
                self.add_response_action(resp, "launch_if_confirmed", output_type='GLOBAL_COMMAND', module_id='OPENMOXIE_CHAT', content_id="short")
                return resp
        return None

    # Get the current or a new session for this device for this module/content ID pair
    def get_session(self, device_id, id, maker):
        # each device has a single session only for now
        if device_id in self._device_sessions:
            if self._device_sessions[device_id]['id'] == id:
                return self._device_sessions[device_id]['session']

        # new session needed
        new_session = { 'id': id, 'session': maker['xtor'](**maker['params']) }
        self._device_sessions[device_id] = new_session
        return new_session['session']

    # Get's a chat session object for use in the web chat
    def get_web_session_for_module(self, device_id, module_id, content_id):
        id = module_id + '/' + content_id
        maker = self._modules.get(id)
        return self.get_session(device_id, id, maker) if maker else None

    # Create a generic base response object matching a request object
    def make_response(self, rcr, res=0, output_type='GLOBAL_RESPONSE'):
        resp = { 
            'command': 'remote_chat',
            'result': res,
            'backend': rcr['backend'],
            'event_id': rcr['event_id'],
            'output': { },
            'response_actions': [
                {
                    'output_type': output_type
                }
            ],
            'fallback': False,
            'response_action': {
                'output_type': output_type
            }
        }

        if 'speech' in rcr:
            resp['input_speech'] = rcr['speech']
        return resp

    # Markup text      
    def make_markup(self, text):
        return automarkup_process(text, self._automarkup_rules)

    # Add a named response action to a response, with optional params
    def add_response_action(self, resp, action_name, module_id=None, content_id=None, output_type='GLOBAL_RESPONSE'):
        action = { 'action': action_name, 'output_type': output_type }
        if module_id:
            action['module_id'] = module_id
        if content_id:
            action['content_id'] = content_id
        resp['response_actions'] = [ action ]
        resp['response_action'] = action

    # Get the next response to a chat
    def next_session_response(self, device_id, sess, rcr, resp):
        speech = rcr["speech"]
        text,overflow = sess.next_response(speech)
        resp['output']['text'] = text
        resp['output']['markup'] = self.make_markup(text)
        if overflow:
            self.add_response_action(resp, 'exit_module')
        self._server.send_command_to_bot_json(device_id, 'remote_chat', resp)
    
    # Entry point where all RemoteChatRequests arrive
    def handle_request(self, device_id, rcr):
        id = rcr.get('module_id', '') + '/' + rcr.get('content_id', '')
        cmd = rcr.get('command')
        # check any global commands, and use their responses over anything else
        global_response = self.check_global(rcr)
        if global_response:
            logger.debug(f'Global response inside {id}') 
            self._server.send_command_to_bot_json(device_id, 'remote_chat', global_response)
            return
        maker = self._modules.get(id)
        if maker:
            logger.debug(f'Handling RCR:{cmd} for {id}') 
            sess = self.get_session(device_id, id, maker)
            if cmd == 'notify':
                sess.ingest_notify(rcr)
            elif cmd == "prompt":
                resp = self.make_response(rcr)
                resp['output']['markup'] = sess.get_prompt()
                # Special for prompt-only one-line modules, exit on prompt if max_len=0
                if sess.overflow():
                    self.add_response_action(resp, 'exit_module')
                self._server.send_command_to_bot_json(device_id, 'remote_chat', resp)
            else:
                self._worker_queue.submit(self.next_session_response, device_id, sess, rcr, self.make_response(rcr))
        else:
            session_reset = False
            if device_id in self._device_sessions:
                del self._device_sessions[device_id]
                session_reset = True
            if cmd != 'notify':
                logger.debug(f'Ignoring request for other module: {id} SessionReset:{session_reset}')
                # Rather than ignoring these, we return a generic FALLBACK response
                resp = self.make_response(rcr, output_type='FALLBACK')
                resp['output']['text'] = resp['output']['markup'] = "I'm sorry. Can  you repeat that?"
                self._server.send_command_to_bot_json(device_id, 'remote_chat', resp)

