#!/usr/bin/python
#
# Copyright 2014 Matthew Wall
#
# weewx driver that reads data from a file
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
#
# See http://www.gnu.org/licenses/

#
# Based on https://weatherlink.github.io/weatherlink-live-local-api/

# "data":
# {
#     "did":"001D0A700002",
#     "ts":1531754005,
#     "conditions": [
#     {
#             "lsid":48308,                                  // logical sensor ID **(no unit)**
#             "data_structure_type":1,                       // data structure type **(no unit)**
#             "txid":1,                                      // transmitter ID **(no unit)**
#             "temp": 62.7,                                  // most recent valid temperature **(°F)**
#             "hum":1.1,                                     // most recent valid humidity **(%RH)**
#             "dew_point": -0.3,                             // **(°F)**
#             "wet_bulb":null,                               // **(°F)**
#             "heat_index": 5.5,                             // **(°F)**
#             "wind_chill": 6.0,                             // **(°F)**
#             "thw_index": 5.5,                              // **(°F)**
#             "thsw_index": 5.5,                             // **(°F)**
#             "wind_speed_last":2,                           // most recent valid wind speed **(mph)**
#             "wind_dir_last":null,                          // most recent valid wind direction **(°degree)**
#             "wind_speed_avg_last_1_min":4                  // average wind speed over last 1 min **(mph)**
#             "wind_dir_scalar_avg_last_1_min":15            // scalar average wind direction over last 1 min **(°degree)**
#             "wind_speed_avg_last_2_min":42606,             // average wind speed over last 2 min **(mph)**
#             "wind_dir_scalar_avg_last_2_min": 170.7,       // scalar average wind direction over last 2 min **(°degree)**
#             "wind_speed_hi_last_2_min":8,                  // maximum wind speed over last 2 min **(mph)**
#             "wind_dir_at_hi_speed_last_2_min":0.0,         // gust wind direction over last 2 min **(°degree)**
#             "wind_speed_avg_last_10_min":42606,            // average wind speed over last 10 min **(mph)**
#             "wind_dir_scalar_avg_last_10_min": 4822.5,     // scalar average wind direction over last 10 min **(°degree)**
#             "wind_speed_hi_last_10_min":8,                 // maximum wind speed over last 10 min **(mph)**
#             "wind_dir_at_hi_speed_last_10_min":0.0,        // gust wind direction over last 10 min **(°degree)**
#             "rain_size":2,                                 // rain collector type/size **(0: Reserved, 1: 0.01", 2: 0.2 mm, 3:  0.1 mm, 4: 0.001")**
#             "rain_rate_last":0,                            // most recent valid rain rate **(counts/hour)**
#             "rain_rate_hi":null,                           // highest rain rate over last 1 min **(counts/hour)**
#             "rainfall_last_15_min":null,                   // total rain count over last 15 min **(counts)**
#             "rain_rate_hi_last_15_min":0,                  // highest rain rate over last 15 min **(counts/hour)**
#             "rainfall_last_60_min":null,                   // total rain count for last 60 min **(counts)**
#             "rainfall_last_24_hr":null,                    // total rain count for last 24 hours **(counts)**
#             "rain_storm":null,                             // total rain count since last 24 hour long break in rain **(counts)**
#             "rain_storm_start_at":null,                    // UNIX timestamp of current rain storm start **(seconds)**
#             "solar_rad":747,                               // most recent solar radiation **(W/m²)**
#             "uv_index":5.5,                                // most recent UV index **(Index)**
#             "rx_state":2,                                  // configured radio receiver state **(no unit)**
#             "trans_battery_flag":0,                        // transmitter battery status flag **(no unit)**
#             "rainfall_daily":63,                           // total rain count since local midnight **(counts)**
#             "rainfall_monthly":63,                         // total rain count since first of month at local midnight **(counts)**
#             "rainfall_year":63,                            // total rain count since first of user-chosen month at local midnight **(counts)**
#             "rain_storm_last":null,                        // total rain count since last 24 hour long break in rain **(counts)**
#             "rain_storm_last_start_at":null,               // UNIX timestamp of last rain storm start **(sec)**
#             "rain_storm_last_end_at":null                  // UNIX timestamp of last rain storm end **(sec)**
#     },
#     {
#             "lsid":3187671188,
#             "data_structure_type":2,
#             "txid":3,
#             "temp_1":null,                                 // most recent valid soil temp slot 1 **(°F)**
#             "temp_2":null,                                 // most recent valid soil temp slot 2 **(°F)**
#             "temp_3":null,                                 // most recent valid soil temp slot 3 **(°F)**
#             "temp_4":null,                                 // most recent valid soil temp slot 4 **(°F)**
#             "moist_soil_1":null,                           // most recent valid soil moisture slot 1 **(|cb|)**
#             "moist_soil_2":null,                           // most recent valid soil moisture slot 2 **(|cb|)**
#             "moist_soil_3":null,                           // most recent valid soil moisture slot 3 **(|cb|)**
#             "moist_soil_4":null,                           // most recent valid soil moisture slot 4 **(|cb|)**
#             "wet_leaf_1":null,                             // most recent valid leaf wetness slot 1 **(no unit)**
#             "wet_leaf_2":null,                             // most recent valid leaf wetness slot 2 **(no unit)**
#             "rx_state":null,                               // configured radio receiver state **(no unit)**
#             "trans_battery_flag":null                      // transmitter battery status flag **(no unit)**
#     },
#     {
#             "lsid":48307,
#             "data_structure_type":4,
#             "temp_in":78.0,                                // most recent valid inside temp **(°F)**
#             "hum_in":41.1,                                 // most recent valid inside humidity **(%RH)**
#             "dew_point_in":7.8,                            // **(°F)**
#             "heat_index_in":8.4                            // **(°F)**
#     },
#     {
#             "lsid":48306,
#             "data_structure_type":3,
#             "bar_sea_level":30.008,                       // most recent bar sensor reading with elevation adjustment **(inches)**
#             "bar_trend": null,                            // current 3 hour bar trend **(inches)**
#             "bar_absolute":30.008                         // raw bar sensor reading **(inches)**
#     }]
# },
# "error":null }
#


from __future__ import with_statement
import logging
import time

from socket import *
import struct
import time
from typing import Dict, Any, Union

import requests
import json

import weewx.drivers

## DEBUG ONLY
import pprint

DRIVER_NAME = 'WeatherLinkLiveUDP'
DRIVER_VERSION = "0.1"

MM_TO_INCH = 0.0393701

print("BEGIN OF DIVER RUN!!!!!!!")

# Open UDP Socket
comsocket = socket(AF_INET, SOCK_DGRAM)
comsocket.bind(('', 22222))
comsocket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)


try:
    # Test for WeeWX v4 logging
    import weeutil.logger
    import logging

    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style WeeWX logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'WLL: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


def _get_as_float(d, s):
    v = None
    if s in d:
        try:
            v = float(d[s])
        except ValueError as e:
            logerr("cannot read value for '%s': %s" % (s, e))
    return v

def loader(config_dict, engine):
    return FileParseDriver(**config_dict[DRIVER_NAME])

class FileParseDriver(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from a file"""

    def __init__(self, **stn_dict):
        self.poll_interval = float(stn_dict.get('poll_interval', 30))

        self.wll_ip = stn_dict.get('wll_ip')
        #print(self.wll_ip)
        if self.wll_ip is None:
            logerr("No Weatherlink Live URL provided")

        self.timeout = None
        self.StartTime = time.time()

        # Set UDP broadcast for 1 hour.
        self.Real_Time_URL = 'http://%s:80/v1/real_time?duration=3600' % self.wll_ip
        self.CurrentConditions_URL = 'http://%s:80/v1/current_conditions' % self.wll_ip

        self.txid_ISS  = stn_dict.get('ISS_id', 1)
        self.txid_wind = stn_dict.get('wind_id', 1)

        self.last_rain_storm = None
        self.last_rain_storm_start_at = None

        self.LaunchTime = time.time()
        self.UPD_CountDown = 0


        #print(self.Real_Time_URL)
        log.info("Polling interval is %s" % self.poll_interval)

    def genLoopPackets(self):
        ### global URL
        ####UDP_PORT = 22222

        print("Launch Time:", time.strftime("%H:%M:%S", time.gmtime(self.LaunchTime)))
        print("Currnt Time:", time.strftime("%H:%M:%S", time.gmtime(time.time())) )
        try:
            if self.UPD_CountDown < time.time():
                print("KICK ON UDP")
                req = requests.get(self.Real_Time_URL)
                Req_data = req.json()
                self.UPD_CountDown = time.time() + Req_data['data']['duration']
                print ("end UDP = ", time.strftime("%H:%M:%S", time.gmtime(self.UPD_CountDown)))
                print("Currnt Time:", time.strftime("%H:%M:%S", time.gmtime(time.time())))
                ResponseString = "UDP broadcast end:", time.strftime("%H:%M:%S", time.gmtime(self.UPD_CountDown))
                logdbg(ResponseString)

        except Exception as e:
            logerr("read failed: %s" % e)
            pass

        #print(resp)
        #print(resp.status_code)
        while True:
            # read whatever values we can get from the file
            #data = {}
            try:
                self.timeout = time.time() + self.poll_interval
                while time.time() < self.timeout:
                    ########print("Poll Intervall:", self.poll_interval)
                    ###elapsed_time = time.time() - self.StartTime
                    ####print("elapsed Time:", time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
                    #### print("Loop until:", self.timeout)
                    data, wherefrom = comsocket.recvfrom(2048)
                    UDP_data = json.loads(data.decode("utf-8"))
                    if UDP_data["conditions"] == None:
                        print(UDP_data["error"])
                    else:
                        #  print(json_data)
                        timestampUDP = UDP_data['ts']
                        _packet = {'dateTime': timestampUDP,
                                   'usUnits': weewx.US}
                        ### print(UDP_data)
                        for condition in UDP_data['conditions']:
                            if condition["txid"] == 1:
                                ####print(testDict)
                                #print("WIND:", testDict["wind_dir_last"],"/", testDict["wind_speed_last"] )
                                #print("HWnD:", testDict["wind_dir_at_hi_speed_last_10_min"],"/", testDict["wind_speed_hi_last_10_min"] )
                                #print(timestampUDP)
                                ##_packet.update({'windDir': condition["wind_dir_last"]})
                                #_packet.update({'windSpeed': condition["wind_speed_last"]})
                                #_packet.update({'windDir': condition["wind_dir_last"]})
                                #_packet.update({'windGust': condition["wind_speed_hi_last_10_min"]})
                                #_packet.update({'windGustDir': condition["wind_dir_at_hi_speed_last_10_min"]})

                                if "wind_speed_last" in condition:  # most recent valid wind speed **(mph)**
                                    _packet.update({'windSpeed': condition["wind_speed_last"]})

                                if "wind_dir_last" in condition:  # most recent valid wind direction **(°degree)**
                                    _packet.update({'windDir': condition["wind_dir_last"]})

                                if "wind_speed_hi_last_10_min" in condition:  # maximum wind speed over last 10 min **(mph)**
                                    _packet.update({'windGust': condition["wind_speed_hi_last_10_min"]})

                                if "wind_dir_scalar_avg_last_10_min" in condition:  # gust wind direction over last 10 min **(°degree)**
                                    _packet.update({'windGustDir': condition["wind_dir_scalar_avg_last_10_min"]})

                                # Yield UDP
                                yield _packet

                #comsocket.close()
                # with open(self.path) as f:
                #     for line in f:
                #         eq_index = line.find('=')
                #         name = line[:eq_index].strip()
                #         value = line[eq_index + 1:].strip()
                #         data[name] = value

                print("----------------------------")
                elapsed_time = time.time() - self.StartTime
                print("elapsed Time:", time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))

                ##### Actual Data from WLL
                try:
                    CurrentConditionRequest = requests.get(self.CurrentConditions_URL, timeout=1)

                except Exception as error:

                    logerr("Error connecting to the WLL.")
                    logerr("%s" % e)

                    # Sleep for 1 UDP cycle
                    time.sleep(2)

                    continue  # Move Along

                CurrentConditions = CurrentConditionRequest.json()
                ### pprint.pprint(CurrentConditions)

                #print(CurrentConditions['data']['ts'])

                _packet = {'dateTime': CurrentConditions['data']['ts'],
                           'usUnits': weewx.US}


                for condition in CurrentConditions['data']['conditions']:


                    # data_structure_type 1 contains ISS date, use txid

                    if condition['data_structure_type'] == 1 and condition['txid'] == 1:

                        if "temp" in condition:  # most recent valid temperature **(°F)**
                            _packet.update({'outTemp': condition['temp']})
                        if "hum" in condition:  # most recent valid temperature **(°F)**
                            _packet.update({'outHumidity': condition['hum']})

                        if "dew_point" in condition:  # **(°F)**
                            _packet.update({'dewpoint': condition['dew_point']})

                        if "heat_index" in condition:  # **(°F)**
                            _packet.update({'heatindex': condition['heat_index']})

                        if "wind_chill" in condition:  # **(°F)**
                            _packet.update({'windchill': condition['wind_chill']})

                        if "solar_rad" in condition:  #
                            _packet.update({'radiation': condition['solar_rad']})

                        if "uv_index" in condition:  #
                            _packet.update({'UV': condition['uv_index']})

                        ## Wind
                        if "wind_speed_last" in condition:  # most recent valid wind speed **(mph)**
                            _packet.update({'windSpeed': condition["wind_speed_last"]})

                        if "wind_dir_last" in condition:  # most recent valid wind direction **(°degree)**
                            _packet.update({'windDir': condition["wind_dir_last"]})

                        if "wind_speed_hi_last_10_min" in condition:  # maximum wind speed over last 10 min **(mph)**
                            _packet.update({'windGust': condition["wind_speed_hi_last_10_min"]})

                        if "wind_dir_scalar_avg_last_10_min" in condition:  # gust wind direction over last 10 min **(°degree)**
                            _packet.update({'windGustDir': condition["wind_dir_scalar_avg_last_10_min"]})

                        if "trans_battery_flag" in condition:  #
                            _packet.update({'txBatteryStatus': condition['trans_battery_flag']})
                        if "rain_size" in condition:  # rain collector type/size **(0: Reserved, 1: 0.01", 2: 0.2 mm, 3:  0.1 mm, 4: 0.001")**

                            rain_collector_type = condition["rain_size"]

                            if 1 <= rain_collector_type <= 4:

                                if rain_collector_type == 1:
                                    rain_count_size = 0.01

                                elif rain_collector_type == 2:
                                    rain_count_size = 0.2 * MM_TO_INCH

                                elif rain_collector_type == 3:
                                    rain_count_size = 0.1

                                elif rain_collector_type == 4:
                                    rain_count_size = 0.001 * MM_TO_INCH

                                if "rain_rate_last" in condition:  # most recent valid rain rate **(counts/hour)**
                                    _packet.update({'rainRate': float(condition["rain_rate_last"]) * rain_count_size})

                                if "rain_storm" in condition and "rain_storm_start_at" in condition:

                                    # Calculate the rain accumulation by reading the total rain count and checking the increments

                                    rain_storm = condition[
                                        "rain_storm"]  # total rain count since last 24 hour long break in rain **(counts)**
                                    rain_storm_start_at = condition[
                                        "rain_storm_start_at"]  # UNIX timestamp of current rain storm start **(seconds)**

                                    rain_count = 0.0

                                    if self.last_rain_storm is not None and self.last_rain_storm_start_at is not None:

                                        if rain_storm_start_at != self.last_rain_storm_start_at:
                                            rain_count = rain_storm

                                        elif rain_storm >= self.last_rain_storm:
                                            rain_count = float(rain_storm) - float(self.last_rain_storm)

                                    self.last_rain_storm = rain_storm
                                    self.last_rain_storm_start_at = rain_storm_start_at

                                    _packet.update({'rain': rain_count * rain_count_size})

                    # 3 = LSS BAR Current Conditions record
                    elif condition['data_structure_type'] == 3:

                        if "bar_sea_level" in condition:  # most recent bar sensor reading with elevation adjustment **(inches)**
                            _packet.update({'barometer': condition["bar_sea_level"]})

                        if "bar_absolute" in condition:  # raw bar sensor reading **(inches)**
                            _packet.update({'pressure': condition["bar_absolute"]})

                    # 4 = LSS Temp/Hum Current Conditions record
                    elif condition['data_structure_type'] == 4:

                        if "temp_in" in condition:  # most recent valid inside temp **(°F)**
                            _packet.update({'inTemp': condition["temp_in"]})

                        if "hum_in" in condition:  # most recent valid inside humidity **(%RH)**
                            _packet.update({'inHumidity': condition["hum_in"]})

                        if "dew_point_in" in condition:  # **(°F)**
                            _packet.update({'inDewpoint': condition["dew_point_in"]})

                    ####print("GET DATA - NO UDP")

                    # Yield the packets to LOOP
                    #print(_packet)
                    #

                ## except from try to get actual Conditions
                ###except Exception as e

            except Exception as e:
                logerr("read failed: %s" % e)

            yield _packet

            # map the data into a weewx loop packet

            #for vname in data:
            #    _packet[self.label_map.get(vname, vname)] = _get_as_float(data, vname)

            ###yield _packet
            #Sleep for one UDP cycle
            time.sleep(2.5)
        # Close UDP socket
        #print("Close Socket")
        #comsocket.close()

    @property
    def hardware_name(self):
        return "FileParse"

# To test this driver, run it directly as follows:
#   PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/fileparse.py
# if __name__ == "__main__":
#     import weeutil.weeutil
#     import weeutil.logger
#     import weewx
#     weewx.debug = 1
#     weeutil.logger.setup('fileparse', {})
#
#     driver = FileParseDriver()
#     for packet in driver.genLoopPackets():
#         print(weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet)