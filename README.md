# Temperature Controller

Software zur Steuerung der Klimatisierung im Labor.

Es gibt die Steuerung selbst und ein Control Panel, beide kommunizieren über TCP sockets.

Zur Absicherung der Software, wurden mit pytest Unittests geschrieben, die im Ordner *tests* enthalten sind.


## Installation

### Controller

Zur Installation gibt es ein Shell-Script *controllerData/Setup.sh*, das die meisten Schritte automatisch ausführt. Es bleiben die lokale Konfiguration (*connectionData.py* und *sensors.py*) und das erste Starten übrig.

Die einzelnen Schritte sind folgend erklärt.


### Der Controller selbst
* Python (>=3.9) installieren.
TemperatureController.py und die Ordner *controllerData* und *devices* müssen auf der Steuerung sein.
* Im Ordner controllerData die Datei *connectionData.py* modifizieren mit einem dictionary, das alle Parameter für die datenbank enthält: `database = {'host': "hostname",...}`.
* Im Ordner controllerData die Datei *sensors.py* umbenennen und an lokale Bedingungen anpassen: Unter welchem Namen welche Sensoren ausgelesen werden sollen. Dort können auch Offsets etc. definiert werden.
* Nötige Python Abhängigkeiten installieren: PyQt5/PyQt6.
* Für die Sensoren: tinkerforge und was man für sonstige Sensoren braucht, zum Beispiel pyvisa für serielle Kommunikation.

### Autostart des Controllers
* In *controllerData/temperature-controller.service* die Dateipfade des Start und Stop-Scripts anpassen.
* Ordner erstellen falls noch nicht vorhanden `mkdir -p ~/.config/systemd/user`.
* Symlink einrichten mit `ln -s ~/temperature-controller/controllerData/temperature-controller.service ~/.config/systemd/user/`.
* Systemd neu laden: `systemctl --user daemon-reload`.
* Autostart aktivieren: `systemctl --user enable temperature-controller`.
* Mit `systemctl --user start/stop/restart temperature-controller` kann der Service gestartet, gestoppt, neu gestartet werden. Zum Stoppen wird *stopController.py* verwendet, das den Stopp-Befehl wie das ControlPanel verwendet.


### Control Panel
* *ControlPanel.ui*, *ControlPanel.pyw* und die Ordner *data* und *devices* müssen auf dem Rechner sein, der fernsteuert.
* Nötige Python Abhängigkeiten installieren.
* Programm starten und in den Settings die IP und Port des zu steuernden Rechners eingeben (Lokalhost geht nicht, es muss die Internetadresse sein). Der Port ist standardmäßig 22001.

### Inbetriebnahme
* TemperatureController starten (Doppelklick, im Terminal, oder mit `systemctl --user start temperature-controller` wenn der Service installiert wurde).
* Panel starten (gleicher oder anderer Rechner).
* Name der Tabelle in der Datenbank eintragen und mit *Set* bestätigen.
* PIDs konfigurieren und Output auf PID stellen.
