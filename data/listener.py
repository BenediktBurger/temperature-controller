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
    stopController = QtCore.pyqtSignal()
    #signals = {'pidsChanged': QtCore.pyqtSignal(),
    #           'stopController': QtCore.pyqtSignal(),
    #           }

    def __init__(self, host=None, port=-1, threadpool=None):
        """Initialize the Thread."""
        super().__init__()
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
            connection, addr = self.listener.accept()
            print(addr)
            handler = ConnectionHandler(connection, self.signals)
            self.threadpool.start(handler)
        self.listener.close()
        print("listen stopped")


class ConnectionHandler(QtCore.QRunnable):
    """Handling the connection and its requests."""

    def __init__(self, connection, signals):
        """Initialize the handler."""
        super().__init__()
        self.connection = connection
        self.signals = signals

    def run(self):
        """Handle the connection"""
        typ, content = intercom.readMessage(self.connection)
        reaction = {'OFF': self.stopController
                    }
        try:
            reaction[typ](content)
        except KeyError:
            intercom.sendMessage(self.connection, 'ERR', "Unknown command".encode('ascii'))
        finally:
            self.connection.close()

    def stopController(self, content):
        """Stop the controller."""
        intercom.sendMessage(self.connection, 'ACK')
        self.connection.close()
        self.signals['stopController'].emit()
