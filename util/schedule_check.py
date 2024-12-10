from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import CANNED_QUERY_SCHEDULE
import sys
import os
import time
import json
import argparse

_DEFAULT_OUTFILE = "Schedule.json"
creds = None

def save_query(command, payload):
    outfile = args.out_file if args.out_file else _DEFAULT_OUTFILE
    if "schedule" in payload:
        with open(outfile, "w") as of:
            of.write(json.dumps(payload["schedule"], indent=4))
            of.flush()
            print(f"Downloaded schedule and saved to {outfile}")
            os._exit(os.EX_OK)

def on_connect(client, rc):
    request = CANNED_QUERY_SCHEDULE
    # add our AUID
    request["payload"]["auid"] = creds.get_user_id()
    if args.schedule:
        request["payload"]["schedule_id"] = args.schedule
    print(f"Querying...{request}")
    client.publish_canned(request)
    
parser = argparse.ArgumentParser(description='Download Schedule')
parser.add_argument("--out_file", dest="out_file", metavar="out_file", type=str, action="store", help="Target file to store output")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
parser.add_argument("--schedule", dest="schedule", metavar="schedule", type=str, action="store", help="Schedule name to query")
args = parser.parse_args()

creds = RobotCredentials()
c = MoxieClient(RobotCredentials(), endpoint=args.iot) if args.iot else MoxieClient(creds)
c.add_connect_handler(on_connect)
c.add_command_handler("query_result", save_query)
c.connect(start=True)
time.sleep(30)
print("Did not receive Schedule after 30s.  Aborting.")
c.stop()
