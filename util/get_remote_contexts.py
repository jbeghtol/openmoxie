from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import CANNED_QUERY_REMOTE_CHAT_CONTEXTS
import sys
import os
import time
import json
import argparse
import collections

_DEFAULT_OUTFILE = "Contexts.json"
_PENDING_CONTEXTS = None

def dict_merge(dct, merge_dct):
    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict) and isinstance(merge_dct[k], dict)):  #noqa
            dict_merge(dct[k], merge_dct[k])
        elif (k in dct and isinstance(dct[k], list) and isinstance(merge_dct[k], list)):  #noqa
            dct[k] = dct[k] + merge_dct[k]
        else:
            dct[k] = merge_dct[k]

def save_contexts(command, payload):
    global _PENDING_CONTEXTS
    if payload["result"] == 9:
        print("Initial results incomplete.  Waiting on addition responses.")
        if not _PENDING_CONTEXTS:
            _PENDING_CONTEXTS = payload["query_data"]["contexts"]
            print(f"First set: {len(_PENDING_CONTEXTS['conversation_contexts'])}")
        else:
            dict_merge(_PENDING_CONTEXTS, payload["query_data"]["contexts"])
            print(f"Next set: {len(_PENDING_CONTEXTS['conversation_contexts'])}")
        return
    elif payload["result"] == 0:
        if not _PENDING_CONTEXTS:
            contexts = payload["query_data"]["contexts"]
            print(f"Initial results in first response.  Size: {len(contexts['conversation_contexts'])}")
        else:
            print(f"Final results response size: {len(payload['query_data']['contexts']['conversation_contexts'])}")
            dict_merge(_PENDING_CONTEXTS, payload["query_data"]["contexts"])
            contexts = _PENDING_CONTEXTS
            _PENDING_CONTEXTS = None
        print(f"Final merged set: {len(contexts['conversation_contexts'])}")
        outfile = args.out_file if args.out_file else _DEFAULT_OUTFILE
        with open(outfile, "w") as of:
            of.write(json.dumps(contexts, indent=4))
            version = payload["query_data"]["version"]
            print(f"Downloaded version {version} and saved to {outfile}")
            os._exit(os.EX_OK)
    else:
        print(f'Failed with error {payload["result"]}')
        os._exit(os.EX_OK)

def on_connect(client, rc):
    request = CANNED_QUERY_REMOTE_CHAT_CONTEXTS
    if args.production:
        request["topic"] = "remote-chat"
    if args.api_version:
        api_ver = int(args.api_version)
        request["payload"]["api_version"] = api_ver
    else:
        api_ver = request["payload"]["api_version"]
    request["payload"]["user_id"] = creds.get_user_id()
    endp = request["topic"]
    print(f"Querying from {endp} using api_version={api_ver}")
    client.publish_canned(request)
    
parser = argparse.ArgumentParser(description='Download Contexts')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--out_file", dest="out_file", metavar="out_file", type=str, action="store", help="Target file to store output")
parser.add_argument("--production", "--production", action="store_true", help="Use rc-production instead of rc-staging")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
args = parser.parse_args()

creds = RobotCredentials()
c = MoxieClient(creds, endpoint=args.iot) if args.iot else MoxieClient(creds)
c.add_connect_handler(on_connect)
c.add_command_handler("remote_chat", save_contexts)
c.connect(start=True)
time.sleep(10)
print("Did not receive contexts after 10s.  Aborting.")
c.stop()
