# dbus-gridmeter-sml
SML optical readout grid meter driver for victron venus devices

Alpha version, use by own risk

## prerequisites
* install pip:
   * opkg update
   * opkg install python3-pip
* then install smllib
   * python -m pip install smllib

## Install
* copy or clone files into /data/etc/dbus-gridmeter_sml
* run install.sh
* add /etc/udev/rules.d/serial-starter.rules a rule for your own serial optical adapter. Example:
    
    ACTION=="add", ENV{ID_BUS}=="usb", ENV{ID_MODEL}=="CP2102_USB_to_UART_Bridge_Controller", ENV{VE_SERVICE}="gridmeter_sml"

* add link in /data/conf/serial-starter.d to link the service name you choose in serial-starter.rules to the service folder. Example:

    service gridmeter_sml dbus-gridmeter_sml

* now dbus-gridmeter-sml should be started when you plug in the usb adapter
* it is recommended to move the entry in /data/rc.local up to be the first entry, so that on reboot the driver is called befor a serialbattery driver grabs the port. serialbattery will misinterprete a SML meter for some erratic battery. Also add a "sleep 1" to give it more time to run
* find log here: /var/log/dbus_gridmeter_sml.ttyUSBx/current
