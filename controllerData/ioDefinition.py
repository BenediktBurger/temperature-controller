"""
Define a class for input and output of the Temperature controller.

classes
-------
InputOutput
    Handle input and output.

Created on Mon Jun 14 16:25:43 2021 by Benedikt Moneke
"""

import logging
from typing import Any

from . import sensors

log = logging.getLogger("TemperatureController")

try:  # Tinkerforge for sensors/output
    from tinkerforge.ip_connection import IPConnection, Error as tfError
    from tinkerforge.brick_hat import BrickHAT
    from tinkerforge.bricklet_air_quality import BrickletAirQuality
    from tinkerforge.bricklet_analog_in_v3 import BrickletAnalogInV3
    from tinkerforge.bricklet_analog_out_v3 import BrickletAnalogOutV3
    from tinkerforge.bricklet_one_wire import BrickletOneWire
    from tinkerforge.bricklet_temperature_v2 import BrickletTemperatureV2
except ModuleNotFoundError:
    log.error("Tinkerforge modules not found.")
    tf = False
else:
    tf = True
    devices = {111: BrickHAT,
               297: BrickletAirQuality,
               295: BrickletAnalogInV3,
               2115: BrickletAnalogOutV3,
               2123: BrickletOneWire,
               2113: BrickletTemperatureV2,
               }


class InputOutput:
    """Definition of input for sensors and output for controlling."""

    # Setup and closure.
    def __init__(self, controller=None) -> None:
        """Initialize the input/output"""
        self.controller = controller
        self.setupTinkerforge()
        try:
            sensors.setup(self)
        except Exception as exc:
            log.exception("Input-output init failed.", exc_info=exc)

    def setupTinkerforge(self) -> None:
        """Create the tinkerforge connection."""
        if not tf:
            return
        self.tfDevices = {}  # dictionary for the bricklets
        self.tfMap = {}  # dictionary for mapping the devices to tasks
        tfCon = IPConnection()
        tfCon.connect("localhost", 4223)  # values for local installation
        self.tfCon = tfCon
        tfCon.register_callback(IPConnection.CALLBACK_ENUMERATE, self.deviceConnected)
        tfCon.enumerate()  # ask all bricklets/bricklets to announce themselves

    def deviceConnected(self, uid, connected_uid, position, hardware_version,
                        firmware_version, device_identifier, enumeration_type) -> None:
        """Store a connected thinkerforge device in the database."""
        if enumeration_type < IPConnection.ENUMERATION_TYPE_DISCONNECTED:
            # Types: AVAILABLE 0, CONNECTED 1, DISCONNECTED 2
            log.info(f"Device {'connected' if enumeration_type else 'available'}: {uid} at {position} of type {device_identifier}.")  # noqa
            if uid not in self.tfDevices.keys():
                self.tfDevices[uid] = devices[device_identifier](uid, self.tfCon)
            if device_identifier == BrickHAT.DEVICE_IDENTIFIER:
                self.tfMap['HAT'] = uid
            elif device_identifier == BrickletAnalogOutV3.DEVICE_IDENTIFIER:
                if position == 'a':
                    self.tfMap['out0'] = uid
                else:
                    self.tfMap['out1'] = uid
            elif device_identifier == BrickletAirQuality.DEVICE_IDENTIFIER:
                self.tfMap['airQuality'] = uid
        else:
            # Only uid and enumeration_type have valid values.
            log.info(f"Device {uid} disconnected.")
            try:
                del self.tfDevices[uid]
            except KeyError:
                pass
            else:
                if uid in self.tfMap.values():
                    self.tfMap = {key: val for key, val in self.tfMap.items() if val != uid}

    def close(self) -> None:
        """Close the connection."""
        try:
            sensors.close(self)
        except Exception as exc:
            log.exception("Sensors close failed.", exc_info=exc)
        try:  # Deactivate Watchdog.
            self.tfDevices[self.tfMap['HAT']].set_sleep_mode(0, 0, False, False, False)
        except (AttributeError, KeyError):
            log.error("No HAT brick found, watchdog is not deactivated.")
        try:
            self.tfCon.disconnect()
        except AttributeError:
            pass  # Not existent

    # Methods
    def getSensors(self) -> dict[str, float]:
        """Request the sensor data and return a dictionary."""
        try:  # Renew the HAT brick watchdog.
            self.tfDevices[self.tfMap['HAT']].set_sleep_mode(30, 1, True, False, True)
            # Parameters: Go to sleep in s, sleep for s, do sleeping, let bricklets sleep,
            # turn indicator on
        except (AttributeError, KeyError):
            pass
        try:  # Read the sensors.
            data = sensors.getData(self)
            assert isinstance(data, dict)
        except (AssertionError, NotImplementedError):
            return {}
        except Exception as exc:
            log.exception("Get sensors failed.", exc_info=exc)
            return {}
        else:
            return data

    def setOutput(self, name: str, value: float) -> None:
        """Set the output with `name` to `value` (for tinkerforge in V)."""
        if name in ("out0", "out1"):
            try:
                self.tfDevices[self.tfMap[name]].set_output_voltage(value * 1000)
            except (AttributeError, KeyError):
                log.warning(f"Output '{name}' is not connected.")
            except tfError as exc:
                if exc.value in (tfError.TIMEOUT, tfError.NOT_CONNECTED):
                    del self.tfDevices[self.tfMap[name]]
                    del self.tfMap[name]
        else:
            try:
                sensors.setOutput(self, name, value)
            except NotImplementedError as exc:
                raise KeyError(exc)

    def executeCommand(self, command: str) -> Any:
        """Send `command` to sensors."""
        try:
            return sensors.executeCommand(self, command)
        except NotImplementedError:
            return
