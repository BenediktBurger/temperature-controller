#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the ioDefinition.py.

Created on Mon Jun 21 13:11:23 2021 by Benedikt Moneke
"""

# for tests
import logging
import pytest
try:
    from tinkerforge.ip_connection import Error as tfError
except ModuleNotFoundError:
    tf = False
else:
    tf = True


# file to test
from controllerData import ioDefinition
from controllerData.ioDefinition import sensors  # type: ignore


ioDefinition.log.addHandler(logging.StreamHandler())


class Empty():
    def __init__(self):
        self.readoutMethods = []


@pytest.fixture
def empty():
    return Empty()


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

    def set_sleep_mode(self, *args):
        self.args = args


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
            self.voltage = voltage / 1000  # mV to V


@pytest.mark.skipif(tf is False)
@pytest.fixture
def mock_tinkerforge(monkeypatch):
    if tf is False:
        pytest.skip(reason="Tinkerforge not installed")

    def returner(*args):
        return args

    monkeypatch.setattr(
        ioDefinition, "devices", {297: returner, 111: returner, 2115: returner}, False
    )
    monkeypatch.setattr(ioDefinition, "IPConnection", Mock_IPConnection, False)
    monkeypatch.setattr(ioDefinition, 'BrickHAT', Mock_BrickHAT, False)
    monkeypatch.setattr(ioDefinition, 'BrickletAirQuality', Mock_BrickletAirQuality, False)
    monkeypatch.setattr(ioDefinition, 'BrickletAnalogOutV3', Mock_BrickletAnalogOutV3, False)


@pytest.fixture
def tf_device_pars():
    """Tinkerforge device parameters."""
    # 0: uid, 1: connected_uid, 2: position, 3: hardware_version, 4: firmware_version,
    # 5: device_identifier, 6: enumeration_type
    return ["abc", "def", "i", 0, 0, 111, 1]


@pytest.mark.skipif(tf is False)
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


@pytest.fixture
def calling():
    def callingf(*args):
        global called
        called = True
        global calledArgs
        calledArgs = args
    return callingf


@pytest.fixture
def raisingAssertion():
    def raising(*args):
        raise AssertionError
    return raising


@pytest.fixture
def raising():
    def raisingf(*args):
        raise Exception('test')
    return raisingf


# General and tinkerforge tests.
def test_setupTinkerforge_False(empty, monkeypatch):
    monkeypatch.setattr(ioDefinition, 'tf', False)
    ioDefinition.InputOutput.setupTinkerforge(empty)
    with pytest.raises(AttributeError):
        empty.tfDevices


@pytest.mark.parametrize('device_identifier, name', [(297, 'airQuality'),
                                                     (111, 'HAT'),
                                                     (2115, 'out1')
                                                     ])
def test_deviceConnected(mock_tinkerforge, skeleton, tf_device_pars, device_identifier, name):
    tf_device_pars[5] = device_identifier
    uid = tf_device_pars[0]
    ioDefinition.InputOutput.deviceConnected(skeleton, *tf_device_pars)
    assert skeleton.tfDevices[uid] == (uid, 0)
    assert skeleton.tfMap[name] == uid


def test_deviceConnected_available(skeleton, mock_tinkerforge, tf_device_pars, caplog):
    caplog.set_level(logging.DEBUG)
    tf_device_pars[6] = 0
    ioDefinition.InputOutput.deviceConnected(skeleton, *tf_device_pars)
    assert caplog.text.endswith("Device available: abc at i of type 111.\n")


class Test_deviceDisconnected:
    @pytest.fixture(autouse=True)
    def pars_modified(self, tf_device_pars):
        tf_device_pars[6] = Mock_IPConnection.ENUMERATION_TYPE_DISCONNECTED
        return tf_device_pars

    @pytest.fixture(autouse=True)
    def setup(self, skeleton, mock_tinkerforge, pars_modified):
        uid = pars_modified[0]
        skeleton.tfDevices[uid] = 5
        skeleton.tfMap['out0'] = uid
        return skeleton

    @pytest.fixture
    def act(self, setup, pars_modified):
        ioDefinition.InputOutput.deviceConnected(setup, *pars_modified)
        return setup

    def test_device_list(self, setup, act):
        assert setup.tfDevices == {}

    def test_device_map(self, setup, act):
        assert setup.tfMap == {}

    def test_output(self, setup, caplog, pars_modified):
        caplog.set_level(logging.DEBUG)
        ioDefinition.InputOutput.deviceConnected(setup, *pars_modified)
        assert caplog.text.endswith("Device abc disconnected.\n")


class Test_close:
    def test_close_tf(self, empty):
        empty.tfCon = Mock_IPConnection()
        ioDefinition.InputOutput.close(empty)
        assert empty.tfCon.disconnected

    def test_stop_watchdog(self, skeleton):
        skeleton.tfDevices['abc'] = Mock_BrickHAT()
        skeleton.tfMap['HAT'] = 'abc'
        ioDefinition.InputOutput.close(skeleton)
        assert skeleton.tfDevices['abc'].args == (0, 0, False, False, False)

    def test_close_sensors(self, empty, monkeypatch: pytest.MonkeyPatch, calling):
        monkeypatch.setattr(sensors, 'close', calling)
        ioDefinition.InputOutput.close(empty)
        assert called

    def test_close_sensors_failed(self, skeletonP, monkeypatch: pytest.MonkeyPatch, raising):
        monkeypatch.setattr(sensors, 'close', raising)
        ioDefinition.InputOutput.close(skeletonP)
        pass  # TODO test exception log


class Test_getSensors:
    @pytest.fixture
    def sensorsGetData(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sensors, 'getData', lambda *args: {})

    def test_getSensors_Clean(self, empty, sensorsGetData):
        assert ioDefinition.InputOutput.getSensors(empty) == {}

    def test_renew_watchdog(self, skeleton, sensorsGetData):
        skeleton.tfDevices['abc'] = Mock_BrickHAT()
        skeleton.tfMap['HAT'] = 'abc'
        ioDefinition.InputOutput.getSensors(skeleton)
        assert skeleton.tfDevices['abc'].args == (30, 1, True, False, True)

    def test_call_sensors(self, empty, monkeypatch):
        monkeypatch.setattr(sensors, 'getData', lambda *args: {'test': True})
        assert ioDefinition.InputOutput.getSensors(empty) == {'test': True}

    def test_call_sensors_no_dictionary(self, empty, monkeypatch):
        monkeypatch.setattr(sensors, 'getData', lambda *args: [])
        assert ioDefinition.InputOutput.getSensors(empty) == {}

    def test_call_sensors_failed(self, skeletonP, monkeypatch, raising, caplog):
        monkeypatch.setattr(sensors, 'getData', raising)
        ioDefinition.InputOutput.getSensors(skeletonP)
        assert "Get sensors failed." in caplog.text


def test_setOutput_Not_Connected(skeletonP, caplog):
    caplog.set_level(0)
    ioDefinition.InputOutput.setOutput(skeletonP, 'out1', 100)
    assert "Output 'out1' is not connected." in caplog.text


@pytest.mark.skipif(not tf, reason="Tinkerforge not installed.")
def test_setOutput_connection_lost(skeleton):
    skeleton.tfDevices['ao3'] = Mock_BrickletAnalogOutV3()
    skeleton.tfMap['out1'] = 'ao3'
    ioDefinition.InputOutput.setOutput(skeleton, 'out1', -1)
    assert 'ao3' not in skeleton.tfDevices.keys()


class Test_setOutput:
    def test_tf(self, skeleton):
        skeleton.tfDevices['ao3'] = Mock_BrickletAnalogOutV3()
        skeleton.tfMap['out1'] = 'ao3'
        ioDefinition.InputOutput.setOutput(skeleton, 'out1', 9)
        assert skeleton.tfDevices['ao3'].voltage == 9

    def test_external(self, skeleton, monkeypatch, calling):
        monkeypatch.setattr(sensors, 'setOutput', calling)
        ioDefinition.InputOutput.setOutput(skeleton, 'out5', 2)
        assert calledArgs == (skeleton, 'out5', 2)

    def test_noSensorsFile(self, skeleton, monkeypatch):
        with pytest.raises(KeyError):
            ioDefinition.InputOutput.setOutput(skeleton, 'out5', 2)
