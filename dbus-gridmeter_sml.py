#!/usr/bin/python
from smllib import SmlStreamReader
from smllib import errors as smlerr
import serial
from serial import SerialException

# import normal packages
import platform
import logging
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import configparser  # for config/ini file
import traceback

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__),'/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService

class DbusSmlSmartmeterService:
    def __init__(self, port, servicename, deviceinstance, paths, productname='Smartmeter SML Reader', connection='SML service'):
        self._dbusservice = VeDbusService(f"{servicename}.sml_{deviceinstance:02d}", register=False)
        self._paths = paths
        self.error_counter = 0

        self._config = self._getConfig()
        self.serial_port = serial.Serial(port, 9600, timeout=1)
        if not self.serial_port.is_open:
            logging.error(f"{servicename} /DeviceInstance = {deviceinstance} Can't open serial port {port}")
            sys.exit(1)

        logging.debug("%s /DeviceInstance = %d" %
                      (servicename, deviceinstance))

        sm_serial = self._getSmartMeterSerial()
        if sm_serial is None:
            logging.error(f"{servicename} /DeviceInstance = {deviceinstance} Couldn't read device ID, is a SML device attached?")
            sys.exit(1)

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path(
            '/Mgmt/ProcessVersion', 'Unknown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', '%s on %s' % (connection, port))

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        #self._dbusservice.add_path('/ProductId', 16) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
        # self._dbusservice.add_path('/ProductId', 0xFFFF) # id assigned by Victron Support from SDM630v2.py
        # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Energy Meter
        self._dbusservice.add_path('/ProductId', 45069)
        # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Energy Meter
        self._dbusservice.add_path('/DeviceType', 345)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', productname)
        self._dbusservice.add_path('/FirmwareVersion', 0.3)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', 'grid')
        self.allowed_roles = ['grid', 'pvinverter', 'genset']
        self.default_role = 'grid'
        self.role = self.default_role
        self._dbusservice.add_path('/AllowedRoles', self.allowed_roles)

        # normaly only needed for pvinverter
        self._dbusservice.add_path('/Position', 0)
        self._dbusservice.add_path('/Serial', sm_serial)
        self._dbusservice.add_path('/UpdateIndex', 0)

        # add path values to dbus
        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

        self._dbusservice.register()
        self._dbusservice["/Connected"] = 1

        # last update
        self._lastUpdate = 0

        # add _update function 'timer'
        # pause 500ms before the next request
        gobject.timeout_add(500, self._update)


    def _getSmartMeterSerial(self):
        meter_data = self._getSmlSmartmeterData(True)
        if meter_data is None or not meter_data:
            return None
        return "%s %s" % (meter_data['mfg'],meter_data['serial'])


    def _get_role_instance(self):
        print("GetRoleInstance called")
        return 'grid', 40


    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" %
                    (os.path.dirname(os.path.realpath(__file__))))
        return config


    def _getSmartMeterDeviceId(self):
        value = self._config['DEFAULT']['SmlPathSmartMeterId']
        return value


    def _getSmartMeterOverallConsumption(self):
        value = self._config['DEFAULT']['SmlPathOverallConsumption']
        return value


    def _getSmlSmartmeterData(self, parse = False):
        try:
            start = time.time()
            sml_frame = None
            stream = SmlStreamReader()

            while sml_frame is None:
              # we should get 1 msg per second, but sometimes it takes longer
              if time.time()-start > 6:
                logging.info("Smartmeter IR timeout")
                return None
              try:
                toread = self.serial_port.inWaiting()
                if toread < 1:
                  time.sleep(0.02)
                  continue
                s = self.serial_port.read(toread)
              except SerialException as e:
                logging.warning(traceback.format_exc())
                return None

              # Add more bytes, once it's a complete frame the SmlStreamReader will
              # return the frame instead of None
              stream.add(s)
              try:
                sml_frame = stream.get_frame()
                if sml_frame is None:
                   continue

              except smlerr.CrcError as ce:
                logging.info("CRC Error")
                continue

            # parse values
            obis_values = sml_frame.get_obis()
            mfg = ''
            serialno = ''
            if parse:
              for msg in sml_frame.parse_frame():
                #logging.info(msg.format_msg())
                for list_entry in getattr(msg.message_body, 'val_list', []):
                  if '129-129:199.130.3' in list_entry.obis.obis_code:
                    mfg = list_entry.value
                  if '1-0:0.0.9' in list_entry.obis.obis_code:
                    try:
                      serialno = int(list_entry.value[-8:],16)
                    except ValueError:
                      serialno = list_entry.value

            for list_entry in obis_values:
              #logging.info('%s %s' % (list_entry.obis.obis_code, list_entry.value))
              if '1-0:16.7.0' in list_entry.obis.obis_code:
                power = float(list_entry.value)
              if '1-0:1.8.0' in list_entry.obis.obis_code:
                total = float(list_entry.value) * (10**list_entry.scaler)

            return { 'power': power, 'total': total, 'mfg': mfg, 'serial': serialno }

        except Exception as e:
          logging.error(f"Exception in _getSmlSmartmeterData: {str(e)}")



    def _update(self):
        try:
            # get data from smartmeter
            meter_data = self._getSmlSmartmeterData()

            if meter_data is None or not meter_data:
              # exit on continuous failure - probably due to port probing
              if self.error_counter > 4:
                self._dbusservice['/Ac/Power'] = None
                self._dbusservice['/Ac/L1/Voltage'] = None
                self._dbusservice['/Ac/L2/Voltage'] = None
                self._dbusservice['/Ac/L3/Voltage'] = None
                self._dbusservice['/Ac/L1/Current'] = None
                self._dbusservice['/Ac/L2/Current'] = None
                self._dbusservice['/Ac/L3/Current'] = None
                self._dbusservice['/Ac/L1/Power'] = None
                self._dbusservice['/Ac/L2/Power'] = None
                self._dbusservice['/Ac/L3/Power'] = None
                self._dbusservice['/Ac/Current'] = None
                self._dbusservice['/Ac/Voltage'] = None
                self._dbusservice['/Ac/Energy/Forward'] = None
                self._dbusservice['/Ac/Energy/Reverse'] = None
                sys.exit(1)
              self.error_counter += 1
              return True

            self.error_counter = 0
            #logging.info('meter_data %s' % meter_data)

            # send data to DBus, fake all the values that we not have to make victron happy
            total_value = meter_data['power']
            phase_1 = total_value/3
            phase_2 = total_value/3
            phase_3 = total_value/3
            grid_sold =  0
            grid_bought = meter_data['total']/1000
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
            self._dbusservice['/Ac/Voltage'] = voltage

            self._dbusservice['/Ac/Energy/Forward'] = grid_bought
            self._dbusservice['/Ac/Energy/Reverse'] = grid_sold

            # increment UpdateIndex - to show that new data is available
            index = self._dbusservice['/UpdateIndex'] + 1  # increment index
            if index > 255:   # maximum value of the index
                index = 0       # overflow from 255 to 0
            self._dbusservice['/UpdateIndex'] = index
            self._dbusservice['/DeviceInstance'] = 40  # muss irgendwie aktiv gesetzt werden damit es ankommt, sollte eigentlich nicht nötig sein


            # update lastupdate vars
            self._lastUpdate = time.time()
        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)
            sys.exit(1)

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
            sys.exit(-1)

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
                '/Ac/Energy/Forward': {'initial': None, 'textformat': _kwh},
                # energy sold to the grid
                '/Ac/Energy/Reverse': {'initial': None, 'textformat': _kwh},
                '/Ac/Power': {'initial': 0, 'textformat': _w},

                '/Ac/Current': {'initial': 0, 'textformat': _a},
                '/Ac/Voltage': {'initial': 230, 'textformat': _v},

                '/Ac/L1/Voltage': {'initial': 230, 'textformat': _v},
                '/Ac/L2/Voltage': {'initial': 230, 'textformat': _v},
                '/Ac/L3/Voltage': {'initial': 230, 'textformat': _v},
                '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
            })

        logging.info(
            'Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)
        sys.exit(1)


if __name__ == "__main__":
    main()

