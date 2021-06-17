"""
Main file of the base program.

created on 23.11.2020 by Benedikt Moneke
"""

# Standard packages.
try:
    from PyQt6 import QtCore, QtWidgets, uic
    from PyQt6.QtCore import pyqtSlot
except ModuleNotFoundError:
    from PyQt5 import QtCore, QtWidgets, uic
    from PyQt5.QtCore import pyqtSlot
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
        #   PID components
        self.pbComponents.clicked.connect(self.getComponents)
        self.pbReset.clicked.connect(self.resetPID)

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

    # General settings
    @pyqtSlot()
    def getGeneral(self):
        """Get the general settings."""
        keys = ['database/table', 'readoutInterval']
        typ, data = self.com.sendObject('GET', keys)
        self.leDatabaseTable.setText(data['database/table'])
        self.sbReadoutInterval.setValue(5000 if data['readoutInterval'] is None else int(data['readoutInterval']))

    @pyqtSlot()
    def setGeneral(self):
        """Set the changed general settings."""
        if self.changedGeneral != {}:
            self.com.sendObject('SET', self.changedGeneral)
            self.changedGeneral.clear()

    @pyqtSlot()
    def changedDatabaseTable(self):
        """Store the changed database table in the dictionary."""
        self.changedGeneral['database/table'] = self.leDatabaseTable.text()

    @pyqtSlot(int)
    def changedReadoutInterval(self, value):
        """Store the changed readout interval in the dictionary."""
        self.changedGeneral['readoutInterval'] = value

    # PID values
    @pyqtSlot()
    def getPID(self):
        """Get all the values for the selected PID controller."""
        name = f"pid{self.bbId.currentText()}"
        keys = [f"{name}/setpoint", f"{name}/Kp", f"{name}/Ki", f"{name}/Kd",
                f"{name}/lowerLimit", f"{name}/upperLimit", f"{name}/sensor",
                f"{name}/autoMode", f"{name}/lastOutput"]
        typ, data = self.com.sendObject('GET', keys)
        self.sbSetpoint.setValue(self.gotToFloat(data[keys[0]]))
        self.sbKp.setValue(self.gotToFloat(data[keys[1]]))
        self.sbKi.setValue(self.gotToFloat(data[keys[2]]))
        self.sbKd.setValue(self.gotToFloat(data[keys[3]]))
        self.sbLowerLimit.setValue(self.gotToFloat(data[keys[4]]))
        self.cbLowerLimit.setChecked(True if data[keys[4]] is None else False)
        self.sbUpperLimit.setValue(self.gotToFloat(data[keys[5]]))
        self.cbUpperLimit.setChecked(True if data[keys[5]] is None else False)
        self.leSensor.setText(data[keys[6]])
        self.cbAutoMode.setChecked(False if data[keys[7]] is False else True)
        self.sbLastOutput.setValue(self.gotToFloat(data[keys[8]]))
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
            self.com.sendObject('SET', self.changedPID)
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
            self.changedPID[f'pid{self.bbId.currentText()}/upperLimit'] = None
        else:
            self.changedPID[f'pid{self.bbId.currentText()}/upperLimit'] = self.sbUpperLimit.value()

    @pyqtSlot(float)
    def changedLowerLimit(self, value):
        """Store the lower Limit in the dictionary."""
        self.changedPID[f'pid{self.bbId.currentText()}/lowerLimit'] = value

    @pyqtSlot(int)
    def changedLowerLimitNone(self, checked):
        """Store the None value of lower limit"""
        if checked:
            self.changedPID[f'pid{self.bbId.currentText()}/lowerLimit'] = None
        else:
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

    # Commands
    @pyqtSlot()
    def getComponents(self):
        """Show the pid components."""
        key = f"pid{self.bbId.currentText()}"
        typ, data = self.com.sendObject('CMD', [key, "components"])
        self.lbComponents.setText(f"{data[key+'/components']}")

    @pyqtSlot()
    def resetPID(self):
        self.com.sendObject('CMD', [f"pid{self.bbId.currentText()}", "reset"])


if __name__ == '__main__':  # if this is the started script file
    """Start the main window if this is the called script file."""
    app = QtWidgets.QApplication(sys.argv)  # create an application
    mainwindow = ControlPanel()  # start the first widget, the main window
    app.exec()  # start the application with its Event loop
