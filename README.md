# Temperature Controller

Software zur Steuerung der Klimatisierung im Labor.

Es gibt die Steuerung selbst und ein Control Panel, beide kommunizieren über TCP sockets.


## Installation

### Controller
* TemperatureController.py und die Ordner *controllerData* und *devices* müssen auf der Steuerung sein.
* Im Ordner controllerData die datei *connectionData.py* anlegen mit einem dictionary, das alle Parameter für die datenbank enthält: database = {'host': "hostname",...}
* Falls nötig die sensors.py Datei an die lokalen Begebenheiten anpassen.
* Nötige Python Abhängigkeiten installieren.

### Control Panel
* ControlPanel.ui, ControlPanel.pyw und die Ordner *data* und *devices* müssen auf dem Rechner sein, der fernsteuert.
* Nötige Python Abhängigkeiten installieren.
* Programm starten und in den Settings die IP und Port des zu steuernden Rechners eingeben (Lokalhost geht nicht, es muss die Internetadresse sein).


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