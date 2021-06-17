"""
Intercom listener and handler for temperature controller

classes
-------
Listener
    A QObject listening on incoming intercom.
Handler
    QRunnables handling intercom requests.

Created on Mon Jun 14 14:05:04 2021 by Benedikt Moneke
"""

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


class Listener(QtCore.QObject):
    """Listening on incoming intercom for new connections."""

    def __init__(self, host=None, port=-1, threadpool=None, controller=None):
        """Initialize the Thread."""
        super().__init__()
        self.signals = ListenerSignals()
        self.controller = controller
        assert port >= 0, "No valid port number specified."
        if host is None:  # figure out our IP
            sock = socket.socket(type=socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))  # just a reliable server
            host = sock.getsockname()[0]
            sock.close()
        print(f"Listener init at {host}:{port}.")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # die Adresse sofort wieder benutzen, nicht den 2 Minuten Timer nach Stop des vorherigen Servers warten
        listener.bind((host, port))
        listener.settimeout(5)
        listener.listen(1)
        self.listener = listener
        self.stop = False
        if threadpool is None:
            self.threadpool = QtCore.QThreadPool()
        else:
            self.threadpool = threadpool

    def __del__(self):
        """On deletion close connection."""
        try:
            self.listener.close()
        except Exception as exc:
            print(f"Closure failed with {exc}.")

    def listen(self):
        """Listen for connections and emit it via signals."""
        print("start listen")
        while not self.stop:
            try:
                connection, addr = self.listener.accept()
            except socket.timeout:
                pass
            else:
                print(addr)
                handler = ConnectionHandler(connection, self.signals, self.controller)
                self.threadpool.start(handler)
        self.listener.close()
        print("listen stopped")


class ListenerSignals(QtCore.QObject):
    """Signals for the listener."""
    stopController = QtCore.pyqtSignal()
    pidChanged = QtCore.pyqtSignal(str)
    timerChanged = QtCore.pyqtSignal(str, int)
    setOutput = QtCore.pyqtSignal(str, float)
    sensorCommand = QtCore.pyqtSignal(str)


class ConnectionHandler(QtCore.QRunnable):
    """Handling the connection and its requests."""

    def __init__(self, connection, signals, controller=None):
        """Initialize the handler."""
        super().__init__()
        self.connection = connection
        self.signals = signals
        self.controller = controller

    def run(self):
        """Handle the connection"""
        try:
            typ, content = intercom.readMessage(self.connection)
        except TypeError as exc:
            intercom.sendMessage(self.connection, 'ERR', f"TypeError: {exc}".encode('ascii'))
            return
        reaction = {'OFF': self.stopController,
                    'SET': self.setValue,
                    'GET': self.getValue,
                    'CMD': self.executeCommand,
                    }
        try:
            reaction[typ](content)
        except KeyError:
            intercom.sendMessage(self.connection, 'ERR', "Unknown command".encode('ascii'))
        finally:
            self.connection.close()

    def setValue(self, content):
        """Write the content in the settings and emit an appropriate signal."""
        data = pickle.loads(content)
        assert type(data) == dict, "The content has to be a dictionary."
        settings = QtCore.QSettings()
        signals = {}
        for key in data.keys():
            settings.setValue(key, data[key])
            if 'pid' in key:
                signals['pid'] = key[3]
            if key == 'readoutInterval':
                self.signals.timerChanged.emit('readoutTimer', data[key])
        if 'pid' in signals.keys():
            self.signals.pidChanged.emit(signals['pid'])
        intercom.sendMessage(self.connection, 'ACK')

    def getValue(self, content):
        """Get some value."""
        keys = pickle.loads(content)
        settings = QtCore.QSettings()
        data = {}
        for key in keys:
            data[key] = settings.value(key)
            """if key == 'pid0components':
                data[key] = self.controller.pids['0'].components
            if key == 'pid1components':
                data[key] = self.controller.pids['1'].components"""
        intercom.sendMessage(self.connection, 'SET', pickle.dumps(data))

    def executeCommand(self, content):
        """Execute a command."""
        deviceName, command = pickle.loads(content)
        if deviceName.startswith('pid'):
            device = self.controller.pids[deviceName[3]]
            if command == 'components':
                data = pickle.dumps({f"{deviceName}/components": device.components})
                intercom.sendMessage(self.connection, 'SET', data)
            elif command == 'reset':
                device.reset
                intercom.sendMessage(self.connection, 'ACK')
        if deviceName == "sensors":
            self.signals.sensorCommand.emit(command)
            intercom.sendMessage(self.connection, 'ACK')
        if deviceName.startswith('out'):
            name = deviceName[3]
            self.signals.setOutput.emit(name, float(command))
            intercom.sendMessage(self.connection, 'ACK')

    def stopController(self, content):
        """Stop the controller."""
        intercom.sendMessage(self.connection, 'ACK')
        self.connection.close()
        self.signals.stopController.emit()
