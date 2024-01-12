#!/usr/bin/env python3
"""
Main file of the temperature controller for the lab.

Created on Mon Jun 14 11:12:51 2021 by Benedikt Moneke
"""

from argparse import ArgumentParser
import datetime
import logging
import math
import time
from typing import Any, Optional


from qtpy import QtCore
from qtpy.QtCore import Slot as pyqtSlot  # type: ignore
from simple_pid import PID
try:
    from pyleco.core.message import Message, MessageTypes
    from pyleco.utils.qt_listener import QtListener
except ModuleNotFoundError:
    PYLECO = False
else:
    PYLECO = True

# local packages
from controllerData import connectionData    # Data to connect to database.
from controllerData import listener, ioDefinition
from devices.intercom import Publisher


log = logging.getLogger("TemperatureController")
log.addHandler(logging.StreamHandler())  # log to stderr
log.setLevel(logging.INFO)
# Nothing yet marked as critical
# critical_handler = logging.FileHandler("log.txt")
# critical_handler.setLevel(logging.CRITICAL)
# critical_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
# log.addHandler(critical_handler)

try:
    import psycopg2
except ModuleNotFoundError:
    psycopg2 = None
    log.warning("Package 'psycopg2' not found, no database access possible.")


class ListHandler(logging.Handler):
    """Store log entries in a list of strings.

    :param length: Maximum length of entries in the list, rotating buffer system.
        If None, keep all.
    """

    def __init__(self, length: Optional[int] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log: list[str] = []
        self.length = length

    def emit(self, record):
        if self.length is not None and len(self.log) >= self.length:
            self.log.pop(0)
        try:
            self.log.append(self.format(record))
        except Exception:
            self.handleError(record)

    def reset(self):
        """Clear the internal log."""
        self.log.clear()


class TemperatureController(QtCore.QObject):
    """The temperature controller itself."""
    stopSignal = QtCore.pyqtSignal()
    stopApplication = QtCore.pyqtSignal()

    def __init__(self, name: str = "TemperatureController", host: str = "localhost", **kwargs):
        super().__init__(**kwargs)

        # Configure Settings
        application = QtCore.QCoreApplication.instance()
        if application is not None:
            application.setOrganizationName("NLOQO")
            application.setApplicationName(name)
        settings = QtCore.QSettings()
        self.settings = settings

        # General config
        self.data = {}  # Current data dictionary.
        self.last_value_set = time.time()
        self.tries = 0

        # Store log in a list
        self.log = ListHandler(100)
        self.log.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        log.addHandler(self.log)
        logging.getLogger("pyleco").addHandler(self.log)

        # Create objects like timers
        self.readoutTimer = QtCore.QTimer()
        self.threadpool = QtCore.QThreadPool()

        # Initialize sensors
        self.inputOutput = ioDefinition.InputOutput(controller=self)

        # PID controllers
        self.pids: dict[str, PID] = {}
        for i in range(settings.value('pids', defaultValue=2, type=int)):
            self.pids[str(i)] = PID(auto_mode=False)
            # auto_mode false, in order to start with the last value.
        self.pidSensor = {}  # the main sensor of the PID
        self.pidState = {}  # state of the corresponding output: 0 off, 1 manual, 2 pid
        self.pidOutput = {}  # Output device of the pid.
        for key in self.pids.keys():
            self.setupPID(key)

        # Configure the listener thread for listening intercom.
        self.setupListener(settings)
        if PYLECO:
            print("temp name", name)
            self.setup_leco_listener(name=name, host=host)

        self.connectDatabase()
        self.publisher = Publisher(port=11099, standalone=True)

        # Configure readoutTimer
        self.readoutTimer.start(settings.value('readoutInterval', 5000, int))
        self.readoutTimer.timeout.connect(self.readTimeout)
        log.info("Temperature Controller initialized")

    def __del__(self):
        log.removeHandler(self.log)

    def setupListener(self, settings: QtCore.QSettings):
        """Setup the thread listening for intercom."""
        self.listenerThread = QtCore.QThread()
        self.stopSignal.connect(self.listenerThread.quit)
        self.listener = listener.Listener(port=settings.value('listener/port', 22001, int),
                                          threadpool=self.threadpool, controller=self)
        self.listener.moveToThread(self.listenerThread)
        self.listenerThread.started.connect(self.listener.listen)
        self.listenerThread.start()
        # Listener Signals.
        self.listener.signals.stopController.connect(self.shut_down)
        self.listener.signals.pidChanged.connect(self.setupPID)
        self.listener.signals.timerChanged.connect(self.setTimerInterval)
        self.listener.signals.setOutput.connect(self.setOutput)
        self.listener.signals.sensorCommand.connect(self.sendSensorCommand)

    def setup_leco_listener(self, name: str, host: str) -> None:
        """Set up the Leco listener."""
        self.leco_listener = QtListener(name=name, host=host)
        self.leco_listener.signals.message.connect(self.handle_message)
        self.leco_listener.start_listen()
        self.leco_listener.register_rpc_method(self.shut_down)
        self.leco_listener.register_rpc_method(self.get_current_data)
        self.leco_listener.register_rpc_method(self.get_log)
        self.leco_listener.register_rpc_method(self.reset_log)
        self.leco_listener.register_rpc_method(self.sendSensorCommand)
        self.leco_listener.register_rpc_method(self.setOutput)
        self.leco_listener.register_rpc_method(self.set_PID_settings)
        self.leco_listener.register_rpc_method(self.get_PID_settings)
        self.leco_listener.register_rpc_method(self.reset_PID)
        self.leco_listener.register_rpc_method(self.get_current_PID_state)
        self.leco_listener.register_rpc_method(self.get_readout_interval)
        self.leco_listener.register_rpc_method(self.set_readout_interval)
        self.leco_listener.register_rpc_method(self.get_database_table)
        self.leco_listener.register_rpc_method(self.set_database_table)

    def set_PID_settings(self,
                         name: str,
                         lower_limit: Optional[float] = None,
                         upper_limit: Optional[float] = None,
                         Kp: Optional[float] = None,
                         Ki: Optional[float] = None,
                         Kd: Optional[float] = None,
                         setpoint: Optional[float] = None,
                         auto_mode: Optional[bool] = None,
                         last_output: Optional[float] = None,
                         state: Optional[int] = None,
                         sensors: Optional[list[str]] = None,
                         output_channel: Optional[str] = None,
                         ) -> None:
        self._set_pid_settings_from_dict(
            name=name,
            lowerLimit=lower_limit,
            upperLimit=upper_limit,
            Kp=Kp,
            Ki=Ki,
            Kd=Kd,
            setpoint=setpoint,
            autoMode=auto_mode,
            lastOutput=last_output,
            state=state,
            sensors=sensors,
            output=output_channel,
        )

    def _set_pid_settings_from_dict(self, name: str, **kwargs) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup(f'pid{name}')
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "lowerLimit":
                settings.setValue("lowerLimitNone", math.isinf(value))
            elif key == "upperLimit":
                settings.setValue("upperLimitNone", math.isinf(value))
            settings.setValue(key, value)
        settings.setValue("sensor", ",".join(settings.value("sensors")))
        self.setupPID(name=name)

    @pyqtSlot(str)
    def setupPID(self, name: str) -> None:
        """Configure the pid controller with `name`."""
        pid = self.pids[name]
        settings = QtCore.QSettings()
        settings.beginGroup(f'pid{name}')
        pid.output_limits = (
            None if settings.value('lowerLimitNone', True, bool) else settings.value('lowerLimit',
                                                                                     type=float),
            None if settings.value('upperLimitNone', True, bool) else settings.value('upperLimit',
                                                                                     type=float))
        pid.Kp = settings.value('Kp', defaultValue=1, type=float)
        pid.Ki = settings.value('Ki', defaultValue=0, type=float)
        pid.Kd = settings.value('Kd', defaultValue=0, type=float)
        pid.setpoint = settings.value('setpoint', 22.2, type=float)
        pid.set_auto_mode(settings.value('autoMode', True, type=bool),
                          settings.value('lastOutput', 0, type=float))
        self.pidState[name] = settings.value('state', defaultValue=0, type=int)
        sensors = settings.value('sensor', type=str).replace(' ', '').split(',')
        if sensors == ['']:
            log.warning(f"PID '{name}' does not have sensors configured.")
        self.pidSensor[name] = sensors
        self.pidOutput[name] = settings.value('output', f"out{name}", str)

    def get_PID_settings(self, pid: str | int) -> dict[str, Any]:
        PID_settings = {
            # key: (defaultValue, type)
            'lowerLimitNone': (True, bool),
            'upperLimitNone': (True, bool),
            'lowerLimit': (0, float),
            'upperLimit': (0, float),
            'Kp': (1, float),
            'Ki': (0, float),
            'Kd': (0, float),
            "autoMode": (True, bool),
            "lastOutput": (0, float),
            'setpoint': (22.2, float),
            "sensor": ("", str),
            "output": ("", str),
            "state": (0, int),
        }
        config = {}
        settings = QtCore.QSettings()
        settings.beginGroup(f'pid{pid}')
        for key, setting in PID_settings.items():
            config[key] = settings.value(key, *setting)
        config["output"] = settings.value('output', f"out{pid}", str)
        config["sensors"] = settings.value('sensor', type=str).replace(' ', '').split(',')
        return config

    @pyqtSlot()
    def shut_down(self) -> None:
        """Stop the controller and the application."""
        log.info("About to stop")
        self.readoutTimer.stop()
        # Stop the listener.
        try:
            self.listener.stop = True
        except AttributeError:
            pass
        self.stopSignal.emit()
        self.listenerThread.wait(10000)  # timeout in ms

        # Close the sensor and database
        self.inputOutput.close()
        try:
            self.database.close()
        except AttributeError:
            pass  # No database connection.

        # Stop the Application.
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            self.stopApplication.connect(app.quit)
            self.stopApplication.emit()
        log.info("Stopped.")

    # CONNECTIONS

    def connectDatabase(self):
        """(Re)Establish a connection to the database for storing sensor data."""
        try:
            self.database.close()
            del self.database
        except AttributeError:
            pass  # no database present
        if psycopg2 is None:
            return
        try:
            self.database = psycopg2.connect(**connectionData.database, connect_timeout=5)
        except AttributeError:
            pass
        except Exception as exc:
            log.exception("Database connection error.", exc_info=exc)

    # CONFIG

    def setTimerInterval(self, name, interval):
        """Set the interval for a timer with `name` to `interval`."""
        # it is the only timer right now.
        self.readoutTimer.setInterval(interval)

    @pyqtSlot(str)
    def sendSensorCommand(self, command: str):
        """Send a command to the sensors."""
        return self.inputOutput.executeCommand(command)

    # OPERATION

    @pyqtSlot()
    def readTimeout(self) -> None:
        """Read the sensors and calculate a pid value."""
        data = self.inputOutput.getSensors()
        output = {}
        for key in self.pids.keys():
            for sensor in self.pidSensor[key]:
                try:
                    output[key] = self.pids[key](data[sensor])
                except KeyError:
                    pass
                else:
                    if self.pidState[key] == 2:
                        self.setOutput(self.pidOutput[key], output[key])
                        if self.last_value_set + 60 < time.time():
                            self.settings.setValue(f"pid{key}/lastOutput",
                                                   output[key])
                            pass
                    break  # Valid sensor found: stop loop.
        for key in output.keys():
            data[f'pidOutput{key}'] = output[key]
        self.data = data
        self.writeDatabase(data)
        self.publisher(data)

    @pyqtSlot(str, float)
    def setOutput(self, name: str, value: float) -> None:
        """Set the output with `name` to `value` if the state allows it."""
        try:
            self.inputOutput.setOutput(name, value)
        except KeyError:
            log.warning(f"Output '{name}' is unknown.")

    def writeDatabase(self, data: dict[str, float]):
        """Write the iterable data in the database with the timestamp."""
        try:  # Check connection to the database and reconnect if necessary.
            database = self.database
        except AttributeError:
            if self.tries < 10:
                self.tries += 1
            else:
                self.connectDatabase()
                self.tries = 0
            return  # No database connection existing.
        table = self.settings.value('database/table', defaultValue="", type=str)
        if table == "":
            log.warning("No database table is configured.")
            return
        columns = "timestamp"
        for key in data.keys():
            columns += f", {key}"
        length = len(data)
        with database.cursor() as cursor:
            try:
                cursor.execute(f"INSERT INTO {table} ({columns}) VALUES (%s{', %s' * length})",
                               (datetime.datetime.now(), *data.values()))
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                self.connectDatabase()  # Connection lost, reconnect.
            except Exception as exc:
                log.exception("Database write error.", exc_info=exc)
                database.rollback()
            else:
                database.commit()

    # LECO methods
    def handle_message(self, message: Message) -> None:
        if message.header_elements.message_type != MessageTypes.JSON:
            log.warning(f"Unknown message received {message}.")
            return
        result = self.leco_listener.message_handler.rpc.process_request(message.payload[0])
        self.leco_listener.communicator.send(receiver=message.sender,
                                             conversation_id=message.conversation_id,
                                             message_type=message.header_elements.message_type,
                                             data=result
                                             )

    def set_database_table(self, table_name: str) -> None:
        settings = QtCore.QSettings()
        settings.setValue("database/table", table_name)

    def get_database_table(self) -> str:
        return QtCore.QSettings().value("database/table", type=str)

    def set_readout_interval(self, interval: float) -> None:
        """Set the readout interval in seconds (ms resolution)."""
        settings = QtCore.QSettings()
        interval_ms = int(interval * 1000)
        settings.setValue("readoutInterval", interval_ms)
        self.readoutTimer.setInterval(interval_ms)

    def get_readout_interval(self) -> float:
        return QtCore.QSettings().value("readoutInterval", type=int) / 1000

    def get_current_data(self) -> dict[str, float]:
        """Get current sensor and output data."""
        return self.data

    def reset_PID(self, pid: int | str = 0) -> None:
        if isinstance(pid, int):
            pid = str(pid)
        self.pids[pid].reset()

    def get_current_PID_state(self, pid: int | str = 0) -> tuple[float, float, float]:
        if isinstance(pid, int):
            pid = str(pid)
        return self.pids[pid].components

    def get_log(self) -> list[str]:
        return self.log.log

    def reset_log(self) -> None:
        self.log.reset()


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("-r", "--host", help="set the host name of this Node's Coordinator")
    parser.add_argument("-n", "--name", help="set the application name")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="increase the logging level by one, may be used more than once")

    kwargs = vars(parser.parse_args())
    for key, value in list(kwargs.items()):
        # remove not set values
        if value is None:
            del kwargs[key]
    verbosity = kwargs.pop("verbose")
    if verbosity:
        logging.getLogger("pyleco").addHandler(logging.StreamHandler())

    # Use stored values.
    try:
        address: str = connectionData.leco_coordinator_host_address
    except AttributeError:
        pass
    else:
        if ":" in address:
            host, port = address.split(":", maxsplit=1)
            kwargs.setdefault("port", int(port))
        else:
            host = address
        kwargs.setdefault("host", host)

    application = QtCore.QCoreApplication([])
    controller = TemperatureController(**kwargs)  # noqa: F841
    application.exec()  # start the event loop


if __name__ == "__main__":
    """If called as a script, start the qt system and start the controller."""
    main()
