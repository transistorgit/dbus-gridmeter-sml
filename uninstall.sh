#!/bin/bash
set -x

DRIVERNAME=dbus-gridmeter_sml

rm -rf /opt/victronenergy/service/$DRIVERNAME
rm -rf /opt/victronenergy/service-templates/$DRIVERNAME
rm -rf /opt/victronenergy/$DRIVERNAME

pkill -f "python .*/$DRIVERNAME.py"
