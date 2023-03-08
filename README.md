# dbus-gridmeter-sml
SML optical readout grid meter driver for victron venus devices

Alpha version, needs more love

Install

* Dateien unter /data/etc/gridmeter-sml installieren
* installscript ausführen
* in /etc/udev/rules.d/serial-starter.rules für das Adaptermodell den eigenen Treiber eintragen
* Treiber in /etc/venus/serial-starter.conf auf Service-Ordner linken
* nun sollte der Treiber gestartet werden wenn das Gerät eingesteckt wird. ggfs kann es nötig sein den installaufruf in /data/rc.local ganz nach oben zu schieben und auch ein sleep 1 danach einzubauen, damit der port nicht weggeschnappt wird
* log: /var/log/gridmeter_sml.ttyUSBx/current


TODO

* alles von gridmeter_sml zu dbus-gridmeter-sml umbenennen
* unnötige Messwerte entfernen
* auto-restart fixen

