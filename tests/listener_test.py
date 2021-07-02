#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the listener.py file.

Created on Sat Jun 19 08:17:59 2021 by Benedikt Moneke
"""

# for tests
import pytest

# auxiliary for fixtures and tests
import pickle
import socket

from devices import intercom

# file to test
from controllerData import listener


class Mock_Controller:
    def __init__(self):
        self.pids = {}


class Mock_PID:
    components = 123
    def __init__(self):
        self.resetted = False

    def reset(self):
        self.resetted = True


@pytest.fixture(autouse=True)
def disable_network(monkeypatch, connection):
    def new_sendMessage(*args, **kwargs):
        global message
        message = list(args)

    def new_readMessage(connection=connection):
        return typ, content
    monkeypatch.setattr(intercom, "sendMessage", lambda *args, **kwargs: new_sendMessage(*args, **kwargs))
    monkeypatch.setattr(intercom, "readMessage", lambda connection: new_readMessage(connection))


@pytest.fixture
def signals():
    return listener.ListenerSignals()


@pytest.fixture
def ch(connection, signals, empty):
    return listener.ConnectionHandler(connection, signals, empty)


@pytest.fixture
def chP(ch):
    ch.controller = Mock_Controller()
    ch.controller.pids['0'] = Mock_PID()
    return ch

@pytest.fixture
def chPP(chP, empty):
    def passing():
        pass
    chP.controller.inputOutput = empty
    chP.controller.inputOutput.tfCon = empty
    chP.controller.inputOutput.tfCon.enumerate = passing
    return chP

class Test_listener():
    """Test the listener."""

    @pytest.fixture(scope="class")
    def listener(self):
        listi = listener.Listener(host='127.0.0.1', port=12345)
        yield listi
        del listi

    def test_init_name(self, listener):
        assert listener.listener.getsockname() == ('127.0.0.1', 12345)

    def test_init_timeout(self, listener):
        assert listener.listener.gettimeout() == 3

    def test_init_config(self, listener):
        assert listener.listener.family == socket.AF_INET
        assert listener.listener.type == socket.SOCK_STREAM

    def test_init_invalid_port(self):
        with pytest.raises(AssertionError):
            listener.Listener()


class Test_handler():
    """Test the connectionHandler."""

    @pytest.fixture
    def running(self):
        global typ, content
        typ = 'ACK'
        content = None

    @pytest.mark.parametrize('typIn, contentIn, answer', [('ACK', None, ['ERR', "Unknown command".encode('ascii')]),
                                                          ('OFF', None, ['ACK']),
                                                          ('GET', pickle.dumps(['pid0']), ['SET', pickle.dumps({"pid0": None})]),
                                                          ])
    def test_run(self, ch, typIn, contentIn, answer):
        global typ, content
        typ = typIn
        content = contentIn
        ch.run()
        assert message[1:] == answer

    def test_run_no_content(self, ch):
        global typ, content
        typ, content = 'SET', b''
        ch.run()
        assert message[2] == "No message content".encode('ascii')

    def test_run_wrong_content(self, ch):
        global typ, content
        typ, content = 'SET', 5
        ch.run()
        assert message[1] == "ERR"

    def test_run_insufficient_content(self, ch):
        global typ, content
        typ, content = 'CMD', pickle.dumps("test")
        ch.run()
        assert message[1] == 'ERR'

    def test_setValue_wrong_input(self, ch):
        with pytest.raises(AssertionError) as excinfo:
            ch.setValue(pickle.dumps([]))
        assert excinfo

    def test_getValue(self, ch):
        ch.getValue(pickle.dumps(["pid0"]))
        content = pickle.loads(message[2])
        assert message[1] == "SET"
        assert content == {"pid0": None}

    def test_getValue_wrong(self, ch):
        with pytest.raises(AssertionError):
            ch.getValue(pickle.dumps(5))

    def test_getValue_errors(self, ch):
        ch.controller.errors = {'test': "value"}
        ch.getValue(pickle.dumps(['errors']))
        content = pickle.loads(message[2])
        assert content == {'errors': {'test': "value"}}

    def test_delValue(self, ch):
        ch.controller.errors = {'test': "value"}
        ch.delValue(pickle.dumps(['errors']))
        assert ch.controller.errors == {}

    def test_executeCommand_pid_components(self, chP):
        content = pickle.dumps(['pid0', "components"])
        chP.executeCommand(content)
        assert message[1:] == ['SET', pickle.dumps({f"pid0/components": 123})]

    def test_executeCommand_pid_reset(self, chP):
        content = pickle.dumps(['pid0', "reset"])
        chP.executeCommand(content)
        assert chP.controller.pids['0'].resetted == True

    @pytest.mark.parametrize('out, value', [('0', 15.3), ('1', "10"), ('3', "17.3")])
    def test_executeCommand_output(self, ch, qtbot, out, value):
        content = pickle.dumps([f'out{out}', value])
        with qtbot.waitSignal(ch.signals.setOutput) as blocker:
            ch.executeCommand(content)
        assert message[1] == 'ACK'
        assert blocker.args == [out, float(value)]

    def test_executeCommand_output_no_name(self, ch):
        content = pickle.dumps(['out', ""])
        ch.executeCommand(content)
        assert message[1:] == ['ERR', "No output name given.".encode('ascii')]

    def test_executeCommand_output_wrong_value(self,ch):
        content = pickle.dumps(['out1', 'f'])
        ch.executeCommand(content)
        assert message[1:] == ['ERR', "Value is not a number.".encode('ascii')]

    def test_executeCommand_sensors(self, ch, qtbot):
        content = pickle.dumps(['sensors', "testing"])
        with qtbot.waitSignal(ch.signals.sensorCommand) as blocker:
            ch.executeCommand(content)
        assert message[1] == 'ACK'
        assert blocker.args == ["testing"]

    def test_executeCommand_tinkerforge_enumerate(self, chPP):
        content = pickle.dumps(['tinkerforge', "enumerate"])
        chPP.executeCommand(content)
        assert message[1] == 'ACK'

    def test_executeCommand_tinkerforge_enumerate_fail(self, chP):
        content = pickle.dumps(['tinkerforge', "enumerate"])
        chP.executeCommand(content)
        assert message[1] == 'ERR'
        

    def test_stopController(self, ch, qtbot):
        with qtbot.waitSignal(ch.signals.stopController):
            ch.stopController('')
        assert message[1] == 'ACK'
