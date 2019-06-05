#!/usr/bin/env python3

import json
import threading
import requests
import zipfile
import io
import yaml
import tempfile
import shutil
import os
from requests_toolbelt.multipart.encoder import MultipartEncoder
from napalm import get_network_driver


class ConfigOptions(object):
    def __init__(self, access_token, base_url, messages_url, room_id, bcdirectory, scdirectory, drcdirectory,
                 creds_file, headers, core_dev, core_vlan, core_exclude):
        self.results = []
        self.serials = {}
        self.access_token = access_token
        self.base_url = base_url
        self.messages_url = messages_url
        self.room_id = room_id
        self.bcdirectory = bcdirectory  # Where device configs are stored prior to being pushed to devices
        self.scdirectory = scdirectory  # Where device dict file is saved
        self.drcdirectory = drcdirectory  # Temp dir is created here to store running config of devices after pushing
        # self.temp_dir = tempfile.TemporaryDirectory(dir=self.drcdirectory)
        self.creds_file = creds_file
        self.headers = headers
        self.core_dev = core_dev
        self.core_vlan = core_vlan
        self.core_exclude = core_exclude
        with open(creds_file) as credentials:
            self.creds = json.load(credentials)

    # Base device connection to use in NAPALM functions
    def dev_base_connection(self, base_address, devtype, base_username, base_password, time_out):
        driver = get_network_driver(devtype)
        device = driver(base_address, base_username, base_password, time_out)
        return device

    # Used to grab address info from the core switch
    def get_addresses(self):
        device = self.dev_base_connection(self.core_dev, 'ios', self.creds['autoname'], self.creds['autopass'], 1)
        device.open()
        entries = device.cli(['sh ip arp vlan {} | e {}|Protocol'.format(self.core_vlan, self.core_exclude)])
        addresses = []
        for line in entries['sh ip arp vlan {} | e {}|Protocol'.format(self.core_vlan, self.core_exclude)].split('\n'):
            if 'Incomplete' in line:
                pass
            else:
                address = line.split()[1]
                addresses.append(address)
        return addresses

    # Compare serials/addresses that are online w/ given file, then create a address to hostname mapping dictionary
    def get_address_hostnames(self, online_serials, pending_serials):
        new_dict = {}
        for address, serial_1 in online_serials.items():
            for hostname, serial_2 in pending_serials.items():
                if serial_1 == serial_2:
                    new_dict[address] = hostname

        return new_dict

    # Create multiple threads to push configurations
    def mass_config(self, device_dict, temp_dir):
        threads = []
        for dev_address, hostname in device_dict.items():
            thread = threading.Thread(target=self.config_devices, args=(dev_address, hostname, temp_dir))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        return self.results

    # Attempt to configure a device using 'new_config' function
    # If it fails, then append hostname to the results list
    def config_devices(self, dev_address, hostname, temp_dir):
        try:
            config_file = open(self.bcdirectory+'{}.txt'.format(hostname), 'r')
            config_file.close()
            device = self.dev_base_connection(dev_address, 'ios', self.creds['username'], self.creds['password'], 1)
            self.new_config(device, self.bcdirectory+'{}.txt'.format(hostname), hostname, temp_dir)
        except:
            self.results.append(hostname)

    # Sets hostname of device, configures it, then saves its running config to a temp director,
    # and then returns its running config
    def new_config(self, device, config, hostname, temp_dir):
        device.open()
        device.load_template('set_hostname', hostname=hostname)
        device.commit_config()
        device.load_merge_candidate(filename=config)
        device.commit_config()
        with open(temp_dir.name+'/{}_running.txt'.format(hostname), 'w') \
                as running_config:
            running = device.get_config()['running']
            running_config.write(running)
        device.close()
        return running

    # Used in grabbing serials for potential config devices - done towards beginning of /config
    def get_serials(self, address):
        device = self.dev_base_connection(address, 'ios', self.creds['username'], self.creds['password'], 1)
        try:
            device.open()
            serial = device.get_facts()['serial_number']
            device.close()
            self.serials[address] = serial
        except:
            self.serials[address] = 'Unknown'

    # Logs into devices and returns all serials as a dictionary to be used later
    def serial_dictionary(self, addresses):
        threads = []
        for device in addresses:
            thread = threading.Thread(target=self.get_serials, args=(device, ))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        return self.serials

    # Logs into device and grabs chassis serial number
    def get_serial(self, device):
        device.open()
        serial_num = device.get_facts()['serial_number']
        device.close()
        return serial_num

    # Tries to create a zip file of the device running configs before uploading back to Teams
    def create_attachment(self, room_id, temp_dir):
        try:
            shutil.make_archive(self.drcdirectory+'running_configs', 'zip', temp_dir.name)
            content = MultipartEncoder({'roomId': room_id,
                                        'text': 'Running configs attached',
                                        'files': ('running_configs.zip',
                                                  open(self.drcdirectory+'running_configs.zip', 'rb'),
                                                  'application/x-zip-compressed')})
            return content
        except:
            return 'No configs to return'

    # Post attachment to teams
    def post_attachment_to_teams(self, message):
        requests.post(self.messages_url, data=message,
                      headers={'Authorization': 'Bearer {}'.format(self.access_token),
                               'Content-Type': message.content_type})

    # Send the reply message from the bot back into the room the query was sent from
    def send_to_teams(self, message, room_id):
        payload = {"roomId": room_id, "text": message}
        return requests.post(self.messages_url, data=json.dumps(payload), headers=self.headers)

    # Try to get text from the sender's message as well as their email
    def get_message(self, response):
        senders_message = response.json().get('text')
        senders_email = response.json().get('personEmail')
        return senders_message, senders_email

    # Attempt to retrieve an attachment addressed to the bot
    def get_attachment_from_message(self, response):
        senders_attachment = response.json().get('files')[0]
        return senders_attachment

    # Attempts to grab an uploaded zip file from message
    def upload(self, message, room_id):
        attach_headers = {"Authorization": "Bearer {}".format(self.access_token)}
        try:
            attachment_url = self.get_attachment_from_message(message)
            attachment = requests.get(attachment_url, headers=attach_headers)
            attach_type = attachment.headers['content-type']
            if attach_type != 'application/x-zip-compressed':
                self.send_to_teams('Only zip files allowed', room_id)
            else:
                with zipfile.ZipFile(io.BytesIO(attachment.content)) as zip_file:
                    zip_file.extractall(self.bcdirectory)
                    self.send_to_teams('Files can be found at {}'.format(self.bcdirectory), room_id)
        except TypeError:
            self.send_to_teams('Missing file or improper file type, try again', room_id)

    # Tries to complete configuration of either a single or multiple devices
    def complete_config(self, msg_details, room_id):
        attach_headers = {"Authorization": "Bearer {}".format(self.access_token)}
        temp_dir = tempfile.TemporaryDirectory(dir=self.drcdirectory)

        # Grab attachment, check type, compare against allowed types, then write to new file
        try:
            attachment_url = self.get_attachment_from_message(msg_details)
            attachment = requests.get(attachment_url, headers=attach_headers)
            attach_type = attachment.headers['content-type']
            if attach_type != 'text/plain':
                self.send_to_teams('Only .yml files supported', room_id)
            else:
                with open(self.scdirectory+'devices.yml', 'wb') as devices_file:
                    devices_file.write(attachment.content)

                # Send notification to room that message is received
                self.send_to_teams('Attachment received, will start configuring devices shortly', room_id)
                self.send_to_teams('Checking existing devices first, please stand by', room_id)

                # Get IP addresses of devices on staging VLAN via ARP entries on core switch
                addresses_on_core = self.get_addresses()
                self.send_to_teams('Following devices detected: ' + '\n' + '{}'.format('\n'.join(addresses_on_core)),
                              room_id)

                # Log into devices found and grab their serial numbers. Data will be in dictionary form
                dev_serials = self.serial_dictionary(addresses_on_core)
                self.send_to_teams('Serial number mappings: ' + '\n' +
                              '\n'.join('{}: {}'.format(k, v) for k, v in dev_serials.items()), room_id)

                # Load previous attachment, then compare attachment serials to device serials found before
                with open(self.scdirectory+'devices.yml', 'r') as yaml_file:
                    wanted_serials = yaml.load(yaml_file, Loader=yaml.BaseLoader)
                ip_to_hostname = self.get_address_hostnames(dev_serials, wanted_serials)
                self.send_to_teams('Preliminary checks completed, configuring devices now', room_id)

                # Begin configuring devices
                failed_devices = self.mass_config(ip_to_hostname, temp_dir)
                if failed_devices:
                    self.send_to_teams('Following devices failed '
                                  '(check config file exists on server, config is good, and that device is reachable:' +
                                  '\n' + '\n'.join(failed_devices), room_id)
                    config_attach = self.create_attachment(room_id, temp_dir)
                    self.post_attachment_to_teams(config_attach)
                    shutil.rmtree(temp_dir.name)
                    os.remove(self.drcdirectory+'running_configs.zip')
                else:
                    self.send_to_teams('All devices were successfully configured', room_id)
                    config_attach = self.create_attachment(room_id, temp_dir)
                    self.post_attachment_to_teams(config_attach)
                    shutil.rmtree(temp_dir.name)
                    os.remove(self.drcdirectory+'running_configs.zip')

        except TypeError as e:
            self.send_to_teams('Missing file or improper file type {}'.format(e), room_id)

    # Logs into device and grabs chassis serial number - used for /serial command
    def return_serial(self, message, room_id):
        if len(message.split(' ')) > 2:
            if message.split(' ')[-1] != '':
                dev_ip = message.split(' ')[-1]
                self.send_to_teams('Checking serial number of {}'.format(dev_ip), room_id)
                device = self.dev_base_connection(dev_ip, 'ios', self.creds['username'], self.creds['password'], 1)
                self.send_to_teams('Serial number of {} is {}'.format(dev_ip, self.get_serial(device)), room_id)
            else:
                self.send_to_teams('Please specify an address', room_id)
        else:
            self.send_to_teams('Please specify an address', room_id)
