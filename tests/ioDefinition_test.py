#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the ioDefinition.py

Created on Mon Jun 21 13:11:23 2021

@author: moneke
"""

# for tests
import pytest
#import pytest-qt
import sys
sys.path.append('C:/Users/moneke/temperature-controller')

# auxiliary for fixtures
#import pickle
#from devices import intercom

# file to test
from controllerData import ioDefinition


@pytest.fixture
def io():
    return ioDefinition.InputOutput()


class raw():
    pass


@pytest.fixture
def empty():
    return raw()


class Mock_InputOutput:
    def __init__(self):
        self.tfCon = 0
        self.tfDevices = {}
        self.tfMap = {}


@pytest.fixture
def skeleton():
    return Mock_InputOutput()


@pytest.fixture
def returner(*args):
    return args


class Mock_IPConnection:
    ENUMERATION_TYPE_DISCONNECTED = 3


class Mock_BrickHAT:
    DEVICE_IDENTIFIER = 111


class Mock_BrickletAirQuality:
    DEVICE_IDENTIFIER = 297

    def get_all_values(self):
        return (100, 200, 300, 400, 500)


class Mock_BrickletAnalogOutV3:
    DEVICE_IDENTIFIER = 2115

    def __init__(self):
        self.voltage = 0

    def set_output_voltage(self, voltage):
        self.voltage = voltage


def test_setupTinkerforge_False(empty):
    tf = False
    ioDefinition.InputOutput.setupTinkerforge(empty)
    with pytest.raises(AttributeError):
        empty.tfDevices


@pytest.mark.parametrize('device_identifier, name', [(297, 'airQuality'),
                                                     (111, 'HAT'),
                                                     (2115, 'analogOut1')
                                                     ])
def test_deviceConnected(monkeypatch, skeleton, device_identifier, name):
    uid = "abc"
    connected_uid = "def"
    position = "i"
    hardware_version = 0
    firmware_version = 0
    enumeration_type = 1

    def returner(*args):
        return args

    monkeypatch.setattr(ioDefinition, 'devices', {297: returner, 111: returner, 2115: returner}, False)
    monkeypatch.setattr(ioDefinition, "IPConnection", Mock_IPConnection, False)
    monkeypatch.setattr(ioDefinition, 'BrickHAT', Mock_BrickHAT, False)
    monkeypatch.setattr(ioDefinition, 'BrickletAirQuality', Mock_BrickletAirQuality, False)
    monkeypatch.setattr(ioDefinition, 'BrickletAnalogOutV3', Mock_BrickletAnalogOutV3, False)
    ioDefinition.InputOutput.deviceConnected(skeleton, uid, connected_uid, position, hardware_version, firmware_version, device_identifier, enumeration_type)
    assert skeleton.tfDevices[uid] == (uid, 0)
    assert skeleton.tfMap[name] == uid


def test_deviceDisconnected(skeleton, monkeypatch):
    uid = 'abc'
    connected_uid = "def"
    position = "i"
    hardware_version = 0
    firmware_version = 0
    enumeration_type = 3
    device_identifier = 0
    skeleton.tfDevices[uid] = 5
    skeleton.tfMap['analogOut0'] = uid
    monkeypatch.setattr(ioDefinition, "IPConnection", Mock_IPConnection, False)
    ioDefinition.InputOutput.deviceConnected(skeleton, uid, connected_uid, position, hardware_version, firmware_version, device_identifier, enumeration_type)
    assert skeleton.tfDevices == {}
    assert skeleton.tfMap == {}

def test_getSensors_Clean(empty):
    empty.getArduino = lambda: {}
    assert ioDefinition.InputOutput.getSensors(empty) == {}


def test_getSensors_TF(skeleton, monkeypatch):
    skeleton.tfDevices['abc'] = Mock_BrickletAirQuality()
    skeleton.tfMap['airQuality'] = 'abc'
    skeleton.getArduino = lambda: {}
    assert ioDefinition.InputOutput.getSensors(skeleton) == {'airPressure': 5.0, 'airQuality': 100, 'humidity': 4.0, 'temperature': 3.0}


def test_setOutput_Too_High(skeleton, capsys):
    ioDefinition.InputOutput.setOutput(skeleton, '1', 15000)
    assert capsys.readouterr().out == "Maximum voltage 12 V.\n"


def test_setOutput_Not_Connected(skeleton, capsys):
    ioDefinition.InputOutput.setOutput(skeleton, '1', 100)
    assert capsys.readouterr().out == "analogOut1 is not connected.\n"


def test_setOutput(skeleton):
    skeleton.tfDevices['ao3'] = Mock_BrickletAnalogOutV3()
    skeleton.tfMap['analogOut1'] = 'ao3'
    ioDefinition.InputOutput.setOutput(skeleton, '1', 9)
    assert skeleton.tfDevices['ao3'].voltage == 9


