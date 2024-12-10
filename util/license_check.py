from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import CANNED_QUERY_LICENSES
import sys
import os
import time
import json
import argparse

_DEFAULT_OUTFILE = "Licenses.json"

def save_query(command, payload):
    outfile = args.out_file if args.out_file else _DEFAULT_OUTFILE
    if "license_values" in payload:
        with open(outfile, "w") as of:
            of.write(json.dumps(payload["license_values"], indent=4))
            of.flush()
            print(f"Downloaded licenses and saved to {outfile}")
            os._exit(os.EX_OK)

def on_connect(client, rc):
    request = CANNED_QUERY_LICENSES
    print(f"Querying...")
    client.publish_canned(request)
    
parser = argparse.ArgumentParser(description='Download Licenses')
parser.add_argument("--out_file", dest="out_file", metavar="out_file", type=str, action="store", help="Target file to store output")
parser.add_argument("--iot", dest="iot", metavar="iot", type=str, action="store", help="Specifiy the IOT endpoint to use [staging, production, dev]")
args = parser.parse_args()

c = MoxieClient(RobotCredentials(), endpoint=args.iot) if args.iot else MoxieClient(RobotCredentials())
c.add_connect_handler(on_connect)
c.add_command_handler("query_result", save_query)
c.connect(start=True)
time.sleep(10)
print("Did not receive licenses after 10s.  Aborting.")
c.stop()
