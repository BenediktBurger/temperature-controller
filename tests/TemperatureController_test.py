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
    def __init__(self):
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
        assert controller.errors == {}

class Test_connectDatabase:
    def test_connectDatabase_close_existent(self, empty, replace_database, connection):
        empty.database = connection
        TemperatureController.TemperatureController.connectDatabase(empty)
        assert connection.open == False

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
        controller.pidSensor['0'] = '0'

    def test_no_pids(self, controller):
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_database == {'0': 0, '1': 1}

    def test_pid_without_sensor(self, controller, pid):
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.errors['pid0Sensor'] == True

    def test_pid_no_output(self, controller, pid_sensor):
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_database['output0'] == 0
        assert controller.test_output == {}

    def test_pid_output(self, controller, pid_sensor):
        controller.pidState['0'] = 2
        TemperatureController.TemperatureController.readTimeout(controller)
        assert controller.test_output['0'] == 0

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

    def test_no_database(self, writeDatabase, empty):
        writeDatabase(empty, {})
        # assert no error

    def test_no_table(self, controller, mock_settings, monkeypatch, writeDatabase):
        controller.database = 5
        writeDatabase(controller, {})
        assert 'databaseTable' in controller.errors.keys()

    def test_write_failure(self, writeDatabase, controller, mock_settings, database):
        controller.database = database
        controller.settings.setValue('database/table', "table")
        writeDatabase(controller, {'0': "fail", '1': "fail"})
        assert controller.database.rollbacked == True
        assert 'databaseWrite' in controller.errors.keys()

    @pytest.fixture
    def fill_database(self, writeDatabase, controller, mock_settings, database):
        controller.database = database
        controller.settings.setValue('database/table', "table")
        writeDatabase(controller, {'0': 0, '1': 1})

    def test_write_commited(self, controller, fill_database):
        assert controller.database.committed == True

    def test_write_text(self, controller, fill_database):
        assert controller.database.executed[0] == "INSERT INTO table (timestamp, 0, 1) VALUES (%s, %s, %s)"

    def test_write_value(self, controller, fill_database):
        _, *value = controller.database.executed[1]
        assert value == [0, 1]

