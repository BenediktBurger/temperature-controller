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
from tinkerforge.ip_connection import IPConnection, Error as tkError
from tinkerforge.brick_hat import BrickHAT
from tinkerforge.bricklet_analog_out_v3 import BrickletAnalogOutV3

from controllerData import connectionData, listener, sensors  # file with the connection data in dictionaries: database = {'host': 'myres'...}.


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
        self.pids['0'] = PID()
        self.pids['1'] = PID()
        self.pidSensors = {}
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
        self.listener = listener.Listener(port=settings.value('listener/port', defaultValue=22001, type=int),
                                          threadpool=self.threadpool, controller=self)
        self.listener.moveToThread(self.listenerThread)
        self.listenerThread.started.connect(self.listener.listen)
        self.listenerThread.start()
        # Listener Signals.
        #self.listener.signals['stopController'].connect(self.stop)
        self.listener.signals.stopController.connect(self.stop)
        self.listener.signals.pidChanged.connect(self.setupPID)
        self.listener.signals.timerChanged.connect(self.setTimerInterval)
        # TODO connections

    @pyqtSlot(str)
    def setupPID(self, id):
        """Configure the pid controller with `id`."""
        print("setupPID called")  # TODO debug
        pid = self.pids[id]
        settings = QtCore.QSettings()
        settings.beginGroup(f'pid{id}')
        pid.output_limits = (settings.value('lowerLimit', defaultValue=None, type=float),
                             settings.value('upperLimit', defaultValue=None, type=float))
        pid.Kp = settings.value('Kp', defaultValue=1, type=float)
        pid.Ki = settings.value('Ki', defaultValue=0, type=float)
        pid.Kd = settings.value('Kd', defaultValue=0, type=float)
        pid.setpoint = settings.value('setpoint', defaultValue=22.2, type=float)
        pid.set_auto_mode(settings.value('autoMode', defaultValue=True, type=bool),
                          settings.value('lastOutput', defaultValue=None, type=float))
        self.pidSensors[id] = settings.value('sensor', defaultValue=0, type=int)
        print("setupPID finished")  # TODO debug

    def setupTinkerforge(self):
        """Create the tinkerforge HAT and bricklets."""
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
        self.listenerThread.quit()
        self.listenerThread.wait()

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

    def setTimerInterval(self, id, interval):
        """Set the interval for a timer with `id` to `interval`."""
        # it is the only timer right now.
        self.readoutTimer.setInterval(interval)

    # OPERATION

    @pyqtSlot()
    def readTimeout(self):
        """Read the sensors and calculate a pid value."""
        data = self.sensors.read()
        output = {}
        for key in self.pids.keys():
            output[key] = self.pids[key](data[self.pidSensors[key]])
            # TODO send it to the output. Implement manual mode
        self.writeDatabase(data + [output['0']])  # TODO during testing only + output

    def writeDatabase(self, data):
        """Write the iterable data in the database with the timestamp."""
        # TODO add error handling and backup storage.
        table = self.settings.value('database/table', defaultValue="", type=str)
        if table == "":
            print("No database table configured.")
            self.errors['database'] = "Table not configured."
            return
        length = len(data)
        with self.database.cursor() as cursor:
            try:
                cursor.execute(f"INSERT INTO {table} VALUES (%s{', %s' * length})",
                               (datetime.datetime.now(), *data))
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
