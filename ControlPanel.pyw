#!/usr/bin/env python3
"""
Main file of the base program.

created on 23.11.2020 by Benedikt Moneke
"""

# Standard packages.
try:
    from PyQt6 import QtCore, QtWidgets, uic
    from PyQt6.QtCore import pyqtSlot
    qtVersion = 6
except ModuleNotFoundError:
    from PyQt5 import QtCore, QtWidgets, uic
    from PyQt5.QtCore import pyqtSlot
    qtVersion = 5
import sys

from devices import intercom

# Local packages.
from data import Settings


class ControlPanel(QtWidgets.QMainWindow):
    """Define the main window and essential methods of the program."""

    def __init__(self, *args, **kwargs):
        """Initialize the main window and its settings."""
        # Use initialization of parent class QMainWindow.
        super().__init__(*args, **kwargs)

        # Load the user interface file and show it.
        uic.loadUi("ControlPanel.ui", self)
        self.show()

        # Get settings.
        application = QtCore.QCoreApplication.instance()
        application.setOrganizationName("NLOQO")
        application.setApplicationName("TemperatureControllerPanel")
        self.settings = QtCore.QSettings()

        # Dictionaries for changed values
        self.changedGeneral = {}
        self.changedPID = {}

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

        # Connect to the controller
        self.connect()

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
            self.connect()
            print("settings changed")

    def connect(self):
        """Create a communicator object."""
        self.com = intercom.Intercom(self.settings.value('IPaddress', defaultValue="127.0.0.1", type=str),
                                     self.settings.value('port', defaultValue=22001, type=int))

    def showError(self, exc=None):
        """Show an error message."""
        message = QtWidgets.QMessageBox()
        if qtVersion == 6:
            icon = QtWidgets.QMessageBox.Icon.Warning
        else:
            icon = QtWidgets.QMessageBox.Warning
        message.setIcon(icon)
        message.setWindowTitle("Communication error")
        message.setText("A communication error occurred, please check the connection settings and whether the temperature controller is running.")
        if exc is not None:
            message.setDetailedText(f"{type(exc).__name__}: {exc}")
        message.exec()

    def sendObject(self, typ, data):
        """Send an object and handle the errors."""
        responseTyp, content = self.com.sendObject(typ, data)
        if responseTyp == 'ERR':
            raise ConnectionError(content.decode('ascii'))
        else:
            return responseTyp, content

    # General settings
    @pyqtSlot()
    def getGeneral(self):
        """Get the general settings."""
        keys = ['database/table', 'readoutInterval']
        try:
            typ, data = self.sendObject('GET', keys)
        except Exception as exc:
            self.showError(exc)
        else:
            self.leDatabaseTable.setText(data['database/table'])
            self.sbReadoutInterval.setValue(5000 if data['readoutInterval'] is None else int(data['readoutInterval']))

    @pyqtSlot()
    def setGeneral(self):
        """Set the changed general settings."""
        if self.changedGeneral != {}:
            try:
                self.sendObject('SET', self.changedGeneral)
            except Exception as exc:
                self.showError(exc)
            else:
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
        try:
            self.sendObject('CMD', ["out0", self.sbOut0.value()])
        except Exception as exc:
            self.showError(exc)

    @pyqtSlot()
    def setOutput1(self):
        """Set the output to the value of the corresponding spinbox."""
        try:
            self.sendObject('CMD', ["out1", self.sbOut1.value()])
        except Exception as exc:
            self.showError(exc)

    @pyqtSlot()
    def shutDown(self):
        """Ask for confirmation and send shut down command."""
        confirmation = QtWidgets.QMessageBox()
        confirmation.setWindowTitle("Really shut down?")
        confirmation.setText("Do you want to shut down the temperature controller? You can not start it with this program, but have to do it on the computer itself!")
        if qtVersion == 6:
            icon = QtWidgets.QMessageBox.Icon.Question
            buttons = [QtWidgets.QMessageBox.StandardButtons.Yes, QtWidgets.QMessageBox.StandardButtons.Cancel]
        else:
            icon = QtWidgets.QMessageBox.Question
            buttons = [QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.Cancel]
        confirmation.setIcon(icon)
        confirmation.setStandardButtons(buttons[0] | buttons[1])
        if confirmation.exec() == buttons[0]:
            try:
                self.com.send('OFF')
            except Exception as exc:
                self.showError(exc)

    # PID values
    @pyqtSlot()
    def getPID(self):
        """Get all the values for the selected PID controller."""
        name = f"pid{self.bbId.currentText()}"
        keys = [f"{name}/setpoint", f"{name}/Kp", f"{name}/Ki", f"{name}/Kd",
                f"{name}/lowerLimit", f"{name}/lowerLimitNone", f"{name}/upperLimit", f"{name}/upperLimitNone",
                f"{name}/sensor", f"{name}/autoMode", f"{name}/lastOutput", f"{name}/state"]
        try:
            typ, data = self.sendObject('GET', keys)
        except Exception as exc:
            self.showError(exc)
        else:
            self.sbSetpoint.setValue(self.gotToFloat(data[keys[0]]))
            self.sbKp.setValue(self.gotToFloat(data[keys[1]]))
            self.sbKi.setValue(self.gotToFloat(data[keys[2]]))
            self.sbKd.setValue(self.gotToFloat(data[keys[3]]))
            self.sbLowerLimit.setValue(self.gotToFloat(data[keys[4]]))
            self.cbLowerLimit.setChecked(False if data[keys[5]] in ("0", "false") else True)
            self.sbUpperLimit.setValue(self.gotToFloat(data[keys[6]]))
            self.cbUpperLimit.setChecked(False if data[keys[7]] in ("0", "false") else True)
            self.leSensor.setText(data[keys[8]])
            self.cbAutoMode.setChecked(False if data[keys[9]] in ("0", "false") else True)
            self.sbLastOutput.setValue(self.gotToFloat(data[keys[10]]))
            self.bbOutput.setCurrentIndex(int(self.gotToFloat(data[keys[11]])))
            self.changedPID.clear()  # Reset changed dictionary.

    def gotToFloat(self, received):
        """Turn a received number into a float, because sometimes it is a string"""
        if received is None:
            return 0
        return float(received)

    @pyqtSlot()
    def setPID(self):
        """Set the changed values."""
        if self.changedPID != {}:
            try:
                self.sendObject('SET', self.changedPID)
            except Exception as exc:
                self.showError(exc)
            else:
                self.changedPID.clear()

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
        self.changedPID[f'pid{self.bbId.currentText()}/upperLimit'] = value

    @pyqtSlot(int)
    def changedUpperLimitNone(self, checked):
        """Store the None value of upper limit"""
        if checked:
            self.changedPID[f'pid{self.bbId.currentText()}/upperLimitNone'] = True
        else:
            self.changedPID[f'pid{self.bbId.currentText()}/upperLimitNone'] = False
            self.changedPID[f'pid{self.bbId.currentText()}/upperLimit'] = self.sbUpperLimit.value()

    @pyqtSlot(float)
    def changedLowerLimit(self, value):
        """Store the lower Limit in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/lowerLimit'] = value

    @pyqtSlot(int)
    def changedLowerLimitNone(self, checked):
        """Store the None value of lower limit"""
        if checked:
            self.changedPID[f'pid{self.bbId.currentText()}/lowerLimitNone'] = True
        else:
            self.changedPID[f'pid{self.bbId.currentText()}/lowerLimitNone'] = False
            self.changedPID[f'pid{self.bbId.currentText()}/lowerLimit'] = self.sbLowerLimit.value()

    @pyqtSlot()
    def changedSensor(self):
        """Store the Sensor in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/sensor'] = self.leSensor.text()

    @pyqtSlot(int)
    def changedAutoMode(self, value):
        """Store the auto mode in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/autoMode'] = value

    @pyqtSlot(float)
    def changedLastOutput(self, value):
        """Store the last output in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/lastOutput'] = value

    @pyqtSlot(int)
    def changedState(self, value):
        """Store the output state in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/state'] = value

    # Commands
    @pyqtSlot()
    def getComponents(self):
        """Show the pid components."""
        key = f"pid{self.bbId.currentText()}"
        try:
            typ, data = self.sendObject('CMD', [key, "components"])
        except Exception as exc:
            self.showError(exc)
        else:
            self.lbComponents.setText(f"{data[key+'/components']}")

    @pyqtSlot()
    def resetPID(self):
        try:
            self.sendObject('CMD', [f"pid{self.bbId.currentText()}", "reset"])
        except Exception as exc:
            self.showError(exc)

    @pyqtSlot()
    def getErrors(self):
        try:
            typ, data = self.sendObject('GET', ['errors'])
            errors = data['errors']
        except Exception as exc:
            self.showError(exc)
        else:
            text = ""
            for key in errors.keys():
                text += f"{key}:\t{errors[key]}\n"
            if text == "":
                text = "None"
            self.lbErrors.setText(text)

    @pyqtSlot()
    def clearErrors(self):
        try:
            typ, data = self.sendObject('DEL', ['errors'])
        except Exception as exc:
            self.showError(exc)
        else:
            self.getErrors()


if __name__ == '__main__':  # if this is the started script file
    """Start the main window if this is the called script file."""
    app = QtWidgets.QApplication(sys.argv)  # create an application
    mainwindow = ControlPanel()  # start the first widget, the main window
    app.exec()  # start the application with its Event loop
