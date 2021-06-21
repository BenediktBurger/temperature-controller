#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for the listener.py file.

Created on Sat Jun 19 08:17:59 2021

@author: moneke
"""

# for tests
import pytest
#import pytest-qt
import sys
sys.path.append('C:/Users/moneke/temperature-controller')

# auxiliary for fixtures
import pickle
from devices import intercom

# file to test
from controllerData import listener


class connection:
    def close(self):
        pass


@pytest.fixture(autouse=True)
def disable_network(monkeypatch):
    def new_sendMessage(*args, **kwargs):
        global message
        message = list(args)

    def new_readMessage(connection=connection()):
        return typ, content
    monkeypatch.setattr(intercom, "sendMessage", lambda *args, **kwargs: new_sendMessage(*args, **kwargs))
    monkeypatch.setattr(intercom, "readMessage", lambda connection: new_readMessage(connection))


# ConnectionHandler
@pytest.fixture
def conn():
    return connection()


@pytest.fixture
def signals():
    return listener.ListenerSignals()


@pytest.fixture
def ch(conn, signals):
    return listener.ConnectionHandler(conn, signals)


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
        #assert message[1:] == ['ERR', "Unknown command".encode('ascii')]

    def test_setValue(self, ch):
        with pytest.raises(AssertionError):
            ch.setValue(pickle.dumps([]))

    def test_getValue(self, ch):
        ch.getValue(pickle.dumps(["pid0"]))
        content = pickle.loads(message[2])
        assert message[1] == "SET"
        assert content == {"pid0": None}
