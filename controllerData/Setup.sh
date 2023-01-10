#! /bin/bash

#######################
# Setup for the temperature controller


# Install python packages.

sudo apt install python3-psycopg2 python3-pyqt5.qtopengl python3-tz python3-tzlocal python3-zmq libudev1 procps


## For serial communication:

#sudo pip3 install pyvisa pyvisa-py


# Install Tinkerforge brick daemon and brick viewer:

cd ~/Downloads
wget --backups=1 https://download.tinkerforge.com/tools/brickd/linux/brickd_linux_latest_armhf.deb
sudo dpkg -i brickd_linux_latest_armhf.deb
wget --backups=1 https://download.tinkerforge.com/tools/brickv/linux/brickv_linux_latest.deb
sudo dpkg -i brickv_linux_latest.deb

# Setup git.

cd ~
if [ ! -d temperature-controller ]
then
	git clone git@git.rwth-aachen.de:benedikt.moneke/temperature-controller.git
else
	cd temperature-controller
	git pull
	cd ~
fi

sudo pip3 install -r temperature-controller/requirements.txt

# Copy sample files, if not yet present
cd ~/temperature-controller/controllerData
cp temperature-controller.service.template temperature-controller.service
cp sensors-sample.py sensors.py
cp connectionData-sample.py connectionData.py
cd ~

# Autostart configuration.
mkdir -p ~/.config/systemd/user
ln -s ~/temperature-controller/controllerData/temperature-controller.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable temperature-controller


# Done.
echo "You still have to setup the connectionData and sensors. Afterwards you can start the controller with 'systemctl --user enable temperature-controller'. Press enter to confirm."
read -s