#!/usr/bin/env python3
"""
Main file of the temperature controller for the lab.

Created on Mon Jun 14 11:12:51 2021 by Benedikt Moneke
"""

import datetime
import logging
import sys
import time

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

# local packages
from controllerData import connectionData    # Data to connect to database.
from controllerData import listener, ioDefinition

log = logging.getLogger("TemperatureController")
log.addHandler(logging.StreamHandler())  # log to stderr
log.setLevel(logging.INFO)
# Nothing yet marked as critical
# critical_handler = logging.FileHandler("log.txt")
# critical_handler.setLevel(logging.CRITICAL)
# critical_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
# log.addHandler(critical_handler)


class ListHandler(logging.Handler):
    """Store log entries in a list of strings.

    :param length: Maximum length of entries in the list, rotating buffer system.
        If None, keep all.
    """

    def __init__(self, length=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = []
        self.length = length

    def emit(self, record):
        if self.length is not None and len(self.log) >= self.length:
            self.log.pop(0)
        try:
            self.log.append(self.format(record))
        except Exception:
            self.handleError(record)

    def reset(self):
        """Clear the internal log."""
        self.log.clear()


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
        self.data = {}  # Current data dictionary.
        self.last_value_set = time.time()
        self.tries = 0

        # Store log in a list
        self.log = ListHandler(100)
        self.log.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        log.addHandler(self.log)

        # Create objects like timers
        self.readoutTimer = QtCore.QTimer()
        self.threadpool = QtCore.QThreadPool()

        # Initialize sensors
        self.inputOutput = ioDefinition.InputOutput(controller=self)

        # PID controllers
        self.pids = {}
        for i in range(self.settings.value('pids', defaultValue=2, type=int)):
            self.pids[str(i)] = PID(auto_mode=False)
            # auto_mode false, in order to start with the last value.
        self.pidSensor = {}  # the main sensor of the PID
        self.pidState = {}  # state of the corresponding output: 0 off, 1 manual, 2 pid
        self.pidOutput = {}  # Output device of the pid.
        for key in self.pids.keys():
            self.setupPID(key)

        # Configure the listener thread for listening intercom.
        self.setupListener(settings)

        self.connectDatabase()

        # Configure readoutTimer
        self.readoutTimer.start(settings.value('readoutInterval', 5000, int))
        self.readoutTimer.timeout.connect(self.readTimeout)
        log.info("Temperature Controller initialized")

    def __del__(self):
        log.removeHandler(self.log)

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
        pid.output_limits = (
            None if settings.value('lowerLimitNone', True, bool) else settings.value('lowerLimit', type=float),
            None if settings.value('upperLimitNone', True, bool) else settings.value('upperLimit', type=float))
        pid.Kp = settings.value('Kp', defaultValue=1, type=float)
        pid.Ki = settings.value('Ki', defaultValue=0, type=float)
        pid.Kd = settings.value('Kd', defaultValue=0, type=float)
        pid.setpoint = settings.value('setpoint', 22.2, type=float)
        pid.set_auto_mode(settings.value('autoMode', True, type=bool),
                          settings.value('lastOutput', 0, type=float))
        self.pidState[name] = settings.value('state', defaultValue=0, type=int)
        sensors = settings.value('sensor', type=str).replace(' ', '').split(',')
        if sensors == ['']:
            log.warning(f"PID '{name}' does not have sensors configured.")
        self.pidSensor[name] = sensors
        self.pidOutput[name] = settings.value('output', f"out{name}", str)

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
        self.stopApplication.connect(QtCore.QCoreApplication.instance().quit,
                                     type=connectionType)
        self.stopApplication.emit()
        log.info("Stopped.")

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
            log.exception("Database connection error.", exc_info=exc)

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
                        self.setOutput(self.pidOutput[key], output[key])
                        if self.last_value_set + 60 < time.time():
                            self.settings.setValue(f"pid{key}/lastOutput",
                                                   output[key])
                            pass
                    break  # Valid sensor found: stop loop.
        for key in output.keys():
            data[f'pidOutput{key}'] = output[key]
        self.data = data
        self.writeDatabase(data)

    @pyqtSlot(str, float)
    def setOutput(self, name, value):
        """Set the output with `name` to `value` if the state allows it."""
        try:
            self.inputOutput.setOutput(name, value)
        except KeyError:
            log.warning(f"Output '{name}' is unknown.")

    def writeDatabase(self, data):
        """Write the iterable data in the database with the timestamp."""
        try:  # Check connection to the database and reconnect if necessary.
            database = self.database
        except AttributeError:
            if self.tries < 10:
                self.tries += 1
            else:
                self.connectDatabase()
                self.tries = 0
            return  # No database connection existing.
        table = self.settings.value('database/table', defaultValue="", type=str)
        if table == "":
            log.warning("No database table is configured.")
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
                log.exception("Database write error.", exc_info=exc)
                database.rollback()
            else:
                database.commit()


if __name__ == "__main__":
    """If called as a script, start the qt system and start the controller."""
    application = QtCore.QCoreApplication(sys.argv)
    controller = TemperatureController()
    application.exec()  # start the event loop
