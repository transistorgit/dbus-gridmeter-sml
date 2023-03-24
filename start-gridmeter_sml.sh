#!/bin/bash
#

. /opt/victronenergy/serial-starter/run-service.sh

# app=$(dirname $0)/dbus-gridmeter_sml.py

# start -x -s $tty
app="python /opt/victronenergy/dbus-gridmeter_sml/dbus-gridmeter_sml.py"
args="/dev/$tty"
start $args
