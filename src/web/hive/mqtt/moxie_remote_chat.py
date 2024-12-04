from openai import OpenAI
import copy
import concurrent.futures

class ChatSession:
    def __init__(self, max_turns=20):
        self._history = []
        self._max_turns = max_turns

    def add_history(self, role, message, history=None):
        history = self._history if not history else history
        if history and history[-1].get("role") == role:
            # same role, append text
            history[-1]["content"] =  history[-1].get("content", '') + ' ' + message
        else:
            history.append({ "role": role, "content": message })
            if len(history) > self._max_turns:
                history = history[-self._max_turns:]

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
        return f"chat history {len(self._history)}"


class SingleContextChatSession(ChatSession):
    def __init__(self, max_turns=20):
        super().__init__(max_turns)        
        self._context = [ { "role": "system", 
            "content": "You are a having a conversation with your friend. Make it interesting and keep the conversation moving forward. Your utterances are around 30-40 words long. Ask only one question per response and ask it at the end of your response."
            } ]

    def next_response(self, speech):
        # clone, add new input, official history comes from notify
        history = copy.deepcopy(self._history)
        self.add_history('user', speech, history)
        client = OpenAI()
        return client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=self._context + history,
                    max_tokens=70,
                    temperature=0.5
                ).choices[0].message.content

    def get_prompt(self):
        return super().get_prompt(msg='Hi there!  Welcome to Open Moxie chat!')


class RemoteChat:
    def __init__(self, server):
        self._server = server
        self._device_sessions = {}
        self._modules = { }
        self.register_module('OPENMOXIE_CHAT', 'default', SingleContextChatSession)
        self._worker_queue = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    def register_module(self, module_id, content_id, cname):
        self._modules[f'{module_id}/{content_id}'] = cname

    def get_session(self, device_id, id, cname):
        # each device has a single session only for now
        if device_id in self._device_sessions:
            if self._device_sessions[device_id]['id'] == id:
                return self._device_sessions[device_id]['session']
        print("New session")
        # new session needed
        new_session = { 'id': id, 'session': cname() }
        self._device_sessions[device_id] = new_session
        return new_session['session']

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
                
    def next_session_response(self, device_id, sess, speech, resp):
        resp['output']['markup'] = sess.next_response(speech)
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
                self._worker_queue.submit(self.next_session_response, device_id, sess, rcr["speech"], self.make_response(rcr))
        elif device_id in self._device_sessions:
            del self._device_sessions[device_id]
            print(f'Ignoring request for other module: {rcr.get("module_id")} (Cleared session)')
        else:
            print(f'Ignoring request for other module: {rcr.get("module_id")}')

