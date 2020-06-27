#!/usr/bin/python
#
# Copyright 2020 Bastiaan Meelberg
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
#
"""

Weewx Driver for The WeatherLink Live (WLL). It implements a HTTP interface for getting current weather data and can support continuous requests as often as every 10 seconds. Also it collects a real-time 2.5 sec broadcast for wind speed and rain over UDP port 22222.

See Davis weatherlink-live-local-api


"""
from __future__ import with_statement

from socket import *
import time

import requests
import json

from requests.exceptions import HTTPError

import weewx.drivers


## DEBUG ONLY
#import pprint

DRIVER_NAME = 'WeatherLinkLiveUDP'
DRIVER_VERSION = '0.2.1b'

MM2INCH = 1/25.4

DEFAULT_TCP_ADDR = '192.168.1.47'
DEFAULT_POLL_INTERVALL = 10

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
        syslog.syslog(level, 'WLL UDP: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)


def loader(config_dict, engine):
    return WeatherLinkLiveUDPDriver(**config_dict[DRIVER_NAME])

class WeatherLinkLiveUDPDriver(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from a WeatherLink Live


    """

    def __init__(self, **stn_dict):
        # Show Diver version
        loginf('WLL UDP driver version is %s' % DRIVER_VERSION)

        self.poll_interval = float(stn_dict.get('poll_interval', DEFAULT_POLL_INTERVALL))
        loginf('TCP polling interval is %s' % self.poll_interval)

        self.wll_ip = stn_dict.get('wll_ip',DEFAULT_TCP_ADDR)
        #print(self.wll_ip)
        if self.wll_ip is None:
            logerr("No Weatherlink Live URL provided")

        self.timeout = None
        self.StartTime = time.time()

        # Tells the WW to begin broadcasting UDP data and continue for 1 hour seconds
        self.Real_Time_URL = 'http://%s:80/v1/real_time?duration=3600' % self.wll_ip
        self.CurrentConditions_URL = 'http://%s:80/v1/current_conditions' % self.wll_ip

        self.txid_ISS  = stn_dict.get('ISS_id', 1)
        # self.txid_wind = stn_dict.get('wind_id', 1)         #not implemented yet

 #       self.last_rain_storm = None
 #       self.last_rain_storm_start_at = None

        self.LaunchTime = time.time()
        self.UPD_CountDown = 0

        self.rain_previous_period = None


    @property
    def hardware_name(self):
        return "WeatherLinkLiveUDP"


    def genLoopPackets(self):

        while True:
            try:
                response = requests.get(self.CurrentConditions_URL)
                # If the response was successful, no Exception will be raised
                response.raise_for_status()
            except HTTPError as http_err:
                errormsg = ('HTTP error occurred: {http_err}')  # Python 3.6
                loginf(errormsg)

            except Exception as err:
                errormsg = ('Other error occurred: {err}')  # Python 3.6
                loginf(errormsg)

            else:

                CurrentConditions = response.json()
                packet = self.DecodeDataWLL(CurrentConditions['data'])
                yield packet

            # Check if UDP is still on
            self.Check_UDP_Broascast()

            # Set timer to listen to UDP
            self.timeout = time.time() + self.poll_interval
            ## self.timeout = time.time() + 10




            # Listen for UDP Broadcast for the duration of the interval
            while time.time() < self.timeout:
                data, wherefrom = comsocket.recvfrom(2048)
                UDP_data = json.loads(data.decode("utf-8"))
                if UDP_data["conditions"] == None:
                    print(UDP_data["error"])
                else:
                    packet = self.DecodeDataWLL(UDP_data)
                    # Yield UDP
                    yield packet


    def DecodeDataWLL(self, data):
        timestamp = data['ts']
        packet = {'dateTime': timestamp, 'usUnits': weewx.US}

        for condition in data['conditions']:
            if condition["data_structure_type"] == 1 and condition['txid'] == 1:

                if "wind_speed_last" in condition:  # most recent valid wind speed **(mph)**
                    packet.update({'windSpeed': condition["wind_speed_last"]})

                if "wind_dir_last" in condition:  # most recent valid wind direction **(°degree)**
                    packet.update({'windDir': condition["wind_dir_last"]})

                if "wind_speed_hi_last_10_min" in condition:  # maximum wind speed over last 10 min **(mph)**
                    packet.update({'windGust': condition["wind_speed_hi_last_10_min"]})

                if "wind_dir_scalar_avg_last_10_min" in condition:  # gust wind direction over last 10 min **(°degree)**
                    packet.update({'windGustDir': condition["wind_dir_scalar_avg_last_10_min"]})

                if "temp" in condition:  # most recent valid temperature **(°F)**
                    packet.update({'outTemp': condition['temp']})

                if "hum" in condition:  # most recent valid temperature **(°F)**
                    packet.update({'outHumidity': condition['hum']})

                if "dew_point" in condition:  # **(°F)**
                    packet.update({'dewpoint': condition['dew_point']})

                if "heat_index" in condition:  # **(°F)**
                    packet.update({'heatindex': condition['heat_index']})

                if "wind_chill" in condition:  # **(°F)**
                    packet.update({'windchill': condition['wind_chill']})

                if "solar_rad" in condition:  #
                    packet.update({'radiation': condition['solar_rad']})

                if "uv_index" in condition:  #
                    packet.update({'UV': condition['uv_index']})
                if "trans_battery_flag" in condition:  #
                    packet.update({'txBatteryStatus': condition['trans_battery_flag']})

                if "rx_state" in condition:
                    packet.update({'signal1': condition['rx_state']})

                if "rain_size" in condition:  # rain collector type/size **(0: Reserved, 1: 0.01", 2: 0.2 mm, 3:  0.1 mm, 4: 0.001")**

                    rain_collector_type = condition["rain_size"]

                    if 1 <= rain_collector_type <= 4:

                        if rain_collector_type == 1:
                            bucketSize = 0.01

                        elif rain_collector_type == 2:
                            bucketSize = 0.2 * MM2INCH

                        elif rain_collector_type == 3:
                            bucketSize = 0.1

                        elif rain_collector_type == 4:
                            bucketSize = 0.001

                        ####if "rain_rate_last" in condition:  # most recent valid rain rate **(counts/hour)**

                        ##### RainRate_last = condition['rain_rate_last']
                            ####packet.update({'rainRate': float(condition["rain_rate_last"]) * bucketSize})

                        rainFall_Daily = condition['rainfall_daily']
                        rainRate = condition['rain_rate_last']

                        # Check current rain for the day and set it
                        if self.rain_previous_period == None:
                            self.rain_previous_period = rainFall_Daily
                            logdbg(f'Daily rain is set at: {round(self.rain_previous_period)} buckets [{round(self.rain_previous_period * bucketSize * 25.4 ,1)} mm / {round(self.rain_previous_period * bucketSize ,2)} in]')

                        # At midnight WLL resets rainfall_daily, so if it Less than the previous_period also reset
                        #
                        # Note: This is not perfect yet! e.g. it is raining at midnight 1 bucket, and the previous_period is
                        # also 1 bucket. Using the 2.5 seconds UDP this is very unlikly, but with a non UDP polinterval of 300
                        # it is possible.
                        #
                        if rainFall_Daily < self.rain_previous_period:
                            self.rain_previous_period = 0
                            logdbg('Midnight rain rest')

                        if rainFall_Daily is not None:

                            if self.rain_previous_period is not None:
                                rain_this_period = (rainFall_Daily - self.rain_previous_period)
                                self.rain_previous_period = rainFall_Daily
                                if rain_this_period > 0:
                                    logdbg(f'Rain this period: +{rain_this_period} buckets.[{round(rain_this_period * bucketSize * 25.4 ,1)} mm / {round(rain_this_period * bucketSize ,2)} in]')
                                    logdbg(f'Set Previous period rain to: {self.rain_previous_period} buckets.[{round(self.rain_previous_period * bucketSize * 25.4 ,1)} mm / {round(self.rain_previous_period * bucketSize ,2)} in]')


                        packet.update({'rain':  rain_this_period * bucketSize })
                        packet.update({'rainRate': rainRate * bucketSize })

            elif condition['data_structure_type'] == 3:

                if "bar_sea_level" in condition:  # most recent bar sensor reading with elevation adjustment **(inches)**
                    packet.update({'barometer': condition["bar_sea_level"]})

                if "bar_absolute" in condition:  # raw bar sensor reading **(inches)**
                    packet.update({'pressure': condition["bar_absolute"]})

            # 4 = LSS Temp/Hum Current Conditions record
            elif condition['data_structure_type'] == 4:

                if "temp_in" in condition:  # most recent valid inside temp **(°F)**
                    packet.update({'inTemp': condition["temp_in"]})

                if "hum_in" in condition:  # most recent valid inside humidity **(%RH)**
                    packet.update({'inHumidity': condition["hum_in"]})

                if "dew_point_in" in condition:  # **(°F)**
                    packet.update({'inDewpoint': condition["dew_point_in"]})
        return (packet)

    def Check_UDP_Broascast(self):
        if self.UPD_CountDown < time.time():
            try:
                response = requests.get(self.Real_Time_URL)
                # If the response was successful, no Exception will be raised
                response.raise_for_status()
            except HTTPError as http_err:
                errormsg = (f'HTTP error occurred: {http_err}')  # Python 3.6
                loginf(errormsg)

            except Exception as err:
                errormsg = (f'Other error occurred: {err}')  # Python 3.6
                loginf(errormsg)

            else:
                Req_data = response.json()
                print(Req_data)
                self.UPD_CountDown = time.time() + Req_data['data']['duration']
                loginf(f'UDP broadcast ends: {weeutil.weeutil.timestamp_to_string(self.UPD_CountDown)}')





# To test this driver, run it directly as follows:
#   PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/Wwatherlinkliveudp.py
if __name__ == "__main__":
    import weeutil.weeutil
    import weeutil.logger
    import weewx
    weewx.debug = 1
    weeutil.logger.setup('WeatherLinkLiveUDP', {})
    print(weeutil.weeutil.timestamp_to_string(time.time()))

    driver = WeatherLinkLiveUDPDriver()
    for packet in driver.genLoopPackets():
        print(weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet)
