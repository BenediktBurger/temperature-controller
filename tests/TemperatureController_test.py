#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the TemperatureController.py file.

Created on Sat Jun 19 08:17:59 2021 by Benedikt Moneke
"""

# the test framework
import pytest

# for fixtures
from PyQt5 import QtCore
import psycopg2
from simple_pid import PID

from controllerData import connectionData, listener

# file to be tested
import TemperatureController


class Mock_Controller:
    def __init__(self):
        self.errors = {}
        self.pids = {}
        self.pidState = {}
        self.pidSensor = {}
        self.test_output = {}

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
        self.signals = listener.ListenerSignals()

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
    def controller(self, replace_application, replace_listener, replace_io, replace_database):
        contr = TemperatureController.TemperatureController()
        yield contr
        contr.stop()

    def test_init(self, controller):
        assert controller.errors == {'pid0Sensor': True, 'pid1Sensor': True}


class Test_connectDatabase:
    def test_connectDatabase_close_existent(self, empty, replace_database, connection):
        empty.database = connection
        TemperatureController.TemperatureController.connectDatabase(empty)
        assert not connection.open

    def test_connectDatabase_load_config(self, empty, monkeypatch):
        monkeypatch.setattr('psycopg2.connect', lambda **kwargs: kwargs)
        TemperatureController.TemperatureController.connectDatabase(empty)
        assert empty.database == connectionData.database

    def test_connectDatabase_fail(self, controller, monkeypatch):
        def raising(**kwargs):
            raise TypeError('test')
        monkeypatch.setattr('psycopg2.connect', raising)
        TemperatureController.TemperatureController.connectDatabase(controller)
        assert controller.errors['database'] == "Database connection error TypeError: test."
        assert not hasattr(controller, 'database')


class Test_setupPID_defaults:
    @pytest.fixture(autouse=True)
    def pid(self, controller):
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

    def test_sensor_error(self, controller):
        assert controller.errors['pid0Sensor']


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
        settings.setValue('upperLimit', 10)
        settings.setValue('Kp', 5)
        settings.setValue('Ki', 4)
        settings.setValue('Kd', 3)
        settings.setValue('setpoint', 15)
        settings.setValue('autoMode', True)
        settings.setValue('lastOutput', 2)
        settings.setValue('state', 1)
        settings.setValue('sensor', "sensor0, sensor1")
        settings.endGroup()
        monkeypatch.setattr('PyQt5.QtCore.QSettings', lambda: settings)
        yield
        settings.clear()

    @pytest.fixture(autouse=True)
    def setupPID(self, controller, pid, sets):
        return TemperatureController.TemperatureController.setupPID(controller, '0')

    def test_limits(self, pid):
        assert pid.output_limits == (0, 10)

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
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_output['0'] == 0

    def test_pid_second_sensor(self, controller, pid):
        controller.pidSensor['0'] = ['missing', '1']
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_database['pidOutput0'] == 1

    def test_pid_no_sensors(self, controller, pid):
        controller.pidSensor['0'] = ['missing']
        assert not hasattr(controller, 'test_database')


def test_setOutput_invalid_name(controller):
    TemperatureController.TemperatureController.setOutput(controller, '3', 5)
    assert 'outputName' in controller.errors.keys()


def test_setOutput_state_disabled(controller, mock_io):
    TemperatureController.TemperatureController.setOutput(controller, '0', 5)
    assert controller.inputOutput.test_output == {}


def test_setOutput(controller, mock_io):
    controller.pidState['0'] = True
    TemperatureController.TemperatureController.setOutput(controller, '0', 5)
    assert controller.inputOutput.test_output['0'] == 5


class Test_writeDatabase:
    @pytest.fixture
    def writeDatabase(self):
        return TemperatureController.TemperatureController.writeDatabase

    @pytest.fixture
    def mock_connect(self, controller):
        def connectDatabase():
            controller.errors['test'] = True
        controller.connectDatabase = connectDatabase

    def test_no_database(self, writeDatabase, controller):
        writeDatabase(controller, {})
        assert controller.errors['databaseNone'] == 0

    def test_no_database_reconnect(self, writeDatabase, controller, mock_connect):
        controller.errors['databaseNone'] = 9
        writeDatabase(controller, {})
        assert controller.errors['test']
        assert 'databaseNone' not in controller.errors

    def test_no_table(self, controller, mock_settings, monkeypatch, writeDatabase):
        controller.database = 5
        writeDatabase(controller, {})
        assert 'databaseTable' in controller.errors.keys()

    def test_write_failure(self, writeDatabase, controller, mock_settings, database):
        controller.database = database
        controller.settings.setValue('database/table', "table")
        writeDatabase(controller, {'0': "fail", '1': "fail"})
        assert controller.database.rollbacked
        assert 'databaseWrite' in controller.errors.keys()

    def test_connection_error(self, controller, writeDatabase, mock_settings, database, mock_connect):
        controller.database = database
        controller.settings.setValue('database/table', "table")
        writeDatabase(controller, {'0': "raise"})
        assert controller.errors['test']

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
