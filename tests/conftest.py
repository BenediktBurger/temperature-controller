#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
General pytest configuration for the temperature controller.

Created on Sat Jun 19 08:17:59 2021 by Benedikt Moneke
"""

# for tests
import pytest
import sys
sys.path.append('C:/Users/moneke/temperature-controller')


class Empty:
    pass

@pytest.fixture
def empty():
    return Empty()

class Connection:
    def __init__(self):
        self.open = True

    def close(self):
        self.open = False

@pytest.fixture
def connection():
    return Connection()

