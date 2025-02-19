import logging
import uuid

logger = logging.getLogger(__name__)

class Volley:
    _request : dict
    _response : dict
    _local_data : dict
    _robot_data: dict

    def __init__(self, request, result=0, output_type='GLOBAL_RESPONSE', robot_data=None, local_data=None):
        self._request = request
        self.create_response(res=result, output_type=output_type)
        self._local_data = local_data if local_data != None else {}
        self._robot_data = robot_data if robot_data != None else {}

    @staticmethod
    def request_from_speech(speech, module_id=None, content_id=None, local_data=None):
        if speech:
            request = { 'event_id': str(uuid.uuid4()), 'command': 'continue', 'speech': speech, 'backend': 'router' }
        else:
            request = { 'event_id': str(uuid.uuid4()), 'command': 'prompt',  'backend': 'router' }
        if module_id: request['module_id'] = module_id
        if content_id: request['content_id'] = content_id
        return Volley(request, local_data=local_data)

    @property
    def request(self):
        return self._request
    
    @property
    def response(self):
        return self._response
    
    @property
    def local_data(self):
        return self._local_data

    @property
    def persist_data(self):
        return self._robot_data.get("persist",{})
    
    @property
    def config(self):
        return self._robot_data.get("config",{})
    
    @property
    def state(self):
        return self._robot_data.get("state",{})

    @property
    def entities(self):
        return self._local_data.get("entities",[])
    
    # Called by volley handling to pass local session data
    def assign_local_data(self, local_data):
        self._local_data = local_data
        logger.info(f'Assigning local_data={local_data}')

    def set_output(self, text, markup, output_type=None):
        self._response['output']['text'] = text
        if markup:
            self._response['output']['markup'] = markup
        if output_type:
            self._response['response_action']['output_type'] = output_type
            self._response['response_actions'][0]['output_type'] = output_type


    def create_response(self, res=0, output_type='GLOBAL_RESPONSE'):
        rcr = self._request
        self._response = { 
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
            self._response['input_speech'] = rcr['speech']
    
    # Add a named response action to a response, with optional params
    def add_response_action(self, action_name, module_id=None, content_id=None, output_type='GLOBAL_RESPONSE'):
        action = { 'action': action_name, 'output_type': output_type }
        if module_id:
            action['module_id'] = module_id
        if content_id:
            action['content_id'] = content_id
        # append if there is already an action, otherwise replace
        if 'response_actions' in self._response and 'action' in self._response['response_action']:
            self._response['response_actions'].append(action)
        else:
            self._response['response_actions'] = [ action ]
            self._response['response_action'] = action

    # Create launch to the next thing (better) or an exit (not as good)
    def add_launch_or_exit(self):
        if 'recommend' in self._request and 'exits' in self._request['recommend'] and len(self._request['recommend']['exits']) > 0:
            self.add_response_action('launch',
                                      module_id=self._request['recommend']['exits'][0].get('module_id'),
                                      content_id=self._request['recommend']['exits'][0].get('content_id'))
        else:
            self.add_response_action('exit_module')

    # Add an execution action to the response
    def add_execution_action(self, fname, fparams=None, output_type='GLOBAL_RESPONSE'):
        action = { 'action': 'execute', 'output_type': output_type, 'function_id': fname }
        if fparams:
            action['function_args'] = fparams
        # append if there is already an action, otherwise replace
        if 'response_actions' in self._response and 'action' in self._response['response_action']:
            self._response['response_actions'].append(action)
        else:
            self._response['response_actions'] = [ action ]
            self._response['response_action'] = action
    
    # Change event subscriptions on this response
    def update_subscriptions(self, event_list, clear=False):
        subrec = { 'active': event_list, 'clear': clear }
        self._response['response_action']['event_subscription'] = subrec
        self._response['response_actions'][0]['event_subscription'] = subrec

    # Get a paintext string from a remote chat response w/ actions in text
    def debug_response_string(self):
        payload = self._response
        respact = ""
        if 'response_actions' in payload:
            for ra in payload["response_actions"]:
                if "action" in ra:
                    if ra["action"] == "launch":
                        pending_launch = ( ra["module_id"], ra["content_id"] if "content_id" in ra else "")
                        respact += f' [{ra["action"]} -> {pending_launch}]'
                    elif ra["action"] == "launch_if_confirmed":
                        pending_if = ( ra["module_id"], ra["content_id"] if "content_id" in ra else "")
                        respact += f' [{ra["action"]} -> {pending_if}]'
                    elif ra["action"] == "execute":
                        pending_if = ( ra["function_id"], ra["function_args"] if "function_args" in ra else "")
                        respact += f' [{ra["action"]} -> {pending_if}]'
                    elif ra["action"] == "exit_module":
                        respact += f' [{ra["action"]}]'
                    else:
                        respact += f' [{ra["action"]} -> Unsupported action]'
        return payload['output']['text'] + respact
