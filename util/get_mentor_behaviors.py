from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import CANNED_QUERY_MENTOR_BEHAVIORS
import sys
import os
import time
import json
import argparse
import collections

_DEFAULT_OUTFILE = "MentorBehaviors.json"

def save_mbs(command, payload):
        mbs = payload["mentor_behaviors"]
        print(f"Initial results in first response.  Size: {len(mbs)}")
        outfile = args.out_file if args.out_file else _DEFAULT_OUTFILE
        with open(outfile, "w") as of:
            print(json.dumps(mbs, indent=4), file=of, flush=True)
            print(f"Downloaded mbs and saved to {outfile}")
            os._exit(os.EX_OK)

def on_connect(client, rc):
    request = CANNED_QUERY_MENTOR_BEHAVIORS
    user = creds.get_user_id()
    request["payload"]["user_id"] = user
    print(f"Querying mentor behavior for ", user)
    print(request)
    client.publish_canned(request)
    
parser = argparse.ArgumentParser(description='Download Contexts')
parser.add_argument("--api_version", dest="api_version", metavar="api_version", type=str, action="store", help="Set the robot API verison in use")
parser.add_argument("--out_file", dest="out_file", metavar="out_file", type=str, action="store", help="Target file to store output")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
args = parser.parse_args()

creds = RobotCredentials()
c = MoxieClient(creds, endpoint=args.iot) if args.iot else MoxieClient(creds)
c.add_connect_handler(on_connect)
c.add_command_handler("query_result", save_mbs)
c.connect(start=True)
time.sleep(10)
print("Did not receive mentor behaviors after 10s.  Aborting.")
c.stop()
