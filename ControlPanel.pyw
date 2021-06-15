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

        self.changed = {}  # Dictionary for changed values

        # Connect actions to slots.
        self.actionClose.triggered.connect(self.close)
        self.actionSettings.triggered.connect(self.openSettings)
        # Connect buttons etc.
        self.bbId.currentTextChanged.connect(self.selectPID)
        self.sbSetpoint.valueChanged.connect(self.changedSetpoint)
        self.sbLowerLimit.valueChanged.connect(self.changedLowerLimit)
        self.sbUpperLimit.valueChanged.connect(self.changedUpperLimit)
        self.cbLowerLimit.stateChanged.connect(self.changedLowerLimitNone)
        self.cbUpperLimit.stateChanged.connect(self.changedUpperLimitNone)
        self.sbKp.valueChanged.connect(self.changedKp)
        self.sbKi.valueChanged.connect(self.changedKi)
        self.sbKd.valueChanged.connect(self.changedKd)
        self.sbSensor.valueChanged.connect(self.changedSensor)
        self.cbAutoMode.stateChanged.connect(self.changedAutoMode)
        self.sbLastOutput.valueChanged.connect(self.changedLastOutput)

        self.pbGet.clicked.connect(self.getClicked)
        self.pbSet.clicked.connect(self.setClicked)

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

    @pyqtSlot()
    def getClicked(self):
        """Get all the values for the selected PID controller."""
        name = self.bbId.currentText()
        keys = [f"pid{name}/setpoint", f"pid{name}/Kp", f"pid{name}/Ki", f"pid{name}/Kd",
                f"pid{name}/lowerLimit", f"pid{name}/upperLimit", f"pid{name}/sensor",
                f"pid{name}/autoMode", f"pid{name}/lastOutput"]
        typ, data = self.com.sendObject('GET', keys)
        self.sbSetpoint.setValue(self.gotToFloat(data[keys[0]]))
        self.sbKp.setValue(self.gotToFloat(data[keys[1]]))
        self.sbKi.setValue(self.gotToFloat(data[keys[2]]))
        self.sbKd.setValue(self.gotToFloat(data[keys[3]]))
        self.sbLowerLimit.setValue(self.gotToFloat(data[keys[4]]))
        self.cbLowerLimit.setChecked(True if data[keys[4]] is None else False)
        self.sbUpperLimit.setValue(self.gotToFloat(data[keys[5]]))
        self.cbUpperLimit.setChecked(True if data[keys[5]] is None else False)
        self.sbSensor.setValue(int(self.gotToFloat(data[keys[6]])))
        self.cbAutoMode.setChecked(False if data[keys[7]] is False else True)
        self.sbLastOutput.setValue(self.gotToFloat(data[keys[8]]))
        self.changed.clear()  # Reset changed dictionary.

    def gotToFloat(self, received):
        """Turn a received number into a float, because sometimes it is a string"""
        if received is None:
            return 0
        return float(received)

    @pyqtSlot()
    def setClicked(self):
        """Set the changed values."""
        self.com.sendObject('SET', self.changed)
        self.changed.clear()

    @pyqtSlot(str)
    def selectPID(self, name):
        """Select the PID controllerwith `name`."""
        self.pbGet.clicked.emit()
        self.lbComponents.setText("")

    # Changed values
    @pyqtSlot(float)
    def changedSetpoint(self, value):
        """Store the setpoint in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/setpoint'] = value

    @pyqtSlot(float)
    def changedKp(self, value):
        """Store the Kp in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/Kp'] = value

    @pyqtSlot(float)
    def changedKi(self, value):
        """Store the Ki in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/Ki'] = value

    @pyqtSlot(float)
    def changedKd(self, value):
        """Store the Kd in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/Kd'] = value

    @pyqtSlot(float)
    def changedUpperLimit(self, value):
        """Store the upper Limit in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/upperLimit'] = value

    @pyqtSlot(int)
    def changedUpperLimitNone(self, checked):
        """Store the None value of upper limit"""
        if checked:
            self.changed[f'pid{self.bbId.currentText()}/upperLimit'] = None
        else:
            self.changed[f'pid{self.bbId.currentText()}/upperLimit'] = self.sbUpperLimit.value()

    @pyqtSlot(float)
    def changedLowerLimit(self, value):
        """Store the lower Limit in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/lowerLimit'] = value

    @pyqtSlot(int)
    def changedLowerLimitNone(self, checked):
        """Store the None value of lower limit"""
        if checked:
            self.changed[f'pid{self.bbId.currentText()}/lowerLimit'] = None
        else:
            self.changed[f'pid{self.bbId.currentText()}/lowerLimit'] = self.sbLowerLimit.value()

    @pyqtSlot(int)
    def changedSensor(self, value):
        """Store the Sensor in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/sensor'] = value

    @pyqtSlot(int)
    def changedAutoMode(self, value):
        """Store the auto mode in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/autoMode'] = value

    @pyqtSlot(float)
    def changedLastOutput(self, value):
        """Store the last output in the dictionary."""
        self.changed[f'pid{self.bbId.currentText()}/lastOutput'] = value

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
    app.organizationName = "NLOQO"
    app.applicationName = "TemperatureControllerPanel"
    app.organizationDomain = "NLOQO"
    mainwindow = ControlPanel()  # start the first widget, the main window
    app.exec()  # start the application with its Event loop
