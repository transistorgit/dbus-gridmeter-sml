#!/bin/bash
#

. /opt/victronenergy/serial-starter/run-service.sh

# app=$(dirname $0)/gridmeter_sml.py

# start -x -s $tty
app="python /opt/victronenergy/gridmeter_sml/gridmeter_sml.py"
args="/dev/$tty"
start $args
