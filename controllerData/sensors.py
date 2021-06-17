"""
Readout sensor class for different readouts depending on the local situation

Created on Mon Jun 14 16:25:43 2021 by Benedikt Moneke
"""

import numpy as np

try:  # Qt for nice effects.
    from PyQt6 import QtCore
    from PyQt6.QtCore import pyqtSlot
    qtVersion = 6
except ModuleNotFoundError:
    from PyQt5 import QtCore
    from PyQt5.QtCore import pyqtSlot
    qtVersion = 5
import pyvisa


class Sensors:
    """Readout sensors"""

    def __init__(self):
        """Initialize the sensors"""
        self.com = self.setup("/dev/ttyACM0")  # 10 on Myres

    def setup(self, port):
        """Configure the connection on `port`."""
        rm = pyvisa.ResourceManager()
        com = rm.open_resource(f"ASRL{port}::INSTR")
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
        return com

    def read(self):
        """Request the sensor data."""
        data = self.com.query("r").split("\t")
        # aux, main, cold, setpoint
        # return self.multiCalc([data[2], data[1], data[0], data[3]])
        temperatures = {'cold': data[0],
                        'main': data[1],
                        'aux': data[2],
                        'setpoint': data[3]
                        }
        for key in temperatures.keys():
            temperatures[key] = self.calculateTemperature(temperatures[key])
        return temperatures

    def calculateTemperature(self, voltage):
        """Convert the `voltage` in mV to a temperature in °C."""
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

    def multiCalc(self, voltages):
        """Convert an iterable `voltages` of strings to temperatures."""
        temperatures = []
        for voltage in voltages:
            temperatures.append(self.calculateTemperature(voltage))
        return temperatures

    def calculateSetpoint(self, temperature):
        """Convert the `temperature` in an Arduino setpoint."""
        pars = [1.90574605e-03, -1.09052486e-01, -9.36743448e+00, 7.84559931e+02]
        return pars[0] * temperature**3 + pars[1] * temperature**2 + pars[2] * temperature + pars[3]

    def setSetpoint(self, temperature):
        """Set the current setpoint of the Arduino."""
        setpoint = self.calculateSetpoint(temperature)
        self.com.query(f"s{setpoint}")

    def sendCommand(self, command):
        """Send a command to the Arduino."""
        self.com.query(command)

    def close(self):
        """Close the connection."""
        self.com.close()


class Dummy:
    """Just a dummy class for testing."""

    def __init__(self):
        """Initialize"""
        self.temperatures = {'main': 22.2}

    def read(self):
        return self.temperatures

    def close(self):
        pass


