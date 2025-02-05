'''
REMOTE CHAT HELPERS

A set of method to assist in creating and adjusting records inside 
RemoteChatRequest (rcr) and RemoteChatResponse dictionaries.
'''
# Create a generic base response object matching a request object
def make_response(rcr, res=0, output_type='GLOBAL_RESPONSE'):
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

# Add a named response action to a response, with optional params
def add_response_action(resp, action_name, module_id=None, content_id=None, output_type='GLOBAL_RESPONSE'):
    action = { 'action': action_name, 'output_type': output_type }
    if module_id:
        action['module_id'] = module_id
    if content_id:
        action['content_id'] = content_id
    resp['response_actions'] = [ action ]
    resp['response_action'] = action

# Create launch to the next thing (better) or an exit (not as good)
def add_launch_or_exit(rcr, resp):
    if 'recommend' in rcr and 'exits' in rcr['recommend'] and len(rcr['recommend']['exits']) > 0:
        add_response_action(resp, 'launch',
                                    module_id=rcr['recommend']['exits'][0].get('module_id'),
                                    content_id=rcr['recommend']['exits'][0].get('content_id'))
    else:
        add_response_action(resp, 'exit_module')

# Get a paintext string from a remote chat response w/ actions in text
def debug_response_string(payload):
    respact = ""
    if 'response_action' in payload:
        ra = payload["response_action"]
        if "action" in ra:
            if ra["action"] == "launch":
                pending_launch = ( ra["module_id"], ra["content_id"] if "content_id" in ra else "")
                respact = f' [{payload["response_action"]["action"]} -> {pending_launch}]'
            elif ra["action"] == "launch_if_confirmed":
                pending_if = ( ra["module_id"], ra["content_id"] if "content_id" in ra else "")
                respact = f' [{payload["response_action"]["action"]} -> {pending_if}]'
            elif ra["action"] == "execute":
                pending_if = ( ra["function_id"], ra["function_args"] if "function_args" in ra else "")
                respact = f' [{payload["response_action"]["action"]} -> {pending_if}]'
            elif ra["action"] == "exit_module":
                respact = f' [{payload["response_action"]["action"]}]'
            else:
                respact = f' [{payload["response_action"]["action"]} -> Unsupported action]'
    return payload['output']['text'] + respact
