#!/usr/bin/env python3
"""Helper file to communicate with the TemperatureController in a REPL
"""

import logging

try:
    from PyQt6.QtCore import QSettings
except ModuleNotFoundError:
    try:
        from PyQt5.QtCore import QSettings
    except ModuleNotFoundError:
        QSettings = None

from devices import intercom


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class Controller:
    """Connection to the TemperatureController."""

    def __init__(self, host=None, port=None):
        if QSettings:
            settings = QSettings("NLOQO", "TemperatureControllerPanel")
            if host is None:
                host = settings.value('IPaddress', "127.0.0.1", str)
            if port is None:
                port = settings.value('port', 22001, int)
        self.com = intercom.Intercom(host, port)

    def sendObject(self, typ, data):
        """Send an object and handle the errors."""
        responseTyp, content = self.com.sendObject(typ, data)
        if responseTyp == 'ERR':
            raise ConnectionError(content.decode('ascii'))
        elif responseTyp == 'SET':
            return content
        elif responseTyp == 'ACK' and not content:
            return responseTyp
        else:
            return responseTyp, content

    def set_value(self, data):
        """Set values in the `data` dictionary."""
        return self.sendObject("SET", data)

    def general(self):
        return self.sendObject('GET', ['database/table', 'readoutInterval'])

    def get_pid(self, id):
        """Get the pid values of the pid with the number `id`."""
        name = f"pid{id}"
        keys = [f"{name}/setpoint", f"{name}/Kp", f"{name}/Ki", f"{name}/Kd",
                f"{name}/lowerLimit", f"{name}/lowerLimitNone", f"{name}/upperLimit", f"{name}/upperLimitNone",
                f"{name}/sensor", f"{name}/autoMode", f"{name}/lastOutput", f"{name}/state", f"{name}/output"]
        return self.sendObject('GET', keys)

    def get_compontents(self, id):
        """Get the components of the pid controller."""
        key = f"pid{id}"
        return self.sendObject('CMD', [key, "components"])[f'{key}/components']

    @property
    def log(self):
        """The log of the controller."""
        return self.sendObject('GET', ['log'])['log']

    @property
    def sensors(self):
        """Sensor values of the controller."""
        return self.sendObject('GET', ['data'])['data']
