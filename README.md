# dbus-gridmeter-sml
SML optical readout grid meter driver for victron venus devices

Dateien unter /data/etc/dbus-gridmeter-sml installieren
installscript ausführen
in /etc/udev/rules.d/serial-starter.rules für das Adaptermodell den eigenen Treiber eintragen
Treiber in /etc/venus/serial-starter.conf auf Service-Ordner linken
nun sollte der Treiber gestartet werden wenn das Gerät eingesteckt wird.
log: /var/log/gridmeter_sml.ttyUSBx/current
