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
try:
    from tinkerforge.ip_connection import IPConnection, Error as tkError
    from tinkerforge.brick_hat import BrickHAT
    from tinkerforge.bricklet_analog_out_v3 import BrickletAnalogOutV3
except ModuleNotFoundError:
    tk = False
else:
    tk = True

from controllerData import connectionData  # file with the connection data in dictionaries: database = {'host': 'myres'...}.
from controllerData import listener, sensors


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
        self.errors = {}  # error dictionary

        # Create objects like timers
        self.readoutTimer = QtCore.QTimer()
        self.threadpool = QtCore.QThreadPool()

        # Create the tinkerforge connection
        self.setupTinkerforge()

        # Initialize sensors
        self.sensors = sensors.Sensors()

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
        pid.output_limits = (settings.value('lowerLimit', defaultValue=None, type=float),
                             settings.value('upperLimit', defaultValue=None, type=float))
        pid.Kp = settings.value('Kp', defaultValue=1, type=float)
        pid.Ki = settings.value('Ki', defaultValue=0, type=float)
        pid.Kd = settings.value('Kd', defaultValue=0, type=float)
        pid.setpoint = settings.value('setpoint', defaultValue=22.2, type=float)
        pid.set_auto_mode(settings.value('autoMode', defaultValue=True, type=bool),
                          settings.value('lastOutput', defaultValue=None, type=float))
        self.pidSensor[name] = settings.value('sensor', defaultValue="", type=str)
        self.pidState[name] = settings.value('state', defaultValue=0, type=int)

    def setupTinkerforge(self):
        """Create the tinkerforge HAT and bricklets."""
        if not tk:
            return
        self.tks = {}
        settings = QtCore.QSettings()
        settings.beginGroup('tk')
        ipcon = IPConnection()
        ipcon.connect("localhost", 4223)  # values for local installation
        try:
            self.tks['connection'] = ipcon
            self.tks['hat'] = BrickHAT(settings.value('hat', defaultValue=None, type=str), ipcon)
            self.tks['analogOut0'] = BrickletAnalogOutV3(settings.value('analogOut0', defaultValue=None, type=str), ipcon)
            self.tks['analogOut1'] = BrickletAnalogOutV3(settings.value('analogOut1', defaultValue=None, type=str), ipcon)
        except tkError as exc:
            print(f"{type(exc.__class__)}:{exc}")

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
        print("Listener told to stop")
        self.stopSignal.emit()
        self.listenerThread.wait()
        print("Listenerthread stopped")

        # Close the sensor and database
        self.sensors.close()
        self.database.close()

        # Stop the Application.
        if qtVersion == 6:
            connectionType = QtCore.Qt.ConnectionType.QueuedConnection
        else:
            connectionType = QtCore.Qt.QueuedConnection
        self.stopApplication.connect(QtCore.QCoreApplication.instance().quit, type=connectionType)
        self.stopApplication.emit()
        print("Stopped")

    # CONNECTIONS

    def connectDatabase(self):
        """(Re)Establish a connection to the database for storing sensor data."""
        try:
            self.database.close()
        except AttributeError:
            pass  # no database present
        self.database = psycopg2.connect(**connectionData.database)

    # CONFIG

    def setTimerInterval(self, name, interval):
        """Set the interval for a timer with `name` to `interval`."""
        # it is the only timer right now.
        self.readoutTimer.setInterval(interval)

    @pyqtSlot(str)
    def sendSensorCommand(self, command):
        """Send a command to the sensors."""
        try:
            self.sensors.sendCommand(command)
        except AttributeError:
            print("Sensor cannot be configured.")

    # OPERATION

    @pyqtSlot()
    def readTimeout(self):
        """Read the sensors and calculate a pid value."""
        data = self.sensors.read()
        output = {}
        for key in self.pids.keys():
            try:
                output[key] = self.pids[key](data[self.pidSensor[key]])
            except KeyError:
                print(f"Pid {key} does not have a valid sensor name.")
            else:
                if self.pidState[key] == 2:
                    self.setOutput(key, output[key])
        try:  # TODO during testing only + output
            data['output'] = output['0']
        except KeyError:
            pass  # no output calculated
        self.writeDatabase(data)

    @pyqtSlot(str, float)
    def setOutput(self, name, value):
        """Set the output with `name` to `value`."""
        if name == '0' and self.pidState[name]:
            self.sensors.setSetpoint(value)

    def writeDatabase(self, data):
        """Write the iterable data in the database with the timestamp."""
        # TODO add error handling and backup storage.
        table = self.settings.value('database/table', defaultValue="", type=str)
        if table == "":
            print("No database table configured.")
            self.errors['database'] = "Table not configured."
            return
        columns = "timestamp"
        for key in data.keys():
            columns += f", {key}"
        length = len(data)
        with self.database.cursor() as cursor:
            try:
                cursor.execute(f"INSERT INTO {table} ({columns}) VALUES (%s{', %s' * length})",
                               (datetime.datetime.now(), *data.values()))
            except Exception as exc:
                print(type(exc.__class__), exc)
                self.database.rollback()
            else:
                self.database.commit()


if __name__ == "__main__":
    """If called as a script, start the qt system and start the controller."""
    application = QtCore.QCoreApplication(sys.argv)
    controller = TemperatureController()
    application.exec()  # start the event loop
