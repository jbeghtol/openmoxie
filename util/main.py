from robot_credentials import RobotCredentials
from moxie_client import MoxieClient
from moxie_messages import CANNED_QUERY_REMOTE_CHAT_CONTEXTS, CANNED_QUERY_CONTEXT_INDEX
import time

#
# Main - Demo.
# Connects, prints config and queryies client services context store index and prints that
# Exits after 10s
# 
def print_handler(command, payload):
    print(command+" "+str(payload))

def on_connect(client, rc):
    client.publish_canned(CANNED_QUERY_CONTEXT_INDEX)

c = MoxieClient(RobotCredentials())
c.add_config_handler(print_handler)
c.add_command_handler("query_result", print_handler)
c.add_connect_handler(on_connect)
c.connect(start=True)
time.sleep(10)
c.stop()
