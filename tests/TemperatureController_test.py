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

from controllerData import listener

# file to be tested
import TemperatureController


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

class Mock_Listener:
    def __init__(self, host=None, port=-1, threadpool=None, controller=None):
        self.signals = listener.ListenerSignals()

    def listen(self):
        pass

    def moveToThread(self, name=""):
        pass

class Mock_InputOutput:
    def __init__(self):
        pass
    def close(self):
        pass

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

@pytest.fixture
def controller(replace_application, replace_listener, replace_io, replace_database):
    contr = TemperatureController.TemperatureController()
    yield contr
    contr.stop()

class Test_Controller_init:
    def test_init(self, controller):
        assert controller.errors == {}
