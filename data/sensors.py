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
    """Readout class for sensors."""

    def __init__(self):
        """Initialize the system."""
        self.temperatures = []
        self.signals = SensorSignals()
        # Initialize the reader class
        self.thread = QtCore.QThread()
        self.reader = Reader()
        self.reader.moveToThread(self.thread)
        self.thread.started.connect(self.reader.listen)
        self.reader.dataReady.connect(self.setTemperatures)
        self.signals.close.connect(self.reader.close)
        self.signals.close.connect(self.thread.quit)
        self.thread.start()

    def close(self):
        """Close the connection."""
        self.reader.stop = True
        self.signals.close.emit()
        self.thread.wait()

    def read(self):
        """Return the values."""
        return self.temperatures

    def calculateTemperature(self, voltage):
        """Convert the `voltage` in mV to a temperature in °C."""
        voltage = float(voltage)
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

    def setTemperatures(self, data):
        """Set the current temperatures from data."""
        self.temperatures = self.multiCalc([data[0], data[1], data[3], data[5]])


class SensorSignals(QtCore.QObject):
    """Signals for Sensors."""
    close = QtCore.pyqtSignal()


class Reader(QtCore.QObject):
    """Read the values."""
    dataReady = QtCore.pyqtSignal(list)

    def __init__(self):
        """Initialize."""
        super().__init__()
        self.com = self.connect()
        self.stop = False

    def connect(self):
        """Configure the connection on `port`."""
        port = "/dev/ttyACM0"
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
        com.timeout = 10000
        return com

    def listen(self):
        """Read the values and send them to the Sensors class."""
        while not self.stop:
            data = self.com.read().split('\t')
            self.dataReady.emit(data)

    @pyqtSlot()
    def close(self):
        """Close the connection."""
        self.com.close()
