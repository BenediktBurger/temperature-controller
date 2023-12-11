#!/usr/bin/env python3
"""
Example configuration of the local sensors.

Adjust this file according to your needs.
If a method is not required, just use 'pass'.

Necessary methods
-----------------
setup : self
    What to do at initialization.
getData : self
    Read the sensors and return a dictionary with the data.
close : self
    What to do at closure of the controller.

Optional methods
----------------
setOutput : self, output, value
    Set an output to a value
executeCommand : self, command
    Handle the string `command`, for example change some device settings.


All the other methods here are examples for routines outsourced from above
necessary or optional methods.
"""

import math
from typing import Any

# Necessary for tinkerforge
from tinkerforge.ip_connection import Error as tfError


# Main methods setup, getData, close.
def setup(self) -> None:
    """Configure the sensors."""
    raise NotImplementedError
    self.rm = pyvisa.ResourceManager()
    try:
        self.south = setupArduino(self.rm, "/dev/ArduinoSouth")
    except Exception:
        pass  # Setup failed, so no device stored.
    try:
        self.north = setupArduino(self.rm, "/dev/ArduinoNorth")
    except Exception:
        pass  # Setup failed, so no device stored.
    try:
        self.wde = setupWDE(self.rm)
    except Exception:
        pass  # Setup failed, so no device stored.


def getData(self) -> dict[str, float]:
    """Read the sensors and return a dictionary."""
    raise NotImplementedError
    data = {}  # Empty dictionary.
    data.update(getAirQuality(self))
    data.update(getArduinoData(self.south))  # Combine with another dictionary.
    data.update(getWDEData(self.wde))
    # Example for a tinkerforge temperature sensor with 'uid', together with error handling
    try:
        data['abc'] = self.tfDevices['uid'].get_temperature() / 100  # Add a single value.
    except tfError as exc:
        if exc.value == tfError.TIMEOUT:
            del self.tfDevices['uid']
    except KeyError:
        pass  # device is not connected
    return data
    # Tinkerforge:
    # temperatureV2.get_temperature() / 100  # in °C
    # analogInV3.get_voltage()  # in mV
    # airQuality.get_all_values()  # air quality, air quality accuracy, temperature in 1/100°C, humidity in 1/100 %, air pressure in 1/100 hPa
    # airQuality.get_iaq_index()  # air quality index (0-500) and its accuracy (0 bad, 3 high)
    # airQuality.get_temperature() / 100  # in °C
    # airQuality.get_humidity() / 100  # relative air humidity in %
    # airQuality.get_air_pressure() / 100  # in hPa


def setOutput(self, output: str, value: float) -> None:
    """Set the additional `output` to `value`."""
    raise NotImplementedError
    print(f"{output} has now value {value}.")


def executeCommand(self, command: str) -> Any:
    """Execute `command`, sending it to the arduino."""
    raise NotImplementedError
    return self.south.query(command)


def close(self) -> None:
    """Close the connections."""
    raise NotImplementedError
    try:
        self.south.close()
    except AttributeError:
        pass  # Not existent
    try:
        self.wde.close()
    except AttributeError:
        pass  # Not existent
    try:
        self.rm.close()  # Serial resource manager
    except AttributeError:
        pass


# Auxiliary methods.

# Tinkerforge
def getAirQuality(self):
    """Read the air quality bricklet and return the data in a dictionary."""
    try:
        bricklet = self.tfDevices[self.tfMap['airQuality']]
    except (AttributeError, KeyError):
        return {}
    try:
        iaq, iaqa, temp, humidity, pressure = bricklet.get_all_values()
    except tfError as exc:
        if exc.value == tfError.TIMEOUT:
            del self.tfDevices[self.tfMap['airQuality']]
            del self.tfMap['airQuality']
        return {}
    else:
        return {  # 'airQuality': iaq,
                'temperature': temp / 100,
                'humidity': humidity / 100,
                'airPressure': pressure / 100,
                }


# Methods for Arduino
def setupArduino(resourceManager, port):
    """Configure the serial connection on `port` for Arduino."""
    arduino = resourceManager.open_resource(f"ASRL{port}::INSTR")
    """
    Arduino uses the same defaults as visa:
        baudrate 9600
        8 data bits
        no parity
        one stop bit
    """
    arduino.read_termination = "\r\n"
    arduino.write_termination = "\n"
    arduino.timeout = 1000
    return arduino


def getArduinoData(arduino):
    try:
        raw = arduino.query("r").split("\t")
    except AttributeError:
        return {}
    else:
        data = {'cold': raw[0],
                'main': raw[1],
                'aux': raw[2],
                'setpoint': raw[3]
                }
        for key in data.keys():
            data[key] = calculateTemperature(data[key])
        return data


def setSetpoint(self, temperature):
    """Set the arduino setpoint to `temperature`."""
    setpoint = calculateSetpoint(temperature)
    self.south.query(f"s{setpoint}")


def calculateTemperature(voltage):
    """Convert the Arduino `voltage` in mV to a temperature in °C."""
    try:
        voltage = float(voltage)
    except Exception as exc:
        print(exc)
        raise
    voltage /= 1024  # to get a relative voltage to the maximum
    # now according to a Labview program:
    voltage = voltage / (1 - voltage)
    if voltage >= 3.277:
        pars = [3.357042, 2.5214848, 3.3743283, -6.4957311]
    elif voltage >= 0.06816:
        pars = [3.354017, 2.5617244, 2.1400943, -7.2405219]
    else:
        pars = [3.3536166, 2.53772, 0.85433271, -8.7912262]
    return 1 / (pars[0] * 1E-3
                + pars[1] * 1E-4 * math.log(voltage)
                + pars[2] * 1E-6 * (math.log(voltage))**2
                + pars[3] * 1E-8 * (math.log(voltage))**3) - 273.15


def calculateSetpoint(temperature):
    """Convert the `temperature` in an Arduino setpoint."""
    pars = [1.90574605e-03, -1.09052486e-01, -9.36743448e+00, 7.84559931e+02]
    return pars[0] * temperature**3 + pars[1] * temperature**2 + pars[2] * temperature + pars[3]


# Methods for ELV USB-WDE weather sensor receiver
def setupWDE(resourceManager):
    """Initialize the ELV wde weather sensor receiver."""
    wde = resourceManager.open_resource("ASRL/dev/ttyUSB0::INSTR")
    wde.read_termination = '\r\n'
    while wde.bytes_in_buffer:
        wde.read()
    return wde


def getWDEData(wde):
    """Read the wde sensor data."""
    data = {}
    if wde.bytes_in_buffer:
        raw = wde.read().replace(',', '.').split(';')
        if raw[2+1]:
            data['experiment'] = float(raw[2+1])
        if raw[2+5]:
            data['outside'] = float(raw[2+5])
            data['humidityout'] = float(raw[10+5])
    return data
