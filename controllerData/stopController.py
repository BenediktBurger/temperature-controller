#!/usr/bin/env python3
"""
Script to stop the Temperature Controller gracefully by telling it to stop.
"""

import socket
import subprocess
import time


def connect(address="127.0.0.1", port=12345, timeout=1):
    """Create and return a TCP connection to `address` and `port` with `timeout`."""
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    connection.connect((address, port))
    return connection


def sendMessage(connection, typ, content=b''):
    """Encode and send a message with `typ` and `content`."""
    header = f"{typ}{len(content):05}".encode('utf-8')
    connection.sendall(header + content)


def writeLog():
    """Write a log file with the system status."""
    result = subprocess.run(["systemctl", "--user", "status", "temperature-controller"],
                            text=True, stdout=subprocess.PIPE)
    try:
        with open("/dev/shm/temperature-controller.log", 'a') as file:
            file.write(result.stdout)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    # Get the localhost internet IP
    sock = socket.socket(type=socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))  # just a reliable server
    host = sock.getsockname()[0]
    sock.close()
    # Send a message to the Listener to stop
    sendMessage(connect(host, 22001), 'OFF')
    time.sleep(.1)  # Give some time to process
    sendMessage(connect(host, 22001), 'ACK')  # to stop the listener
    # Otherwise we have to wait for the listener to time out.
    writeLog()
