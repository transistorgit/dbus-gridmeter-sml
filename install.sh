#!/bin/bash
set -x

#inspired by dbus-serialbattery
#ln -s /data/etc/gridmeter_sml/ /opt/victronenergy/
#ln -s /data/etc/gridmeter_sml/service /opt/victronenergy/service-templates/gridmeter_sml

DRIVERNAME=dbus-gridmeter_sml

#install
rm -rf /opt/victronenergy/service/$DRIVERNAME
rm -rf /opt/victronenergy/service-templates/$DRIVERNAME
rm -rf /opt/victronenergy/$DRIVERNAME
mkdir /opt/victronenergy/$DRIVERNAME
cp -f /data/etc/$DRIVERNAME/* /opt/victronenergy/$DRIVERNAME &>/dev/null
cp -rf /data/etc/$DRIVERNAME/service /opt/victronenergy/service-templates/$DRIVERNAME

#restart if running
pkill -f "python .*/$DRIVERNAME.py"

# add install-script to rc.local to be ready for firmware update
filename=/data/rc.local
if [ ! -f $filename ]; then
    echo "#!/bin/bash" >> $filename
    chmod 755 $filename
fi
grep -qxF "sh /data/etc/$DRIVERNAME/install.sh" $filename || echo "sh /data/etc/$DRIVERNAME/install.sh" >> $filename
