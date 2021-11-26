#!/usr/bin/env python3
"""
Main file of the temperature controller for the lab.

Created on Mon Jun 14 11:12:51 2021 by Benedikt Moneke
"""

import datetime
import sys

try:  # Qt for nice effects.
    from PyQt6 import QtCore
    from PyQt6.QtCore import pyqtSlot
    qtVersion = 6
except ModuleNotFoundError:
    from PyQt5 import QtCore
    from PyQt5.QtCore import pyqtSlot
    qtVersion = 5
import psycopg2
from simple_pid import PID

from controllerData import connectionData  # file with the connection data in dictionaries: database = {'host': 'myres'...}.
from controllerData import listener, ioDefinition


class TemperatureController(QtCore.QObject):
    """The temperature controller itself."""
    stopSignal = QtCore.pyqtSignal()
    stopApplication = QtCore.pyqtSignal()

    def __init__(self):
        """Initialize the controller."""
        super().__init__()

        # Configure Settings
        application = QtCore.QCoreApplication.instance()
        application.setOrganizationName("NLOQO")
        application.setApplicationName("TemperatureController")
        settings = QtCore.QSettings()
        self.settings = settings

        # General config
        self.errors = {}  # Error dictionary.
        self.data = {}  # Current data dictionary.

        # Create objects like timers
        self.readoutTimer = QtCore.QTimer()
        self.threadpool = QtCore.QThreadPool()

        # Initialize sensors
        self.inputOutput = ioDefinition.InputOutput(controller=self)

        # PID controllers
        self.pids = {}
        self.pids['0'] = PID(auto_mode=False)  # in order to start with the last value
        self.pids['1'] = PID(auto_mode=False)
        self.pidSensor = {}  # the main sensor of the PID
        self.pidState = {}  # state of the corresponding output: 0 off, 1 manual, 2 pid
        for key in self.pids.keys():
            self.setupPID(key)

        # Configure the listener thread for listening intercom.
        self.setupListener(settings)

        self.connectDatabase()

        # Configure readoutTimer
        self.readoutTimer.start(settings.value('readoutInterval', defaultValue=5000, type=int))
        self.readoutTimer.timeout.connect(self.readTimeout)

    def setupListener(self, settings):
        """Setup the thread listening for intercom."""
        self.listenerThread = QtCore.QThread()
        self.stopSignal.connect(self.listenerThread.quit)
        self.listener = listener.Listener(port=settings.value('listener/port', defaultValue=22001, type=int),
                                          threadpool=self.threadpool, controller=self)
        self.listener.moveToThread(self.listenerThread)
        self.listenerThread.started.connect(self.listener.listen)
        self.listenerThread.start()
        # Listener Signals.
        self.listener.signals.stopController.connect(self.stop)
        self.listener.signals.pidChanged.connect(self.setupPID)
        self.listener.signals.timerChanged.connect(self.setTimerInterval)
        self.listener.signals.setOutput.connect(self.setOutput)
        self.listener.signals.sensorCommand.connect(self.sendSensorCommand)

    @pyqtSlot(str)
    def setupPID(self, name):
        """Configure the pid controller with `name`."""
        pid = self.pids[name]
        settings = QtCore.QSettings()
        settings.beginGroup(f'pid{name}')
        pid.output_limits = (None if settings.value('lowerLimitNone', defaultValue=True, type=bool) else settings.value('lowerLimit', type=float),
                             None if settings.value('upperLimitNone', defaultValue=True, type=bool) else settings.value('upperLimit', type=float))
        pid.Kp = settings.value('Kp', defaultValue=1, type=float)
        pid.Ki = settings.value('Ki', defaultValue=0, type=float)
        pid.Kd = settings.value('Kd', defaultValue=0, type=float)
        pid.setpoint = settings.value('setpoint', defaultValue=22.2, type=float)
        pid.set_auto_mode(settings.value('autoMode', defaultValue=True, type=bool),
                          settings.value('lastOutput', defaultValue=0, type=float))
        self.pidState[name] = settings.value('state', defaultValue=0, type=int)
        sensors = settings.value('sensor', defaultValue="", type=str).replace(' ', '').split(',')
        if sensors == ['']:
            self.errors[f'pid{name}Sensor'] = True
        self.pidSensor[name] = sensors

    @pyqtSlot()
    def stop(self):
        """Stop the controller and the application."""
        print("About to stop")
        self.readoutTimer.stop()
        # Stop the listener.
        try:
            self.listener.stop = True
        except AttributeError:
            pass
        self.stopSignal.emit()
        self.listenerThread.wait(10000)  # timeout in ms

        # Close the sensor and database
        self.inputOutput.close()
        try:
            self.database.close()
        except AttributeError:
            pass  # No database connection.

        # Stop the Application.
        if qtVersion == 6:
            connectionType = QtCore.Qt.ConnectionType.QueuedConnection
        else:
            connectionType = QtCore.Qt.QueuedConnection
        self.stopApplication.connect(QtCore.QCoreApplication.instance().quit, type=connectionType)
        self.stopApplication.emit()
        print("Stopped.")

    # CONNECTIONS

    def connectDatabase(self):
        """(Re)Establish a connection to the database for storing sensor data."""
        try:
            self.database.close()
            del self.database
        except AttributeError:
            pass  # no database present
        try:
            self.database = psycopg2.connect(**connectionData.database, connect_timeout=5)
        except Exception as exc:
            self.errors['database'] = f"Database connection error {type(exc).__name__}: {exc}."

    # CONFIG

    def setTimerInterval(self, name, interval):
        """Set the interval for a timer with `name` to `interval`."""
        # it is the only timer right now.
        self.readoutTimer.setInterval(interval)

    @pyqtSlot(str)
    def sendSensorCommand(self, command):
        """Send a command to the sensors."""
        self.inputOutput.executeCommand(command)

    # OPERATION

    @pyqtSlot()
    def readTimeout(self):
        """Read the sensors and calculate a pid value."""
        data = self.inputOutput.getSensors()
        output = {}
        for key in self.pids.keys():
            for sensor in self.pidSensor[key]:
                try:
                    output[key] = self.pids[key](data[sensor])
                except KeyError:
                    pass
                else:
                    if self.pidState[key] == 2:
                        self.setOutput(key, output[key])
                    break  # Valid sensor found: stop loop.
        for key in output.keys():
            data[f'pidOutput{key}'] = output[key]
        self.data = data
        self.writeDatabase(data)

    @pyqtSlot(str, float)
    def setOutput(self, name, value):
        """Set the output with `name` to `value` if the state allows it."""
        try:
            if self.pidState[name]:
                self.inputOutput.setOutput(name, value)
        except KeyError:
            self.errors['outputName'] = f"Output '{name}' is unknown."

    def writeDatabase(self, data):
        """Write the iterable data in the database with the timestamp."""
        try:  # Check connection to the database and reconnect if necessary.
            database = self.database
        except AttributeError:
            tries = self.errors.get('databaseNone', -1) + 1
            if tries < 10:
                self.errors['databaseNone'] = tries
            else:
                self.connectDatabase()
                del self.errors['databaseNone']
            return  # No database connection existing.
        table = self.settings.value('database/table', defaultValue="", type=str)
        if table == "":
            self.errors['databaseTable'] = True
            return
        columns = "timestamp"
        for key in data.keys():
            columns += f", {key}"
        length = len(data)
        with database.cursor() as cursor:
            try:
                cursor.execute(f"INSERT INTO {table} ({columns}) VALUES (%s{', %s' * length})",
                               (datetime.datetime.now(), *data.values()))
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                self.connectDatabase()  # Connection lost, reconnect.
            except Exception as exc:
                self.errors['databaseWrite'] = f"Database error {type(exc).__name__}: {exc}."
                database.rollback()
            else:
                database.commit()


if __name__ == "__main__":
    """If called as a script, start the qt system and start the controller."""
    application = QtCore.QCoreApplication(sys.argv)
    controller = TemperatureController()
    application.exec()  # start the event loop
