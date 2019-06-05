#!/usr/bin/env python3

import configparser
import sys
import requests
import requests.packages.urllib3
from flask import Flask
from flask import request
from ciscoconfbot import ConfigOptions

requests.packages.urllib3.disable_warnings()

ciscoconfbot = Flask(__name__)

# Check that config file argument is present

if len(sys.argv) < 2:
    print('Path to config file not present, exiting')
    sys.exit()

config_file = sys.argv[1]

# Set some basic variables to use for the app itself
config = configparser.ConfigParser()
config.read(config_file)
bot_config = config['bot']
bot_email = bot_config.get('bot_email')
access_token = bot_config.get('access_token')
base_url = bot_config.get('base_url')
messages_url = bot_config.get('messages_url')
server = bot_config.get('server')
port = bot_config.get('port')
core_dev = bot_config.get('core_device')
core_vlan = bot_config.get('core_vlan')
core_exclude = bot_config.get('core_address_exclude')

# Set up file/directory structure
directories = config['directories']
base_config_directory = directories.get('base_config_directory')
device_directory = directories.get('device_directory')
device_running_config_directory = directories.get('device_running_config_directory')
creds_file = directories.get('creds_file')


# Main function that's used to parse messages sent to the bot using @botname syntax in Teams
@ciscoconfbot.route('/', methods=['POST'])
def index():
    # Grab message and room ID to use to reply to as bot can be used in any room it's added to
    headers = {"Authorization": "Bearer {}".format(access_token), "Content-Type": "application/json"}
    message_id = request.json.get('data').get('id')
    room_id = request.json.get('data').get('roomId')
    msg_details = requests.get(base_url+"messages/"+message_id, headers=headers)

    # Create config object and grab message details
    config_obj = ConfigOptions(access_token, base_url, messages_url, room_id, base_config_directory,
                               device_directory, device_running_config_directory, creds_file, headers,
                               core_dev, core_vlan, core_exclude)

    # Get text portion of message as well as sender's email
    message, email = config_obj.get_message(msg_details)

    # Check that bot isn't the original sender of the message and that only internal users can query devices
    if email == bot_email:
        return ''

    if 'VistaOutdoor.com' in email:

        # If message is none, send 'help' info, otherwise, complete task as requested

        if '/serial' in message:
            config_obj.return_serial(message, room_id)

        elif '/upload' in message:
            config_obj.upload(msg_details, room_id)

        elif '/config' in message:
            config_obj.complete_config(msg_details, room_id)

        else:
            config_obj.send_to_teams('Please type in an option', room_id)

    else:
        return ''


if __name__ == "__main__":
    ciscoconfbot.run(host=server, port=port, debug=True)
