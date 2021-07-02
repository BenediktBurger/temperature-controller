#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the ioDefinition.py.

Created on Mon Jun 21 13:11:23 2021 by Benedikt Moneke
"""

# for tests
import pytest
from tinkerforge.ip_connection import Error as tfError

# file to test
from controllerData import ioDefinition



class Empty():
    pass


@pytest.fixture
def empty():
    raw = Empty()
    raw.readoutMethods = []
    return raw


@pytest.fixture
def skeleton(empty):
    """Just tinkerforge ready."""
    empty.tfCon = 0
    empty.tfDevices = {}
    empty.tfMap = {}
    return empty


@pytest.fixture
def returner(*args):
    return args


# Mock Classes for Tinkerforge Modules
class Mock_IPConnection:
    ENUMERATION_TYPE_CONNECTED = 0
    ENUMERATION_TYPE_DISCONNECTED = 3

    def disconnect(self):
        self.disconnected = True

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
        if voltage < 0:
            raise tfError(tfError.TIMEOUT, "Test error.")
        else:
            self.voltage = voltage


@pytest.fixture
def mock_tinkerforge(monkeypatch):
    def returner(*args):
        return args

    monkeypatch.setattr(ioDefinition, 'devices', {297: returner, 111: returner, 2115: returner}, False)
    monkeypatch.setattr(ioDefinition, "IPConnection", Mock_IPConnection, False)
    monkeypatch.setattr(ioDefinition, 'BrickHAT', Mock_BrickHAT, False)
    monkeypatch.setattr(ioDefinition, 'BrickletAirQuality', Mock_BrickletAirQuality, False)
    monkeypatch.setattr(ioDefinition, 'BrickletAnalogOutV3', Mock_BrickletAnalogOutV3, False)


@pytest.fixture
def tf_device_pars():
    """Tinkerforge device parameters."""
    # 0: uid, 1: connected_uid, 2: position, 3: hardware_version, 4: firmware_version, 5: device_identifier, 6: enumeration_type
    return ["abc", "def", "i", 0, 0, 111, 1]


@pytest.fixture
def timeout():
    def timingout():
        raise tfError(tfError.TIMEOUT, 'test')
    return timingout

@pytest.fixture
def controller(empty):
    empty.errors = {}
    return empty

@pytest.fixture
def skeletonP(skeleton, controller):
    skeleton.controller = controller
    return skeleton

# General and tinkerforge tests.
def test_setupTinkerforge_False(empty, monkeypatch):
    monkeypatch.setattr(ioDefinition, 'tf', False)
    ioDefinition.InputOutput.setupTinkerforge(empty)
    with pytest.raises(AttributeError):
        empty.tfDevices


@pytest.mark.parametrize('device_identifier, name', [(297, 'airQuality'),
                                                     (111, 'HAT'),
                                                     (2115, 'analogOut1')
                                                     ])
def test_deviceConnected(mock_tinkerforge, skeleton, tf_device_pars, device_identifier, name):
    tf_device_pars[5] = device_identifier
    uid = tf_device_pars[0]
    ioDefinition.InputOutput.deviceConnected(skeleton, *tf_device_pars)
    assert skeleton.tfDevices[uid] == (uid, 0)
    assert skeleton.tfMap[name] == uid

def test_deviceConnected_available(skeleton, mock_tinkerforge, tf_device_pars, capsys):
    tf_device_pars[6] = 0
    ioDefinition.InputOutput.deviceConnected(skeleton, *tf_device_pars)
    assert capsys.readouterr().out == "Device available: abc at i of type 111.\n"

class Test_deviceDisconnected:
    @pytest.fixture(autouse=True)
    def pars_modified(self, tf_device_pars):
        tf_device_pars[6] = Mock_IPConnection.ENUMERATION_TYPE_DISCONNECTED
        return tf_device_pars

    @pytest.fixture(autouse=True)
    def setup(self, skeleton, mock_tinkerforge, pars_modified):
        uid = pars_modified[0]
        skeleton.tfDevices[uid] = 5
        skeleton.tfMap['analogOut0'] = uid
        return skeleton

    @pytest.fixture
    def act(self, setup, pars_modified):
        ioDefinition.InputOutput.deviceConnected(setup, *pars_modified)
        return setup

    def test_device_list(self, setup, act):
        assert setup.tfDevices == {}

    def test_device_map(self, setup, act):
        assert setup.tfMap == {}

    def test_output(self, setup, capsys, pars_modified):
        ioDefinition.InputOutput.deviceConnected(setup, *pars_modified)
        assert capsys.readouterr().out == "Device abc disconnected.\n"


class Test_close:
    @pytest.fixture
    def clean(empty, connection):
        empty.rm = connection
        return empty

    def test_close_clean(self, clean):
        ioDefinition.InputOutput.close(clean)
        assert clean.rm.open == False

    def test_close_tf(self, clean):
        clean.tfCon = Mock_IPConnection()
        ioDefinition.InputOutput.close(clean)
        assert clean.tfCon.disconnected == True



def test_getSensors_Clean(empty):
    assert ioDefinition.InputOutput.getSensors(empty) == {}


def test_getSensors_TF(skeleton):
    skeleton.tfDevices['abc'] = Mock_BrickletAirQuality()
    skeleton.tfMap['airQuality'] = 'abc'
    assert ioDefinition.InputOutput.getSensors(skeleton) == {'airPressure': 5.0, 'airQuality': 100, 'humidity': 4.0, 'temperature': 3.0}


def test_getSensors_TF_connection_lost(skeleton, timeout):
    skeleton.tfDevices['abc'] = Mock_BrickletAirQuality()
    skeleton.tfDevices['abc'].get_all_values = timeout
    skeleton.tfMap['airQuality'] = 'abc'
    ioDefinition.InputOutput.getSensors(skeleton)
    assert 'abc' not in skeleton.tfDevices.keys()

def test_setOutput_Not_Connected(skeletonP, capsys):
    ioDefinition.InputOutput.setOutput(skeletonP, '1', 100)
    assert skeletonP.controller.errors['analogOut1']  == "Not connected."

def test_setOutput_connection_lost(skeleton):
    skeleton.tfDevices['ao3'] = Mock_BrickletAnalogOutV3()
    skeleton.tfMap['analogOut1'] = 'ao3'
    ioDefinition.InputOutput.setOutput(skeleton, '1', -1)
    assert 'ao3' not in skeleton.tfDevices.keys()

def test_setOutput(skeleton):
    skeleton.tfDevices['ao3'] = Mock_BrickletAnalogOutV3()
    skeleton.tfMap['analogOut1'] = 'ao3'
    ioDefinition.InputOutput.setOutput(skeleton, '1', 9)
    assert skeleton.tfDevices['ao3'].voltage == 9


def test_localReadout(empty):
    empty.readoutMethods = [lambda: {'local': 123}]
    assert ioDefinition.InputOutput.getSensors(empty) == {'local': 123}

