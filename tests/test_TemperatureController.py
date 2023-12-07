#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the TemperatureController.py file.

Created on Sat Jun 19 08:17:59 2021 by Benedikt Moneke
"""

# the test framework
import pytest

# for fixtures
try:  # Qt for nice effects.
    from PyQt6 import QtCore
    pyqt = 6
except ModuleNotFoundError:
    from PyQt5 import QtCore
    pyqt = 5
import psycopg2
from simple_pid import PID

from controllerData import connectionData, listener

# file to be tested
import TemperatureController


class Mock_Controller(TemperatureController.TemperatureController):
    def __init__(self):
        self.errors = {}
        self.pids = {}
        self.pidState = {}
        self.pidSensor = {}
        self.pidOutput = {}
        self.test_output = {}

        # General config
        self.data = {}  # Current data dictionary.
        self.last_value_set = 0
        self.tries = 0
        self.settings = QtCore.QSettings()

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

        self.publisher = lambda v: v

    def __del__(self):
        pass

    def setOutput(self, name, value):
        self.test_output[name] = value

    def writeDatabase(self, data):
        self.test_database = data


class Mock_App:
    def __init__(self):
        self.organizationName = ""
        self.applicationName = ""

    def setOrganizationName(self, name):
        self.organizationName = name

    def setApplicationName(self, name):
        self.applicationName = name

    def quit(self):
        pass


class Mock_App_Instance:
    def instance():
        return Mock_App()


class Mock_Settings:
    def __init__(self, data={}):
        self.data = data  # Dictionary for settings.

    def value(self, key, defaultValue=None, type=None):
        try:
            return self.data[key]
        except KeyError:
            return defaultValue

    def setValue(self, key, value):
        self.data[key] = value


class Mock_Listener:
    def __init__(self, host=None, port=-1, threadpool=None, controller=None):
        self.signals = listener.Listener.ListenerSignals()

    def listen(self):
        pass

    def moveToThread(self, name=""):
        pass


class Mock_InputOutput:
    def __init__(self, controller=None):
        self.test_output = {}

    def close(self):
        pass

    def executeCommand(self, command):
        assert command == "valid", "Invalid command"

    def getSensors(self):
        return {'0': 0, '1': 1}

    def setOutput(self, name, value):
        self.test_output[name] = value


class Cursor:
    def __init__(self, parent):
        self.parent = parent

    def __enter__(self):
        return self

    def execute(self, text, data):
        _, *values = data
        if "fail" == values[0]:
            raise TypeError
        elif "raise" == values[0]:
            raise psycopg2.InterfaceError
        else:
            self.parent.executed = [text, data]

    def __exit__(self, *args, **kwargs):
        pass


class Mock_Database:
    def close(self):
        pass

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rollbacked = True


@pytest.fixture
def controller():
    return Mock_Controller()


@pytest.fixture
def mock_io(controller):
    controller.inputOutput = Mock_InputOutput()
    return controller


@pytest.fixture
def mock_settings(controller):
    controller.settings = Mock_Settings()
    return controller


@pytest.fixture
def database():
    return Mock_Database()


@pytest.fixture
def replace_application(monkeypatch):
    monkeypatch.setattr(QtCore, "QCoreApplication", Mock_App_Instance)


@pytest.fixture
def replace_listener(monkeypatch):
    monkeypatch.setattr("controllerData.listener.Listener", Mock_Listener)


@pytest.fixture
def replace_io(monkeypatch):
    monkeypatch.setattr("controllerData.ioDefinition.InputOutput", Mock_InputOutput)


@pytest.fixture
def replace_database(monkeypatch, connection):
    monkeypatch.setattr('psycopg2.connect', lambda **kwargs: connection)


class Test_Controller_init:
    @pytest.fixture
    def controller(self, replace_application, replace_listener, replace_io,
                   replace_database):
        contr = TemperatureController.TemperatureController()
        yield contr
        contr.stop()

    def test_errors(self, controller, caplog):
        assert controller.errors == {'pid0Sensor': True, 'pid1Sensor': True}

    def default_pids(self, controller):
        assert controller.pids.keys() == ('0', '1')


class Test_connectDatabase:
    def test_connectDatabase_close_existent(self, empty, replace_database, connection):
        empty.database = connection
        TemperatureController.TemperatureController.connectDatabase(empty)
        assert not connection.open

    def test_connectDatabase_load_config(self, empty, monkeypatch):
        monkeypatch.setattr('psycopg2.connect', lambda **kwargs: kwargs)
        TemperatureController.TemperatureController.connectDatabase(empty)
        del empty.database['connect_timeout']
        assert empty.database == connectionData.database

    def test_connectDatabase_fail(self, controller, monkeypatch, caplog):
        def raising(**kwargs):
            raise TypeError('test')
        monkeypatch.setattr('psycopg2.connect', raising)
        TemperatureController.TemperatureController.connectDatabase(controller)
        assert "Database connection error TypeError: test." in caplog.text
        assert not hasattr(controller, 'database')


class Test_setupPID_defaults:
    @pytest.fixture(autouse=True)
    def pid(self, controller, caplog):
        caplog.set_level(0)
        controller.pids['0'] = PID(auto_mode=False)
        return controller.pids['0']

    @pytest.fixture(autouse=True)
    def setupPID(self, controller, pid):
        return TemperatureController.TemperatureController.setupPID(controller, '0')

    def test_limits(self, pid):
        assert pid.output_limits == (None, None)

    def test_tunings(self, pid):
        assert pid.tunings == (1, 0, 0)  # Kp, Ki, Kd

    def test_setpoint(self, pid):
        assert pid.setpoint == 22.2

    def test_auto_mode(self, pid):
        assert pid.auto_mode

    def test_integral(self, pid):
        assert pid._integral == 0

    def test_state(self, controller):
        assert controller.pidState['0'] == 0

    def test_sensor_error(self, controller, caplog):
        assert "PID '0' does not have sensors configured." in caplog.text


class Test_setupPID_settings:
    @pytest.fixture(autouse=True)
    def pid(self, controller):
        controller.pids['0'] = PID(auto_mode=False)
        return controller.pids['0']

    @pytest.fixture(autouse=True)
    def sets(self, monkeypatch):
        settings = QtCore.QSettings('NLOQO', "tests")
        settings.beginGroup('pid0')
        settings.setValue('lowerLimit', 0)
        settings.setValue('lowerLimitNone', False)
        settings.setValue('upperLimit', 10)
        settings.setValue('upperLimitNone', True)
        settings.setValue('Kp', 5)
        settings.setValue('Ki', 4)
        settings.setValue('Kd', 3)
        settings.setValue('setpoint', 15)
        settings.setValue('autoMode', True)
        settings.setValue('lastOutput', 2)
        settings.setValue('state', 1)
        settings.setValue('sensor', "sensor0, sensor1")
        settings.endGroup()
        if pyqt == 5:
            monkeypatch.setattr('PyQt5.QtCore.QSettings', lambda: settings)
        if pyqt == 6:
            monkeypatch.setattr('PyQt6.QtCore.QSettings', lambda: settings)
        yield
        settings.clear()

    @pytest.fixture(autouse=True)
    def setupPID(self, controller, pid, sets):
        return TemperatureController.TemperatureController.setupPID(controller, '0')

    def test_limits(self, pid):
        assert pid.output_limits == (0, None)

    def test_tunings(self, pid):
        assert pid.tunings == (5, 4, 3)  # Kp, Ki, Kd

    def test_setpoint(self, pid):
        assert pid.setpoint == 15

    def test_auto_mode(self, pid):
        assert pid.auto_mode

    def test_integral(self, pid):
        assert pid._integral == 2

    def test_state(self, controller):
        assert controller.pidState['0'] == 1

    def test_sensor_error(self, controller):
        assert controller.pidSensor['0'] == ["sensor0", "sensor1"]


def test_sendSensorCommand(controller, mock_io):
    TemperatureController.TemperatureController.sendSensorCommand(controller, 'valid')
    # assert no error


class Test_readoutTimeout:
    @pytest.fixture(autouse=True)
    def io(self, controller):
        controller.inputOutput = Mock_InputOutput()

    @pytest.fixture
    def pid(self, controller):
        controller.pids['0'] = lambda value: value
        controller.pidState['0'] = 0

    @pytest.fixture
    def pid_sensor(self, controller, pid):
        controller.pidSensor['0'] = ['0', '1']

    def test_no_pids(self, controller):
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_database == {'0': 0, '1': 1}

    def test_pid_no_output(self, controller, pid_sensor):
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_database['pidOutput0'] == 0
        assert controller.test_output == {}

    def test_pid_output(self, controller, pid_sensor):
        controller.pidState['0'] = 2
        controller.pidOutput['0'] = 'out0'
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_output['out0'] == 0

    def test_pid_second_sensor(self, controller, pid):
        controller.pidSensor['0'] = ['missing', '1']
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_database['pidOutput0'] == 1

    def test_pid_no_sensors(self, controller, pid, caplog):
        controller.pidSensor['0'] = ['missing']
        caplog.set_level(0)
        TemperatureController.TemperatureController.readTimeout(controller)
        assert "PID '0' does not have sensors configured." in caplog.text


class Test_setOutput:
    def test_invalid_name(self, controller, caplog):
        class Raising_IO:
            def setOutput(self, *args):
                raise KeyError
        controller.inputOutput = Raising_IO()
        TemperatureController.TemperatureController.setOutput(controller, 'out3', 5)
        assert "Output 'out3' is unknown." in caplog.text

    def test_setOutput(self, mock_io):
        controller = mock_io
        controller.pidState['0'] = True
        controller.pidOutput['0'] = "out0"
        TemperatureController.TemperatureController.setOutput(controller, 'out0', 5)
        assert controller.inputOutput.test_output['out0'] == 5


class Test_writeDatabase:
    @pytest.fixture
    def writeDatabase(self):
        return TemperatureController.TemperatureController.writeDatabase

    @pytest.fixture
    def mock_connect(self, controller, caplog):
        # TODO fix, as errors does not exist anymore
        def connectDatabase():
            controller.errors['test'] = True
        controller.connectDatabase = connectDatabase
        assert "PID '0' does not have sensors configured" in caplog.text

    def test_no_database(self, writeDatabase, controller):
        writeDatabase(controller, {})
        assert controller.tries == 0

    def test_no_database_reconnect(self, writeDatabase, controller, mock_connect, caplog):
        controller.tries = 9
        writeDatabase(controller, {})
        assert "no_database" in caplog.text

    def test_no_table(self, controller, mock_settings, monkeypatch, writeDatabase, caplog):
        controller.database = 5
        writeDatabase(controller, {})
        assert "No database table" in caplog.text

    def test_write_failure(self, writeDatabase, controller, mock_settings, database, caplog):
        controller.database = database
        controller.settings.setValue('database/table', "table")
        writeDatabase(controller, {'0': "fail", '1': "fail"})
        assert controller.database.rollbacked
        assert "Database write error." in caplog.text

    def test_connection_error(self, controller, writeDatabase, mock_settings, database, mock_connect, caplog):
        controller.database = database
        controller.settings.setValue('database/table', "table")
        writeDatabase(controller, {'0': "raise"})
        assert "xyz" in caplog.text

    @pytest.fixture
    def fill_database(self, writeDatabase, controller, mock_settings, database):
        controller.database = database
        controller.settings.setValue('database/table', "table")
        writeDatabase(controller, {'0': 0, '1': 1})

    def test_write_commited(self, controller, fill_database):
        assert controller.database.committed

    def test_write_text(self, controller, fill_database):
        assert controller.database.executed[0] == "INSERT INTO table (timestamp, 0, 1) VALUES (%s, %s, %s)"

    def test_write_value(self, controller, fill_database):
        _, *value = controller.database.executed[1]
        assert value == [0, 1]
