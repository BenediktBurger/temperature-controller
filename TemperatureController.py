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

from data import connectionData, listener, sensors  # file with the connection data in dictionaries: database = {'host': 'myres'...}.


class TemperatureController(QtCore.QObject):
    """The temperature controller itself."""
    stopSignal = QtCore.pyqtSignal()
    stopApplication = QtCore.pyqtSignal()

    def __init__(self):
        """Initialize the controller."""
        super().__init__()

        # Configure Settings
        application = QtCore.QCoreApplication.instance()
        application.organizationName = "NLOQO"
        application.applicationName = "TemperatureController"
        settings = QtCore.QSettings()

        # Objects like timers
        self.readoutTimer = QtCore.QTimer()
        self.readoutTimer.start(settings.value('readoutInterval', defaultValue=5000, type=int))
        self.threadpool = QtCore.QThreadPool()

        # Initialize sensors
        self.sensors = sensors.Sensors()

        # PID controllers
        self.pid1 = PID()
        self.pid2 = PID()
        self.pidSensors = {}
        self.setupPID(self.pid1, 'pid1')
        self.setupPID(self.pid2, 'pid2')

        # Configure the listener thread for listening intercom.
        self.setupListener()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.readTimeout)
        self.counter = 0
        self.timer.start(1000)
        self.connectDatabase()
        self.databaseTable = settings.value('database/table', defaultValue=0, type=int)

    def setupListener(self):
        """Setup the thread listening for intercom."""
        self.listenerThread = QtCore.QThread()
        self.listener = listener.Listener(threadpool=self.threadpool)
        self.listener.moveToThread(self.listenerThread)
        self.listenerThread.started.connect(self.listener.listen)
        self.listenerThread.start()
        # Listener Signals.
        self.listener.signals['stopController'].connect(self.stop)
        # TODO connections

    def setupPID(self, pid, name):
        """Configure the `pid` controller with `name`."""
        settings = QtCore.QSettings()
        settings.beginGroup(name)
        pid.output_limits = (0, 10)
        pid.Kp = settings.value('Kp', defaultValue=1, type=float)
        pid.Ki = settings.value('Ki', defaultValue=0, type=float)
        pid.Kd = settings.value('Kd', defaultValue=0, type=float)
        pid.setpoint = settings.value('setpoint', defaultValue=22.2, type=float)
        self.pidSensors[name] = settings.value('sensor', defaultValue="", type=str)

    @pyqtSlot()
    def stop(self):
        """Stop the controller and the application."""
        print("About to stop")
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

    def connectDatabase(self):
        """(Re)Establish a connection to the database for storing sensor data."""
        try:
            self.database.close()
        except AttributeError:
            pass  # no database present
        self.database = psycopg2.connect(**connectionData.database)

    @pyqtSlot()
    def readTimeout(self):
        """Read the sensors and calculate a pid value."""
        data = self.sensors.read()
        output = [self.pid1(data[self.pidSensors['pid1']]),
                  self.pid2(data[self.pidSensors['pid2']])]
        # TODO use pid values
        self.writeDatabase(data + output)  # TODO during testing only + output

    def writeDatabase(self, data):
        """Write the iterable data in the database with the timestamp."""
        # TODO add error handling and backup storage.
        length = len(data)
        with self.database.cursor() as cursor:
            try:
                cursor.execute(f"INSERT INTO {self.databaseTable} VALUES (%s{', %s' * length})",
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
