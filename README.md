# dbus-gridmeter-sml
SML optical readout grid meter driver for victron venus devices

https://github.com/timostark/venus.dbus-iobroker-smartmeter was taken as comfortable starting point, thank you for the fish.

This driver makes it possible to connect an optical smart meter reading head like [this at Amazon](https://www.amazon.de/Hichi-Lesekopf-Stromz%C3%A4hler-optisch-auslesen/dp/B0BTC8RSKL/ref=sr_1_3) to an Raspi with Venus OS and let it's ESS control the Multiplus for zero feed in.

## prerequisites
* install pip:
   * opkg update
   * opkg install python3-pip
* then install smllib
   * python -m pip install smllib

## Install
* copy or clone files into /data/etc/dbus-gridmeter_sml
* run install.sh
* add link in /data/conf/serial-starter.d to link the service name you choose in serial-starter.rules to the service folder. Example:

    alias default gridmeter_sml
    service gridmeter_sml dbus-gridmeter_sml

* now dbus-gridmeter-sml should be started when you plug in the usb adapter and smartmeter data can be parsed in 10s or less
* it is recommended to move the entry in /data/rc.local up to be the first entry, so that on reboot the driver is called befor a serialbattery driver grabs the port. serialbattery will misinterprete a SML meter for some erratic battery. Also add a "sleep 1" to give it more time to run
* find log here: /var/log/dbus_gridmeter_sml.ttyUSBx/current
