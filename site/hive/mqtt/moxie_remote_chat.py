from openai import OpenAI
import copy
import concurrent.futures
from ..models import SinglePromptChat
from ..automarkup import process as automarkup_process
from ..automarkup import initialize_rules as automarkup_initialize_rules

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
        print(f"Notify session")
        # RULES - speech field is what 'assistant' said, but we should skip the [animation]
        # 'user' speech comes from extra_lines[].text when .context_type=='input'
        for line in rcr.get('extra_lines', []):
            if line['context_type'] == 'input':
                self.add_history('user', line['text'])
        speech = rcr.get('speech')
        if speech and 'animation:' not in speech:
            self.add_history('assistant', speech)

    def next_response(self, speech):
        print(f'Inference using history:\n{self._history}')
        return f"chat history {len(self._history)}", None


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

    def set_auto_history(self, val):
        self._auto_history = val
    
    def overflow(self):
        return self._total_volleys >= self._max_volleys
    
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
        client = OpenAI()
        resp = client.chat.completions.create(
                    model=self._model,
                    messages=self._context + history,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature
                ).choices[0].message.content
        if of:
            resp += " " + self._exit_line
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp, of
        
    def get_prompt(self):
        resp = super().get_prompt(msg=self._opener)
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp

class SinglePromptDBChatSession(SingleContextChatSession):
    def __init__(self, pk):
        source = SinglePromptChat.objects.get(pk=pk)
        super().__init__(max_history=source.max_history, max_volleys=source.max_volleys, prompt=source.prompt, opener=source.opener, max_tokens=source.max_tokens, temperature=source.temperature)

class RemoteChat:
    def __init__(self, server):
        self._server = server
        self._device_sessions = {}
        self._modules = { }
        self._modules_info = { "modules": [], "version": "openmoxie_v1" }
        self._worker_queue = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self._automarkup_rules = automarkup_initialize_rules()
        self.update_from_database()

    def register_module(self, module_id, content_id, cname):
        self._modules[f'{module_id}/{content_id}'] = cname

    def get_modules_info(self):
        return self._modules_info
    
    def update_from_database(self):
        # Here we query the database to get all the module/content IDs and update the modules schema and register the modules
        new_modules = {}
        mod_map = {}
        for chat in SinglePromptChat.objects.all():
            new_modules[f'{chat.module_id}/{chat.content_id}'] = { 'xtor': SinglePromptDBChatSession, 'params': { 'pk': chat.pk } }
            print(f'Registering {chat.module_id}')
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
    
    def get_session(self, device_id, id, maker):
        # each device has a single session only for now
        if device_id in self._device_sessions:
            if self._device_sessions[device_id]['id'] == id:
                return self._device_sessions[device_id]['session']
        print("New session")
        # new session needed
        new_session = { 'id': id, 'session': maker['xtor'](**maker['params']) }
        self._device_sessions[device_id] = new_session
        return new_session['session']

    def get_web_session_for_module(self, device_id, module_id, content_id):
        id = module_id + '/' + content_id
        maker = self._modules.get(id)
        return self.get_session(device_id, id, maker) if maker else None

    def make_response(self, rcr, res=0):
        resp = { 
            'command': 'remote_chat',
            'result': res,
            'backend': rcr['backend'],
            'event_id': rcr['event_id'],
            'output': { },
            'response_actions': [
                {
                    'output_type': 'GLOBAL_RESPONSE'
                }
            ],
            'fallback': False,
            'response_action': {
                'output_type': 'GLOBAL_RESPONSE'
            }
        }

        if 'speech' in rcr:
            resp['input_speech'] = rcr['speech']
        return resp
                
    def make_markup(self, text):
        return automarkup_process(text, self._automarkup_rules)

    def next_session_response(self, device_id, sess, rcr, resp):
        speech = rcr["speech"]
        text,overflow = sess.next_response(speech)
        resp['output']['text'] = text
        resp['output']['markup'] = self.make_markup(text)
        if overflow:
            action = { 'action': 'exit_module', 'output_type': 'GLOBAL_RESPONSE' }
            resp['response_actions'][0] = action
            resp['response_action'] = action
        self._server.send_command_to_bot_json(device_id, 'remote_chat', resp)
        
    def handle_request(self, device_id, rcr):
        id = rcr.get('module_id', '') + '/' + rcr.get('content_id', '')
        maker = self._modules.get(id)
        if maker:
            print(f'Handling RCR for OPENMOXIE') 
            sess = self.get_session(device_id, id, maker)
            cmd = rcr.get('command')
            if cmd == 'notify':
                sess.ingest_notify(rcr)
            elif cmd == "prompt":
                resp = self.make_response(rcr)
                resp['output']['markup'] = sess.get_prompt()
                self._server.send_command_to_bot_json(device_id, 'remote_chat', resp)
            else:
                self._worker_queue.submit(self.next_session_response, device_id, sess, rcr, self.make_response(rcr))
        elif device_id in self._device_sessions:
            del self._device_sessions[device_id]
            print(f'Ignoring request for other module: {rcr.get("module_id")} (Cleared session)')
        else:
            print(f'Ignoring request for other module: {rcr.get("module_id")}')

