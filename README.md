# Temperature Controller

Software zur Steuerung der Klimatisierung im Labor.

Es gibt die Steuerung selbst und ein Control Panel, beide kommunizieren über TCP sockets.

Zur Absicherung der Software, wurden mit pytest Unittests geschrieben, die im Ordner tests enthalten sind.


## Installation

### Controller

### Der Controller selbst
* TemperatureController.py und die Ordner *controllerData* und *devices* müssen auf der Steuerung sein.
* Im Ordner controllerData die Datei *connectionData.py* anlegen mit einem dictionary, das alle Parameter für die datenbank enthält: database = {'host': "hostname",...}. Alternativ kann die Datei connectionData-sample an die eigenen Bedürfnisse angepasst und umbenannt werden.
* Im Ordner controllerData die Datei *sensors-sample.py* in *sensors.py* umbenennen und an lokale Bedingungen anpassen: Unter welchem Namen welche Sensoren ausgelesen werden sollen.
* Falls nötig die ioDefinition.py Datei an die lokalen Begebenheiten anpassen.
* Nötige Python Abhängigkeiten installieren: PyQt5/PyQt6
* Für die Sensoren: pyvisa (für serielle Kommunikation), Tinkerforge...

### Autostart des Controllers
* In *controllerData/temperature-controller.service* die Dateipfade des Start und Stop-Scripts anpassen
* Ordner erstellen falls noch nicht vorhanden 'mkdir -p ~/.config/systemd/user'
* Symlink einrichten mit 'ln -s controllerData/temperature-controller.service ~/.config/systemd/user/'
* Systemd neu laden: 'systemctl --user daemon-reload'
* Autostart aktivieren: 'systemctl --user enable temperature-controller.service'


### Control Panel
* ControlPanel.ui, ControlPanel.pyw und die Ordner *data* und *devices* müssen auf dem Rechner sein, der fernsteuert.
* Nötige Python Abhängigkeiten installieren.
* Programm starten und in den Settings die IP und Port des zu steuernden Rechners eingeben (Lokalhost geht nicht, es muss die Internetadresse sein). Der Port ist standardmäßig 22001.

### Inbetriebnahme
* TemperatureController starten (Doppelklick, im Terminal oder mit systemctl --user start)
* Panel starten (gleicher oder anderer Rechner)
* Datenbankname eintragen und mit Set bestätigen
* PIDs konfigurieren und Output auf PID stellen.


## Hilfreiche Links

Wichtige Informationen zu git:
 * https://git-scm.com/docs
 * https://ndpsoftware.com/git-cheatsheet.html

Qt Informationen auch bezüglich Python
 * https://doc.qt.io/ Dokumentation allgemein
 * https://doc.qt.io/qt-5/qtdesigner-manual.html Der QTDesigner, eine Software um die GUI zu erstellen
 * https://doc.qt.io/qt-5/designer-using-a-ui-file-python.html Wie man die Designersachen in Python importiert

Tutorials zu PyQt
 * https://www.tutorialspoint.com/pyqt/index.htm
 * https://www.learnpyqt.com
  * https://www.learnpyqt.com/tutorials/plotting-pyqtgraph/
  * https://www.learnpyqt.com/tutorials/signals-slots-events/
  * https://www.learnpyqt.com/tutorials/creating-dialogs-qt-designer/
 * https://www.guru99.com/pyqt-tutorial.html mit Messagebox
