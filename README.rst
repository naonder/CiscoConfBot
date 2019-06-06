CiscoConfBot
=============


CiscoConfBot is a Webex Teams bot written in Python3.

Source Code
-----------

https://github.com/naonder/CiscoConfBot

PyPI package
------------

https://pypi.org/project/ciscoconfbot/

Setup
-------------

  pip install ciscoconfbot

Create bot at:
    https://developer.webex.com/my-apps/new/bot

Setup webhook via Webex Teams API or at:
    https://developer.webex.com/docs/api/v1/webhooks/create-a-webhook

| See sample creds and configuration files prior to starting bot.
| Create 3 directories where the bot will store various configurations and/or device files.
| Note that config and creds files need to be structured like the examples show.
| Also, see sample .yml file for correct formatting

    mkdir /path/to/dir

Running
-------

Run with

    python -m ciscoconfbot path/to/config/file.ini


| Alternatively, you can setup a system service to start on reboot/reload.
| See example service file for a quick idea.
| Once configured, you can enable it once with:

    systemctl start nameofservice.service


| Or you can enable the service to start after the server/device has been reloaded

    systemctl enable nameofservice.service

Operation
---------

Once bot has been configured, add the bot to a space and invoke:

    @nameofbot

Operations are as follow:

    | @nameofbot /serial ipaddressofdevice (returns serial number of device)
    | @nameofbot /upload (requires zip folder of device configs in hostname.txt format)
    | @nameofbot /config (requires .yml file of hostnames and serial numbers)

Author
------

naonder - nate.a.onder@gmail.com