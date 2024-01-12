#!/usr/bin/env python3
"""
Main file of the base program.

created on 23.11.2020 by Benedikt Moneke
"""

# Standard packages.
from argparse import ArgumentParser
from typing import Any, Dict

from qtpy import QtCore, QtWidgets, uic
from qtpy.QtCore import Slot as pyqtSlot  # type: ignore

# Local packages.
from data import Settings
from data.controller_director import ControllerDirector


class ControlPanel(QtWidgets.QMainWindow):
    """Define the main window and essential methods of the program."""

    # actionClose: QtGui.QAction
    # actionSettings: QtGui.QAction

    leDatabaseTable: QtWidgets.QLineEdit
    sbReadoutInterval: QtWidgets.QSpinBox
    pbGetGeneral: QtWidgets.QPushButton
    pbSetGeneral: QtWidgets.QPushButton
    pbShutDown: QtWidgets.QPushButton
    sbOut0: QtWidgets.QDoubleSpinBox
    sbOut1: QtWidgets.QDoubleSpinBox
    pbOut0: QtWidgets.QPushButton
    pbOut1: QtWidgets.QPushButton

    gbReadout: QtWidgets.QGroupBox
    pbErrorsGet: QtWidgets.QPushButton
    pbErrorsClear: QtWidgets.QPushButton
    pbSensors: QtWidgets.QPushButton
    lbReadout: QtWidgets.QLabel

    gbPID: QtWidgets.QGroupBox
    bbId: QtWidgets.QComboBox
    sbSetpoint: QtWidgets.QDoubleSpinBox
    sbLastOutput: QtWidgets.QDoubleSpinBox
    cbAutoMode: QtWidgets.QCheckBox
    sbLowerLimit: QtWidgets.QDoubleSpinBox
    cbLowerLimit: QtWidgets.QCheckBox
    sbUpperLimit: QtWidgets.QDoubleSpinBox
    cbUpperLimit: QtWidgets.QCheckBox
    sbKp: QtWidgets.QDoubleSpinBox
    sbKi: QtWidgets.QDoubleSpinBox
    sbKd: QtWidgets.QDoubleSpinBox
    pbGetPID: QtWidgets.QToolButton
    pbSetPID: QtWidgets.QToolButton
    leSensor: QtWidgets.QLineEdit
    bbOutput: QtWidgets.QComboBox

    gbPIDcomponents: QtWidgets.QGroupBox
    lbComponents: QtWidgets.QLabel
    pbReset: QtWidgets.QPushButton
    pbComponents: QtWidgets.QPushButton

    def __init__(self, name="TemperatureControllerPanel", actor="TemperatureController",
                 host="localhost",
                 **kwargs):
        # Use initialization of parent class QMainWindow.
        super().__init__(**kwargs)

        # Load the user interface file and show it.
        uic.loadUi("data/ControlPanel.ui", self)
        self.show()

        # Get settings.
        application = QtCore.QCoreApplication.instance()
        if application is not None:
            application.setOrganizationName("NLOQO")
            application.setApplicationName(name)
        self.settings = QtCore.QSettings()

        # Dictionaries for changed values
        self.changedGeneral: Dict[str, Any] = {}
        self.changedPID: Dict[str, Any] = {}

        # Connect actions to slots.
        self.actionClose.triggered.connect(self.close)
        self.actionSettings.triggered.connect(self.openSettings)
        # Connect buttons etc.
        #   General
        self.leDatabaseTable.editingFinished.connect(self.changedDatabaseTable)
        self.sbReadoutInterval.valueChanged.connect(self.changedReadoutInterval)
        self.pbGetGeneral.clicked.connect(self.getGeneral)
        self.pbSetGeneral.clicked.connect(self.setGeneral)
        #   Direct Control
        self.pbOut0.clicked.connect(self.setOutput0)
        self.pbOut1.clicked.connect(self.setOutput1)
        self.pbShutDown.clicked.connect(self.shutDown)
        #   PID
        self.bbId.currentTextChanged.connect(self.selectPID)
        self.sbSetpoint.valueChanged.connect(self.changedSetpoint)
        self.sbLowerLimit.valueChanged.connect(self.changedLowerLimit)
        self.sbUpperLimit.valueChanged.connect(self.changedUpperLimit)
        self.cbLowerLimit.stateChanged.connect(self.changedLowerLimitNone)
        self.cbUpperLimit.stateChanged.connect(self.changedUpperLimitNone)
        self.sbKp.valueChanged.connect(self.changedKp)
        self.sbKi.valueChanged.connect(self.changedKi)
        self.sbKd.valueChanged.connect(self.changedKd)
        self.leSensor.editingFinished.connect(self.changedSensor)
        self.cbAutoMode.stateChanged.connect(self.changedAutoMode)
        self.sbLastOutput.valueChanged.connect(self.changedLastOutput)
        self.pbGetPID.clicked.connect(self.getPID)
        self.pbSetPID.clicked.connect(self.setPID)
        self.bbOutput.currentIndexChanged.connect(self.changedState)
        #   PID components
        self.pbComponents.clicked.connect(self.getComponents)
        self.pbReset.clicked.connect(self.resetPID)
        #   Errors
        self.pbErrorsGet.clicked.connect(self.getErrors)
        self.pbErrorsClear.clicked.connect(self.clearErrors)
        self.pbSensors.clicked.connect(self.getSensors)

        # Connect to the controller
        self.director = ControllerDirector(actor=actor, name=name, host=host)

    @pyqtSlot()
    def closeEvent(self, event):
        """Clean up if the window is closed somehow."""
        # TODO: put in stuff you want to do before closing

        # accept the close event (reject it, if you want to do something else)
        event.accept()

    @pyqtSlot()
    def openSettings(self):
        """Open the settings dialogue and apply changed settings."""
        settings = Settings.Settings()
        if settings.exec():
            # TODO apply changes to variables
            print("settings changed")

    def showError(self, exc=None):
        """Show an error message."""
        message = QtWidgets.QMessageBox()
        icon = QtWidgets.QMessageBox.Icon.Warning
        message.setIcon(icon)
        message.setWindowTitle("Communication error")
        message.setText(("A communication error occurred, please check the "
                         "connection settings and whether the temperature "
                         "controller is running."))
        if exc is not None:
            message.setDetailedText(f"{type(exc).__name__}: {exc}")
        message.exec()

    # General settings
    @pyqtSlot()
    def getGeneral(self):
        """Get the general settings."""
        try:
            table = self.director.get_database_table()
            interval = self.director.get_readout_interval()
        except Exception as exc:
            self.showError(exc)
        else:
            self.leDatabaseTable.setText(table)
            self.sbReadoutInterval.setValue(
                5000 if interval is None else int(interval * 1000))

    @pyqtSlot()
    def setGeneral(self):
        """Set the changed general settings."""
        for key, value in self.changedGeneral.items():
            if key == 'database/table':
                self.director.set_database_table(self.leDatabaseTable.text())
            if key == 'readoutInterval':
                self.director.set_readout_interval(value)
        self.changedGeneral.clear()

    @pyqtSlot()
    def changedDatabaseTable(self):
        """Store the changed database table in the dictionary."""
        self.changedGeneral['database/table'] = self.leDatabaseTable.text()

    @pyqtSlot(int)
    def changedReadoutInterval(self, value):
        """Store the changed readout interval in the dictionary."""
        self.changedGeneral['readoutInterval'] = value

    # Direct Control
    @pyqtSlot()
    def setOutput0(self):
        """Set the output to the value of the corresponding spinbox."""
        self.director.set_output("out0", self.sbOut0.value())

    @pyqtSlot()
    def setOutput1(self):
        """Set the output to the value of the corresponding spinbox."""
        self.director.set_output("out1", self.sbOut1.value())

    @pyqtSlot()
    def shutDown(self):
        """Ask for confirmation and send shut down command."""
        confirmation = QtWidgets.QMessageBox()
        confirmation.setWindowTitle("Really shut down?")
        confirmation.setText(("Do you want to shut down the temperature "
                              "controller? You can not start it with this "
                              "program, but have to do it on the computer "
                              "itself!"))
        icon = QtWidgets.QMessageBox.Icon.Question
        buttons = QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel  # noqa
        confirmation.setIcon(icon)
        confirmation.setStandardButtons(buttons)
        if confirmation.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
            self.director.shut_down_actor()

    # PID values
    @pyqtSlot()
    def getPID(self):
        """Get all the values for the selected PID controller."""
        try:
            data = self.director.get_PID_settings(self.bbId.currentText())
        except Exception as exc:
            self.showError(exc)
            return
        try:
            print(data)
            self.sbSetpoint.setValue(data["setpoint"])
            self.sbKp.setValue(data["Kp"])
            self.sbKi.setValue(data["Ki"])
            self.sbKd.setValue(data["Kd"])
            self.sbLowerLimit.setValue(data["lowerLimit"])
            self.cbLowerLimit.setChecked(data["lowerLimitNone"])
            self.sbUpperLimit.setValue(data["upperLimit"])
            self.cbUpperLimit.setChecked(data["upperLimitNone"])
            self.leSensor.setText(", ".join(data["sensors"]))
            self.cbAutoMode.setChecked(data["autoMode"])
            self.sbLastOutput.setValue(data["lastOutput"])
            self.bbOutput.setCurrentIndex(data["state"])
            self.changedPID.clear()  # Reset changed dictionary.
        except Exception as exc:
            print(data)
            self.showError(exc)

    def gotToFloat(self, received):
        """Turn a received number into a float."""
        if received is None:
            return 0
        return float(received)

    @pyqtSlot()
    def setPID(self):
        """Set the changed values."""
        if self.changedPID:
            print("new values", self.changedPID)  # HACK
            pid_dicts = {}
            for key, value in self.changedPID.items():
                name, par = key.split("/")
                name = name.replace("pid", "")
                try:
                    pid_dicts[name][par] = value
                except KeyError:
                    pid_dicts[name] = {par: value}
            for name, config in pid_dicts.items():
                try:
                    self.director.set_PID_settings(name=name, **config)
                except TypeError as exc:
                    self.showError(exc)

    @pyqtSlot(str)
    def selectPID(self, name):
        """Select the PID controllerwith `name`."""
        self.pbGetPID.clicked.emit()
        self.lbComponents.setText("")

    # Changed PID values
    @pyqtSlot(float)
    def changedSetpoint(self, value):
        """Store the setpoint in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/setpoint'] = value

    @pyqtSlot(float)
    def changedKp(self, value):
        """Store the Kp in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/Kp'] = value

    @pyqtSlot(float)
    def changedKi(self, value):
        """Store the Ki in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/Ki'] = value

    @pyqtSlot(float)
    def changedKd(self, value):
        """Store the Kd in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/Kd'] = value

    @pyqtSlot(float)
    def changedUpperLimit(self, value):
        """Store the upper Limit in the dictionary."""
        if not self.cbUpperLimit.isChecked():
            self.changedPID[f'pid{self.bbId.currentText()}/upper_limit'] = value

    @pyqtSlot(int)
    def changedUpperLimitNone(self, checked):
        """Store the None value of upper limit"""
        if checked:
            # self.changedPID[f'pid{self.bbId.currentText()}/upperLimitNone'] = True
            self.changedPID[f'pid{self.bbId.currentText()}/upper_limit'] = float("inf")
        else:
            # self.changedPID[f'pid{self.bbId.currentText()}/upperLimitNone'] = False
            self.changedPID[f'pid{self.bbId.currentText()}/upper_limit'] = self.sbUpperLimit.value()

    @pyqtSlot(float)
    def changedLowerLimit(self, value):
        """Store the lower Limit in the dictionary."""
        if not self.cbLowerLimit.isChecked():
            self.changedPID[f'pid{self.bbId.currentText()}/lower_limit'] = value

    @pyqtSlot(int)
    def changedLowerLimitNone(self, checked):
        """Store the None value of lower limit"""
        if checked:
            # self.changedPID[f'pid{self.bbId.currentText()}/lowerLimitNone'] = True
            self.changedPID[f'pid{self.bbId.currentText()}/lower_limit'] = float("-inf")
        else:
            # self.changedPID[f'pid{self.bbId.currentText()}/lowerLimitNone'] = False
            self.changedPID[f'pid{self.bbId.currentText()}/lower_limit'] = self.sbLowerLimit.value()

    @pyqtSlot()
    def changedSensor(self):
        """Store the Sensor in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/sensors'] = self.leSensor.text().replace(",", " ").split()  # noqa

    @pyqtSlot(int)
    def changedAutoMode(self, value):
        """Store the auto mode in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/auto_mode'] = value

    @pyqtSlot(float)
    def changedLastOutput(self, value):
        """Store the last output in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/last_output'] = value

    @pyqtSlot(int)
    def changedState(self, value):
        """Store the output state in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/state'] = value

    # Commands
    @pyqtSlot()
    def getComponents(self):
        """Show the pid components."""
        try:
            data = self.director.get_current_PID_state(self.bbId.currentText())
        except Exception as exc:
            self.showError(exc)
        else:
            self.lbComponents.setText(f"{data}")

    @pyqtSlot()
    def resetPID(self):
        """Send a command to reset the PID values of the current controller."""
        try:
            self.director.reset_PID(self.bbId.currentText())
        except Exception as exc:
            self.showError(exc)

    @pyqtSlot()
    def getErrors(self):
        """Show the current log as a table."""
        try:
            log = self.director.get_log()
        except Exception as exc:
            self.showError(exc)
        else:
            self.lbReadout.setText("\n".join(log))

    @pyqtSlot()
    def clearErrors(self):
        """Clear the remote log, afterwards show the new log."""
        try:
            self.director.reset_log()
        except Exception as exc:
            self.showError(exc)
        else:
            self.getErrors()

    @pyqtSlot()
    def getSensors(self):
        """Get the current sensors and values and show them as a table."""
        try:
            sensors = self.director.get_current_data()
        except Exception as exc:
            self.showError(exc)
        else:
            text = "\n".join([f"{key}:\t{value}" for key, value in sensors.items()])
            if text == "":
                text = "None"
            self.lbReadout.setText(text)


def main() -> None:
    parser = ArgumentParser(description=ControlPanel.__doc__)
    parser.add_argument("-r", "--host", help="set the host name of this Node's Coordinator")
    parser.add_argument("-n", "--name", help="set the application name")

    kwargs = vars(parser.parse_args())
    for key, value in list(kwargs.items()):
        # remove not set values
        if value is None:
            del kwargs[key]

    application = QtWidgets.QApplication([])
    panel = ControlPanel(**kwargs)  # noqa: F841
    application.exec()  # start the event loop


if __name__ == "__main__":
    """If called as a script, start the qt system and start the controller."""
    main()
