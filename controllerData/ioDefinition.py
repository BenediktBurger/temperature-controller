"""
Define a class for input and output of the Temperature controller.

classes
-------
InputOutput
    Handle input and output.

Created on Mon Jun 14 16:25:43 2021 by Benedikt Moneke
"""

import numpy as np  # just for Arduinos

import pyvisa  # Serial communication like Arduinos

try:  # Tinkerforge for sensors/output
    from tinkerforge.ip_connection import IPConnection, Error as tfError
    from tinkerforge.brick_hat import BrickHAT
    from tinkerforge.bricklet_air_quality import BrickletAirQuality
    from tinkerforge.bricklet_analog_in_v3 import BrickletAnalogInV3
    from tinkerforge.bricklet_analog_out_v3 import BrickletAnalogOutV3
    from tinkerforge.bricklet_one_wire import BrickletOneWire
    from tinkerforge.bricklet_temperature_v2 import BrickletTemperatureV2
except ModuleNotFoundError:
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
    def __init__(self, controller=None):
        """Initialize the input/output"""
        self.controller = controller
        self.setupTinkerforge()
        self.readoutMethods = []  # List of local readout methods.
        # Local setup.
        self.rm = pyvisa.ResourceManager()
        try:  # Setup Arduino
            self.com = self.setupArduino("/dev/ttyACM0")  # eg-klima
            self.setupWDE(self.rm)
        except Exception:
            self.com = self.setupArduino(10)  # Myres

    def setupTinkerforge(self):
        """Create the tinkerforge connection."""
        if not tf:
            return
        self.tfDevices = {}  # dictionary for the bricklets
        self.tfMap = {}  # dictionary for mapping the devices to tasks
        tfCon = IPConnection()
        tfCon.connect("localhost", 4223)  # values for local installation
        self.tfCon = tfCon
        tfCon.register_callback(IPConnection.CALLBACK_ENUMERATE, self.deviceConnected)
        tfCon.enumerate()  # ask all bricks and bricklets to announce themselves.

    def deviceConnected(self, uid, connected_uid, position, hardware_version, firmware_version, device_identifier, enumeration_type):
        """Store a connected thinkerforge device in the database."""
        if enumeration_type < IPConnection.ENUMERATION_TYPE_DISCONNECTED:  # AVAILABLE 0, CONNECTED 1, DISCONNECTED 2
            print(f"Device {'connected' if enumeration_type else 'available'}: {uid} at {position} of type {device_identifier}.")
            self.tfDevices[uid] = devices[device_identifier](uid, self.tfCon)
            if device_identifier == BrickHAT.DEVICE_IDENTIFIER:
                self.tfMap['HAT'] = uid
            elif device_identifier == BrickletAnalogOutV3.DEVICE_IDENTIFIER:
                if position == 'a':
                    self.tfMap['analogOut0'] = uid
                else:
                    self.tfMap['analogOut1'] = uid
            elif device_identifier == BrickletAirQuality.DEVICE_IDENTIFIER:
                self.tfMap['airQuality'] = uid
        else:
            # Only uid and enumeration_type have valid values.
            print(f"Device {uid} disconnected.")
            try:
                del self.tfDevices[uid]
            except KeyError:
                pass
            else:
                if uid in self.tfMap.values():
                    self.tfMap = {key: val for key, val in self.tfMap.items() if val != uid}

    def close(self):
        """Close the connection."""
        try:
            self.tfCon.disconnect()
        except AttributeError:
            pass  # Not existent
        # Closure of local devices.
        try:
            self.com.close()
        except AttributeError:
            pass  # Not existent
        try:
            self.wde.close()
        except AttributeError:
            pass  # Not existent
        self.rm.close()  # Serial resource manager

    # Methods
    def getSensors(self):
        """Request the sensor data and return a dictionary."""
        data = {}
        try:
            iaq, iaqa, temp, humidity, pressure = self.tfDevices[self.tfMap['airQuality']].get_all_values()
        except tfError as exc:
            if exc.value == tfError.TIMEOUT:
                del self.tfDevices[self.tfMap['airQuality']]
                del self.tfMap['airQuality']
        except (AttributeError, KeyError):
            pass
        else:
            data['airQuality'] = iaq
            data['temperature'] = temp / 100
            data['humidity'] = humidity / 100
            data['airPressure'] = pressure / 100
        for method in self.readoutMethods:  # Read locally defined sensors.
            data.update(method())
        return data
        # Tinkerforge:
        # temperatureV2.get_temperature() / 100  # in °C
        # analogInV3.get_voltage()  # in mV
        # airQuality.get_all_values()  # air quality, air quality accuracy, temperature in 1/100°C, humidity in 1/100 %, air pressure in 1/100 hPa
        # airQuality.get_iaq_index()  # air quality index (0-500) and its accuracy (0 bad, 3 high)
        # airQuality.get_temperature() / 100  # in °C
        # airQuality.get_humidity() / 100  # relative air humidity in %
        # airQuality.get_air_pressure() / 100  # in hPa

    def setOutput(self, name, value):
        """Set the output with `name` to `value`."""
        if name == '0':
            self.setSetpoint(value)
        elif name == '1':
            try:
                self.tfDevices[self.tfMap['analogOut1']].set_output_voltage(value)
            except (AttributeError, KeyError):
                self.controller.errors['analogOut1'] = "Not connected."
            except tfError as exc:
                if exc.value in (tfError.TIMEOUT, tfError.NOT_CONNECTED):
                    del self.tfDevices[self.tfMap['analogOut1']]
                    del self.tfMap['analogOut1']

    # LOCAL DEFINITIONS

    # Methods for Arduino
    def setupArduino(self, port):
        """Configure the serial connection on `port` for Arduino."""
        com = self.rm.open_resource(f"ASRL{port}::INSTR")
        """
        Arduino uses the same defaults as visa:
            baudrate 9600
            8 data bits
            no parity
            one stop bit
        """
        com.read_termination = "\r\n"
        com.write_termination = "\n"
        com.timeout = 1000
        self.readoutMethods.append(self.getArduino)
        return com

    def getArduino(self):
        try:
            arduino = self.com.query("r").split("\t")
        except AttributeError:
            return {}
        else:
            data = {'cold': arduino[0],
                    'main': arduino[1],
                    'aux': arduino[2],
                    'setpoint': arduino[3]
                    }
            for key in data.keys():
                data[key] = self.calculateTemperature(data[key])
            return data

    def executeCommand(self, command):
        """Send `command` to the Arduino."""
        self.com.query(command)

    def calculateTemperature(self, voltage):
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
        return 1 / (pars[0] * 1E-3 + pars[1] * 1E-4 * np.log(voltage) + pars[2] * 1E-6 * (np.log(voltage))**2 + pars[3] * 1E-8 * (np.log(voltage))**3) - 273.15

    def calculateSetpoint(self, temperature):
        """Convert the `temperature` in an Arduino setpoint."""
        pars = [1.90574605e-03, -1.09052486e-01, -9.36743448e+00, 7.84559931e+02]
        return pars[0] * temperature**3 + pars[1] * temperature**2 + pars[2] * temperature + pars[3]

    def setSetpoint(self, temperature):
        """Set the current setpoint of the Arduino."""
        setpoint = self.calculateSetpoint(temperature)
        self.com.query(f"s{setpoint}")

    # Methods for ELV USB-WDE weather sensor receiver
    def setupWDE(self, resourceManager):
        """Initialize the ELV wde weather sensor receiver."""
        self.wde = resourceManager.open_resource("ASRL/dev/ttyUSB0::INSTR")
        self.wde.read_termination = '\r\n'
        while self.wde.bytes_in_buffer:
            self.wde.read()
        self.readoutMethods.append(self.getWDE)

    def getWDE(self):
        """Read the wde sensor data."""
        data = {}
        if self.wde.bytes_in_buffer:
            raw = self.wde.read().replace(',','.').split(';')
            if raw[2+1]:
                data['experiment'] = float(raw[2+1])
            if raw[2+5]:
                data['outside'] = float(raw[2+5])
                data['humidityout'] = float(raw[10+5])
        return data


class Dummy:
    """Just a dummy class for testing."""

    def __init__(self):
        """Initialize"""
        self.temperatures = {'main': 22.2}

    def read(self):
        return self.temperatures

    def close(self):
        pass
