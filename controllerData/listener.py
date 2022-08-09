"""
Intercom listener and handler for temperature controller

classes
-------
Listener : host, port, threadpool, controller
    A QObject listening on incoming intercom.
Handler : connection, signals, controller
    QRunnables handling intercom requests.

Created on Mon Jun 14 14:05:04 2021 by Benedikt Moneke
"""

import logging
import pickle
import socket

try:  # Qt for nice effects.
    from PyQt6 import QtCore
    from PyQt6.QtCore import pyqtSlot
    qtVersion = 6
except ModuleNotFoundError:
    from PyQt5 import QtCore
    from PyQt5.QtCore import pyqtSlot
    qtVersion = 5

from devices import intercom

log = logging.getLogger("TemperatureController")


class Listener(QtCore.QObject):
    """Listening on incoming intercom for new connections."""

    def __init__(self, host=None, port=-1, threadpool=None, controller=None):
        """
        Initialize the Thread.
        
        Parameters
        ----------
        host : str
            Address to listen at. If 'None', try to determine it.
        port : int
            Port to listen at.
        threadpool : QThreadpool
            Pool for threads for the ConnectionHandlers, if not provided, create one.
        controller
            Instance of the temperature controller.
        """
        super().__init__()
        self.signals = self.ListenerSignals()
        self.controller = controller
        assert port >= 0, "No valid port number specified."
        if host is None:  # figure out our IP
            sock = socket.socket(type=socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))  # just a reliable server
            host = sock.getsockname()[0]
            sock.close()
        log.info(f"Listener initialized at {host}:{port}.")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # die Adresse sofort wieder benutzen, nicht den 2 Minuten Timer nach Stop des vorherigen Servers warten
        listener.bind((host, port))
        listener.settimeout(3)
        listener.listen(1)
        self.listener = listener
        self.stop = False
        if threadpool is None:
            self.threadpool = QtCore.QThreadPool()
        else:
            self.threadpool = threadpool

    class ListenerSignals(QtCore.QObject):
        """Signals for the listener."""
        stopController = QtCore.pyqtSignal()
        pidChanged = QtCore.pyqtSignal(str)
        timerChanged = QtCore.pyqtSignal(str, int)
        setOutput = QtCore.pyqtSignal(str, float)
        sensorCommand = QtCore.pyqtSignal(str)

    def __del__(self):
        """On deletion close connection."""
        try:
            self.listener.close()
        except Exception as exc:
            log.exception("Closure failed with.", exc_info=exc)

    def listen(self):
        """Listen for connections and emit it via signals."""
        while not self.stop:
            try:
                connection, address = self.listener.accept()
            except socket.timeout:
                pass
            else:
                handler = ConnectionHandler(connection, self.signals, self.controller, address)
                self.threadpool.start(handler)
        self.listener.close()
        log.info("Listen stopped to listen.")


class ConnectionHandler(QtCore.QRunnable):
    """Handling the connection and its requests."""

    def __init__(self, connection, signals, controller, address=None):
        """Initialize the handler."""
        super().__init__()
        self.connection = connection
        self.signals = signals
        self.controller = controller
        self.address = address

    def run(self):
        """Handle the connection"""
        try:
            typ, content = intercom.readMessage(self.connection)
        except TypeError as exc:
            intercom.sendMessage(self.connection, 'ERR', f"TypeError: {exc}".encode('ascii'))
            self.connection.close()
            return
        except (ConnectionResetError, UnicodeDecodeError):
            self.connection.close()
            return
        except Exception as exc:
            self.controller.errors['intercom'] = f"Communication error {type(exc).__name__}: {exc}. Address {self.address}."
            log.error(f"Communication error {type(exc).__name__}: {exc}. Address {self.address}.")
            self.connection.close()
            return
        reaction = {'OFF': self.stopController,
                    'SET': self.setValue,
                    'GET': self.getValue,
                    'DEL': self.delValue,
                    'CMD': self.executeCommand,
                    }
        try:
            reaction[typ](content)
        except KeyError:
            intercom.sendMessage(self.connection, 'ERR', "Unknown command".encode('ascii'))
        except (TypeError, AssertionError, ValueError) as exc:
            intercom.sendMessage(self.connection, 'ERR', f"Wrong input content: {exc}".encode('ascii'))
        except EOFError:
            intercom.sendMessage(self.connection, 'ERR', "No message content".encode('ascii'))
        finally:
            self.connection.close()

    def setValue(self, content):
        """Write the content in the settings and emit an appropriate signal."""
        data = pickle.loads(content)
        assert type(data) == dict, "The content has to be a dictionary."
        settings = QtCore.QSettings()
        pidChanged = {}
        for key in data.keys():
            settings.setValue(key, data[key])
            if key.startswith('pid'):
                pidChanged[key.split("/")[0]] = True
            if key == 'readoutInterval':
                self.signals.timerChanged.emit('readoutTimer', data[key])
        for key in pidChanged.keys():
            self.signals.pidChanged.emit(key.replace("pid", ""))
        intercom.sendMessage(self.connection, 'ACK')

    def getValue(self, content):
        """Get some value."""
        keys = pickle.loads(content)
        assert hasattr(keys, '__iter__'), "The content has to be an iterable."
        settings = QtCore.QSettings()
        data = {}
        for key in keys:
            if key == 'errors':
                data[key] = self.controller.errors
            elif key == 'data':
                data[key] = self.controller.data
            else:
                data[key] = settings.value(key)
        intercom.sendMessage(self.connection, 'SET', pickle.dumps(data))

    def delValue(self, content):
        """Delete some value."""
        keys = pickle.loads(content)
        assert hasattr(keys, '__iter__'), "The content has to be an iterable."
        if 'errors' in keys:
            self.controller.errors = {}
        intercom.sendMessage(self.connection, 'ACK')

    def executeCommand(self, content):
        """Execute a command."""
        deviceName, command = pickle.loads(content)
        if deviceName.startswith('pid'):
            try:
                device = self.controller.pids[deviceName[3]]
            except IndexError:
                intercom.sendMessage(self.connection, 'ERR', "No pid name given.".encode('ascii'))
                return
            if command == 'components':
                data = pickle.dumps({f"{deviceName}/components": device.components})
                intercom.sendMessage(self.connection, 'SET', data)
            elif command == 'reset':
                device.reset()
                intercom.sendMessage(self.connection, 'ACK')
        elif deviceName == "sensors":
            self.signals.sensorCommand.emit(command)
            intercom.sendMessage(self.connection, 'ACK')
        elif deviceName.startswith('out'):
            if len(deviceName) < 4:
                intercom.sendMessage(self.connection, 'ERR', "No output name given.".encode('ascii'))
                return
            try:
                value = float(command)
            except ValueError:
                intercom.sendMessage(self.connection, 'ERR', "Value is not a number.".encode('ascii'))
            else:
                self.signals.setOutput.emit(deviceName, value)
                intercom.sendMessage(self.connection, 'ACK')
        elif deviceName == 'tinkerforge' and command == 'enumerate':
            try:
                self.controller.inputOutput.tfCon.enumerate()
            except AttributeError:
                intercom.sendMessage(self.connection, 'ERR', "No tinkerforge connection.".encode('ascii'))
            else:
                intercom.sendMessage(self.connection, 'ACK')

    def stopController(self, content):
        """Stop the controller."""
        intercom.sendMessage(self.connection, 'ACK')
        self.connection.close()
        self.signals.stopController.emit()
