"""
Library for communication between programs and with labview.

classes
------
Intercom : address="127.0.0.1", port=12345, timeout=10
    Convenience class for connecting, reading and sending messages.
timeout
    For convenience: Just the socket.timeout error raised at a timeout.

functions
-----------
connect : address="127.0.0.1", port=12345, timeout=None
    Establish and return a connected socket connection.
readMessage : connection
    Receive and decode a message. Return `typ` and `content`.
sendMessage: connection, typ, content=b''
    Encode and send a message with `typ` and `content`.

Created on Thu Mar  4 13:04:32 2021 by Benedikt Moneke
"""

import logging
import pickle
import socket
from socket import timeout as timeout

import zmq


"""
Protocol definition:
    - A three letter uppercase command out of the list 'validCommands'.
    - 5 digits (zero padded on the left) indicating the length of the following content
    - The content with a number of bytes indicated by the previous length

ASCII version of a list is newline (\n) separated.
ASCII version of a dictionary has its elements separated by a newline (\n).
An element consists in a {key}:{type}:{value} triple. Type is:
    - f for float
    - i for int
    - s for string
    - n for None/Null
"""

# list of valid commands
validCommands = (
    # General communication
    'ACK',  # acknowledge any command without a specified response type
    'ERR',  # an error message (pickled)/ascii
    'ECO',  # echo back the message
    'SAV',  # save storage to disk
    'CMD',  # execute some command
    'OFF',  # tell the other side to switch off
    # Data communication with pickled objects
    'GET',  # get variables (pickled iterable): response is SET
    'SET',  # set variables (pickled dictionary)
    'DEL',  # delete variables (pickled iterable)
    'PUB',  # set and publish variables (pickled dictionary)
    'DMP',  # get all variables: response is SET
    # Data communication via ASCII encoding
    'GEA',  # get variables (Ascii list): response is SEA
    'SEA',  # set variables (Ascii dictionary)
    'DEA',  # del variables (Ascii list)
    'PUA',  # set and publish variables (Ascii dictionary)
)


def connect(address="127.0.0.1", port=12345, timeout=None):
    """Create and return a TCP connection to `address` and `port` with `timeout`."""
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    connection.connect((address, port))
    return connection


def readMessage(connection):
    """Receive and decode a message. Return `typ` and `content`."""
    headerLength = 3 + 5  # 3 letters for type, 5 for length
    status = 0
    readBuffer = b''
    while status < 2:
        read = connection.recv(1064)
        if not read:
            break
        readBuffer += read
        if status == 0 and len(readBuffer) >= headerLength:  # Reading header.
            typ = readBuffer[0:3].decode('utf-8')
            length = int(readBuffer[3:headerLength].decode('utf-8'))
            readBuffer = readBuffer[headerLength:]
            status = 1
        if status == 1 and len(readBuffer) >= length:  # Reading message.
            content = readBuffer[:length]
            return typ, content


def sendMessage(connection, typ, content=b''):
    """Encode and send a message with `typ` and `content`."""
    assert typ in validCommands, "Unknown type"
    header = f"{typ}{len(content):05}".encode('utf-8')
    connection.sendall(header + content)


class Intercom:
    """An intercom channel using one-time connections."""

    def __init__(self, address="127.0.0.1", port=12345, timeout=10):
        """Save connection settings."""
        self.address = address, port, timeout

    def send(self, typ, content=b''):
        """Send a message and read the answer."""
        connection = connect(*self.address)
        sendMessage(connection, typ, content)
        read = readMessage(connection)
        connection.close()
        return read

    def sendAscii(self, typ, content):
        """Send a message with ASCII content."""
        return self.send(typ, content.encode('ascii'))

    def sendObject(self, typ, content):
        """Send python objects and return python objects if answer is 'SET'."""
        typ, content = self.send(typ, pickle.dumps(content))
        if typ in ('SET', 'DMP'):
            return typ, pickle.loads(content)
        else:
            return typ, content


class Publisher:
    """
    Publishing key-value data via zmq.

    :param str address: Address of the server, default is localhost.
    :param int port: Port of the server, defaults to 11100, default proxy.
    :param log: Logger to log to.
    :param bool standalone: Use without a proxy server.

    Sending dictionaries of measurement data to Data Collector Programs.

    The key is the first frame (for topic filtering) and the second frame
    contains the pickled value. Each pair is sent as their own message.
    Quantities may be expressed as a (magnitude number, units str) tuple.
    """

    def __init__(self, host="localhost", port=11100, log=None,
                 standalone=False,
                 **kwargs):
        self.log = log or logging.getLogger("__main__.Publisher")
        self.log.info(f"Publisher started at {host}:{port}.")
        self.socket = zmq.Context.instance().socket(zmq.PUB)
        if standalone:
            self._connecting = self.socket.bind
            self._disconnecting = self.socket.unbind
            self.host = "*"
        else:
            self._connecting = self.socket.connect
            self._disconnecting = self.socket.disconnect
            self.host = host
        self._port = False
        self.port = port
        super().__init__(**kwargs)

    def __del__(self):
        self.socket.close(1)

    def __call__(self, data):
        """Publish the dictionary `data`."""
        self.send(data)

    @property
    def port(self):
        """The TCP port to publish to."""
        return self._port

    @port.setter
    def port(self, port):
        self.log.debug(f"Port changed to {port}.")
        if self._port == port:
            return
        if self._port:
            self._disconnecting(f"tcp://{self.host}:{self._port}")
        self._connecting(f"tcp://{self.host}:{port}")
        self._port = port

    def send(self, data):
        """Send the dictionay `data`."""
        assert isinstance(data, dict), "Data has to be a dictionary."
        for key, value in data.items():
            self.socket.send_multipart((key.encode(), pickle.dumps(value)))

    def send_quantities(self, data):
        """Send the dictionay `data` containing Quantities."""
        assert isinstance(data, dict), "Data has to be a dictionary."
        for key, value in data.items():
            self.socket.send_multipart((
                key.encode(),
                pickle.dumps((value.magnitude, f"{value.units:~}"))))
