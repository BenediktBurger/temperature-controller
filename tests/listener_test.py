#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the listener.py file.

Created on Sat Jun 19 08:17:59 2021 by Benedikt Moneke
"""

# for tests
import pytest
import sys
sys.path.append('C:/Users/moneke/temperature-controller')

# auxiliary for fixtures
import pickle
from devices import intercom

# file to test
from controllerData import listener


class Empty:
    pass

@pytest.fixture
def empty():
    return Empty()


class Connection:
    def close(self):
        pass


class Mock_Controller:
    def __init__(self):
        self.pids = {}


class Mock_PID:
    components = 123
    def __init__(self):
        global reset
        reset = False

    def reset(self):
        global reset
        reset = True


@pytest.fixture(autouse=True)
def disable_network(monkeypatch):
    def new_sendMessage(*args, **kwargs):
        global message
        message = list(args)

    def new_readMessage(connection=Connection()):
        return typ, content
    monkeypatch.setattr(intercom, "sendMessage", lambda *args, **kwargs: new_sendMessage(*args, **kwargs))
    monkeypatch.setattr(intercom, "readMessage", lambda connection: new_readMessage(connection))


# ConnectionHandler
@pytest.fixture
def conn():
    return Connection()


@pytest.fixture
def signals():
    return listener.ListenerSignals()


@pytest.fixture
def ch(conn, signals):
    return listener.ConnectionHandler(conn, signals)


@pytest.fixture
def chP(ch):
    ch.controller = Mock_Controller()
    ch.controller.pids['0'] = Mock_PID()
    return ch


class Test_handler():
    """Test the connectionHandler"""

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

    def test_setValue_wrong_input(self, ch):
        with pytest.raises(AssertionError):
            ch.setValue(pickle.dumps([]))

    def test_getValue(self, ch):
        ch.getValue(pickle.dumps(["pid0"]))
        content = pickle.loads(message[2])
        assert message[1] == "SET"
        assert content == {"pid0": None}

    def test_executeCommand_pid_components(self, chP):
        content = pickle.dumps(['pid0', "components"])
        chP.executeCommand(content)
        assert message[1:] == ['SET', pickle.dumps({f"pid0/components": 123})]

    def test_executeCommand_pid_reset(self, chP):
        content = pickle.dumps(['pid0', "reset"])
        chP.executeCommand(content)
        assert reset == True

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

    def test_stopController(self, ch, qtbot):
        with qtbot.waitSignal(ch.signals.stopController):
            ch.stopController('')
        assert message[1] == 'ACK'
