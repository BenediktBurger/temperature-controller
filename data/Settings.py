"""
Module for the settings dialog class.

Created on Thu Nov 26 19:02:38 2020 by Benedikt Moneke
"""

try:
    from PyQt6 import QtCore, QtWidgets, uic
    from PyQt6.QtCore import pyqtSlot
except ModuleNotFoundError:
    from PyQt5 import QtCore, QtWidgets, uic
    from PyQt5.QtCore import pyqtSlot


class Settings(QtWidgets.QDialog):
    """Define the settings dialog and its methods."""

    def __init__(self, *args, **kwargs):
        """Initialize the dialog with the programName as argument of the settings."""
        # Use initialization of parent class QDialog.
        super().__init__(*args, **kwargs)

        # Load the user interface file and show it.
        uic.loadUi("data/Settings.ui", self)
        self.show()

        # Configure settings.
        self.settings = QtCore.QSettings()
        # Convenience list for widgets with value(), SetValue() methods.
        self.sets = (
            # name of widget, key of setting, defaultValue, type of defaultValue
            # (self.leIP, 'IPaddress', "", str),  LINE-edit
            (self.sbPort, 'port', 22001, int),
        )
        self.readValues()

        # CONNECT BUTTONS.
        # Define RestoreDefaults button and connect it.
        #self.pbRestoreDefaults = self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButtons.RestoreDefaults)
        #self.pbRestoreDefaults.clicked.connect(self.restoreDefaults)
        # TODO: example a fileDialog
        # self.btSavePath.clicked.connect(self.openFileDialog)

    @pyqtSlot()
    def readValues(self):
        """Read the stored values and show them on the user interface."""
        for setting in self.sets:
            widget, name, value, typ = setting
            widget.setValue(self.settings.value(name, defaultValue=value, type=typ))
        self.leIP.setText(self.settings.value('IPaddress', defaultValue="127.0.0.1", type=str))
        # TODO: read settings and write them to the field
        # self.Interval.setValue(self.settings.value("interval", defaultValue=5000, type=int))

    @pyqtSlot()
    def restoreDefaults(self):
        """Restore the user interface to default values."""
        for setting in self.sets:
            widget, name, value, typ = setting
            widget.setValue(value)
        self.leIP.setText("127.0.0.1")

    @pyqtSlot()
    def accept(self):
        """Save the values from the user interface in the settings."""
        # is executed, if pressed on a button with the accept role
        for setting in self.sets:
            widget, name, value, typ = setting
            self.settings.setValue(name, widget.value())
        self.settings.setValue('IPaddress', self.leIP.text())
        # TODO: save the values from the fields into settings
        # self.settings.setValue('savePath', self.leSavePath.text())
        super().accept()  # make the normal accept things

    '''
    TEMPLATE: a possible file dialog
    def openFileDialog(self):
        """Open a file path dialog."""
        self.savePath = QtWidgets.QFileDialog.getExistingDirectory(self, "Save path")
        self.leSavePath.setText(self.savePath)
    '''
