#!/usr/bin/python
from smllib import SmlStreamReader
from smllib import errors as smlerr
import serial

# import normal packages
from vedbus import VeDbusService
import platform
import logging
import os
from os import _exit as os_exit
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import configparser  # for config/ini file

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__),
                '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))


class DbusSmlSmartmeterService:
    def __init__(self, port, servicename, deviceinstance, paths, productname='Smartmeter SML Reader', connection='Smartmeter eHz SML service'):
        self._dbusservice = VeDbusService("{}.sml_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        self._config = self._getConfig()
        self.serial_port = serial.Serial(port, 9600, timeout=.3)
        if not self.serial_port.is_open:
            logging.error(f"{servicename} /DeviceInstance = {deviceinstance} Can't open serial port {port}")
            exit(1)

        logging.debug("%s /DeviceInstance = %d" %
                      (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path(
            '/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        #self._dbusservice.add_path('/ProductId', 16) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
        # self._dbusservice.add_path('/ProductId', 0xFFFF) # id assigned by Victron Support from SDM630v2.py
        # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Engerie Meter
        self._dbusservice.add_path('/ProductId', 45069)
        # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Engerie Meter
        self._dbusservice.add_path('/DeviceType', 345)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', productname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.1)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', 'grid')
        self.allowed_roles = ['grid', 'pvinverter', 'genset']
        self.default_role = 'grid'
        self.role = self.default_role
        self._dbusservice.add_path('/AllowedRoles', self.allowed_roles)

        # normaly only needed for pvinverter
        self._dbusservice.add_path('/Position', 0)
        self._dbusservice.add_path('/Serial', self._getSmartMeterSerial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        # add path values to dbus
        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

        # last update
        self._lastUpdate = 0

        # add _update function 'timer'
        # pause 1000ms before the next request
        gobject.timeout_add(500, self._update)

        # add _signOfLife 'timer' to get feedback in log every 5minutes
        gobject.timeout_add(self._getSignOfLifeInterval()
                            * 60*1000, self._signOfLife)

    def _getSmartMeterSerial(self):
        # TODO
        return 12345

    def _get_role_instance(self):
      print("GetRoleInstance called")
      return 'grid', 40

    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" %
                    (os.path.dirname(os.path.realpath(__file__))))
        return config

    def _getSignOfLifeInterval(self):
        value = self._config['DEFAULT']['SignOfLifeLog']

        if not value:
            value = 0

        return int(value)

    def _getSmartMeterDeviceId(self):
        value = self._config['DEFAULT']['SmlPathSmartMeterId']
        return value

    def _getSmartMeterOverallConsumption(self):
        value = self._config['DEFAULT']['SmlPathOverallConsumption']
        return value

    def _getSmlSmartmeterData(self):
        try:
            sml_frame = None
            stream = SmlStreamReader()
            while sml_frame is None:
              try:
                s = self.serial_port.read(100)
              except serial.serialutil.SerialException:
                print("Port blocked, bailing out")
                raise
              stream.add(s)
              try:
                sml_frame = stream.get_frame()
              except smlerr.CrcError as ce:
                print("CRC Error")
                continue

            # Add more bytes, once it's a complete frame the SmlStreamReader will
            # return the frame instead of None

            obis_values = sml_frame.get_obis()

            for list_entry in obis_values:
              if '1-0:16.7.0' in list_entry.obis.obis_code:
                power = list_entry.value
                #print(f"Wirkleistung: {power}W")
                return power

        except Exception as e:
          logging.error(f"Exception in _getSmlSmartmeterData: {str(e)}")
          print(f"Exception: {str(e)}")
          raise


    def _signOfLife(self):
        logging.info("--- Start: sign of life ---")
        logging.info("Last _update() call: %s" % (self._lastUpdate))
        logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
        logging.info("--- End: sign of life ---")
        return True

    def _update(self):
        try:
            # get data from Senec
            meter_data = self._getSmlSmartmeterData() #currently only power

            # send data to DBus
            total_value = meter_data
            phase_1 = meter_data/3 
            phase_2 = meter_data/3
            phase_3 = meter_data/3
            grid_sold = 0
            grid_bought = 0
            voltage = 230

            # positive: consumption, negative: feed into grid
            self._dbusservice['/Ac/Power'] = total_value
            self._dbusservice['/Ac/L1/Voltage'] = voltage
            self._dbusservice['/Ac/L2/Voltage'] = voltage
            self._dbusservice['/Ac/L3/Voltage'] = voltage
            self._dbusservice['/Ac/L1/Current'] = phase_1 / voltage
            self._dbusservice['/Ac/L2/Current'] = phase_2 / voltage
            self._dbusservice['/Ac/L3/Current'] = phase_3 / voltage
            self._dbusservice['/Ac/L1/Power'] = phase_1
            self._dbusservice['/Ac/L2/Power'] = phase_2
            self._dbusservice['/Ac/L3/Power'] = phase_3

            self._dbusservice['/Ac/Current'] = total_value / voltage
            self._dbusservice['/Ac/Voltage'] = phase_3

            ##self._dbusservice['/Ac/L1/Energy/Forward'] = (meter_data['emeters'][0]['total']/1000)
            self._dbusservice['/Ac/Energy/Forward'] = grid_bought
            self._dbusservice['/Ac/Energy/Reverse'] = grid_sold

            # logging
            ##logging.info("House Consumption (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
            #logging.info("L1: %s L2: %s L3: %s" % (self._dbusservice['/Ac/L1/Power'],self._dbusservice['/Ac/L2/Power'],self._dbusservice['/Ac/L3/Power']))
            ##logging.debug("House Forward (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
            ##logging.debug("House Reverse (/Ac/Energy/Revers): %s" % (self._dbusservice['/Ac/Energy/Reverse']))
            # logging.debug("---");

            # increment UpdateIndex - to show that new data is available
            index = self._dbusservice['/UpdateIndex'] + 1  # increment index
            if index > 255:   # maximum value of the index
                index = 0       # overflow from 255 to 0
            self._dbusservice['/UpdateIndex'] = index

            # update lastupdate vars
            self._lastUpdate = time.time()
        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)
            os_exit(1)

        # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True  # accept the change


    

def main():
    # configure logging
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO,
                        handlers=[
                            logging.FileHandler(
                                "%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                            logging.StreamHandler()
                        ])

    try:
        logging.info("Start gridmeter_sml")

        if len(sys.argv) > 1:
            port = sys.argv[1]
        else:
            logging.error("Error: no port given")
            exit(-1)

        from dbus.mainloop.glib import DBusGMainLoop
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        # formatting
        def _kwh(p, v): return (str(round(v, 2)) + ' KWh')
        def _a(p, v): return (str(round(v, 1)) + ' A')
        def _w(p, v): return (str(round(v, 1)) + ' W')
        def _v(p, v): return (str(round(v, 1)) + ' V')

        # start our main-service
        pvac_output = DbusSmlSmartmeterService(
            port,
            servicename='com.victronenergy.grid',
            deviceinstance=40,
            paths={
                # energy bought from the grid
                '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                # energy sold to the grid
                '/Ac/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
                '/Ac/Power': {'initial': 0, 'textformat': _w},

                '/Ac/Current': {'initial': 0, 'textformat': _a},
                '/Ac/Voltage': {'initial': 0, 'textformat': _v},

                '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L1/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/L2/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/L3/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/L1/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
                '/Ac/L2/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
                '/Ac/L3/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
            })

        logging.info(
            'Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)


if __name__ == "__main__":
    main()

