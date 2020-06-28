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

# todo: Implementation of multiple transmitters.
#
"""

Weewx Driver for The WeatherLink Live (WLL). It implements a HTTP interface for getting current weather data and can support continuous requests as often as every 10 seconds. Also it collects a real-time 2.5 sec broadcast for wind speed and rain over UDP port 22222.

See Davis weatherlink-live-local-api


"""


#### TO DO FIRST TCP SHOULD BE CORRECT AND GIVE TIME

from __future__ import with_statement

from socket import *
import time

import requests

import json

##from requests.exceptions import HTTPError
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import weewx.drivers
import datetime


DRIVER_NAME = 'WeatherLinkLiveUDP'
DRIVER_VERSION = '0.2.3b'

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
        loginf('HTTP polling interval is %s' % self.poll_interval)
        if self.poll_interval <10:
            logerr('Unable to set Poll Interval (min. 10 s.)')

        self.wll_ip = stn_dict.get('wll_ip',DEFAULT_TCP_ADDR)
        if self.wll_ip is None:
            logerr("No Weatherlink Live IP provided")

        self.lsid_iss = stn_dict.get('self.lsid_iss')


        # Tells the WW to begin broadcasting UDP data and continue for 1 hour seconds
        self.Real_Time_URL = f'http://{self.wll_ip}:80/v1/real_time?duration=3600'
        self.current_conditions_url = f'http://{self.wll_ip}:80/v1/current_conditions'

        # Make First Contact with WLL
        response = make_request_using_socket(self.current_conditions_url)
        data = response['data']

        if response == None:
            print('error')
        elif data['conditions'][0]['lsid'] and self.lsid_iss is None:
            self.lsid_iss = data['conditions'][0]['lsid']
            loginf(f'ISS is using id: {self.lsid_iss}')

        for condition in data['conditions']:

            if condition['lsid'] == 242741 and condition['data_structure_type'] == 1:

                # Check current rain for the day and set it
                self.rain_previous_period = condition["rainfall_daily"]

                # Set Bucket Size
                # rain collector type/size **(0: Reserved, 1: 0.01", 2: 0.2 mm, 3:  0.1 mm, 4: 0.001")*
                rain_collector_type = condition["rain_size"]

                if 1 <= rain_collector_type <= 4:

                    if rain_collector_type == 1:
                        self.bucketSize = 0.01
                        loginf(f'Bucketsize = 0.1 in')

                    elif rain_collector_type == 2:
                        self.bucketSize = 0.2 * MM2INCH
                        loginf(f'Bucketsize = 0.2 mm')

                    elif rain_collector_type == 3:
                        self.bucketSize = 0.1 * MM2INCH
                        loginf(f'Bucketsize = 0.1 mm')

                    elif rain_collector_type == 4:
                        self.bucketSize = 0.001
                        loginf(f'Bucketsize = 0.001 in')

                # Set current date.
                self.PreviousDatestamp = datetime.date.fromtimestamp(data['ts'])
                # Send to DEBUG
                logdbg(f'Rain daily reset midnight: {str(self.PreviousDatestamp)}')
                logdbg(f'Daily rain is set at: {(self.rain_previous_period)} buckets [{round(self.rain_previous_period * self.bucketSize * 25.4, 1)} mm / {round(self.rain_previous_period * self.bucketSize, 2)} in]')

        self.UPD_CountDown = 0


    @property
    def hardware_name(self):
        return "WeatherLinkLiveUDP"

    def genLoopPackets(self):

        # Start Loop
        while True:

            # Get Current Conditions
            CurrentConditions = make_request_using_socket(self.current_conditions_url)
            packet = self.DecodeDataWLL(CurrentConditions['data'])
            yield packet

            # Check if UDP is still on
            self.Check_UDP_Broascast()

            # Set timer to listen to UDP
            self.timeout = time.time() + self.poll_interval

            # Listen for UDP Broadcast for the duration of the interval
            while time.time() < self.timeout:
                data, wherefrom = comsocket.recvfrom(2048)
                UDP_data = json.loads(data.decode("utf-8"))
                if UDP_data["conditions"] == None:
                    logdbg(UDP_data["error"])
                else:
                    packet = self.DecodeDataWLL(UDP_data)
                    # Yield UDP
                    yield packet


    def DecodeDataWLL(self, data):

        timestamp = data['ts']

        packet = {}
        packet['dateTime'] =  timestamp
        packet['usUnits'] = weewx.US

        DavisDateStamp = datetime.date.fromtimestamp(timestamp)

        for condition in data['conditions']:
            if condition["lsid"] == self.lsid_iss:

                packet['windSpeed'] = condition["wind_speed_last"]


                # #if "wind_speed_last" in condition:  # most recent valid wind speed **(mph)**
                #     packet.update({'windSpeed': condition["wind_speed_last"]})
                #
                # #if "wind_dir_last" in condition:  # most recent valid wind direction **(°degree)**
                #     packet.update({'windDir': condition["wind_dir_last"]})
                packet['winDir'] = condition["wind_dir_last"]
                #
                # if "wind_speed_hi_last_10_min" in condition:  # maximum wind speed over last 10 min **(mph)**
                #     packet.update({'windGust': condition["wind_speed_hi_last_10_min"]})

                packet['windGust'] = condition["wind_speed_hi_last_10_min"]
                #
                # if "wind_dir_scalar_avg_last_10_min" in condition:  # gust wind direction over last 10 min **(°degree)**
                #     packet.update({'windGustDir': condition["wind_dir_scalar_avg_last_10_min"]})

                packet['windGustDir'] = condition["wind_dir_at_hi_speed_last_10_min"]

                if "temp" in condition:  # most recent valid temperature **(°F)**
                    packet['outTemp'] = condition['temp']
                #
                # if "hum" in condition:  # most recent valid temperature **(°F)**
                #     packet.update({'outHumidity': condition['hum']})

                if "hum" in condition:  # most recent valid temperature **(°F)**
                    packet['outHumidity'] = condition['hum']

                if "dew_point" in condition:  # **(°F)**
                #     packet.update({'dewpoint': condition['dew_point']})

                    packet['dewpoint'] = condition['dew_point']

                if "heat_index" in condition:  # **(°F)**
                #     packet.update({'heatindex': condition['heat_index']})

                    packet['heatindex'] = condition['heat_index']

                if "wind_chill" in condition:  # **(°F)**
                #     packet.update({'windchill': condition['wind_chill']})
                    packet['windchill'] = condition['wind_chill']
                #
                if "solar_rad" in condition:  #
                #     packet.update({'radiation': condition['solar_rad']})
                    packet['radiation'] = condition['solar_rad']

                if "uv_index" in condition:  #
                #     packet.update({'UV': condition['uv_index']})
                    packet['UV'] = condition['uv_index']
                # if "trans_battery_flag" in condition:  #
                #     packet.update({'txBatteryStatus': condition['trans_battery_flag']})
                #
                # if "rx_state" in condition:
                #     packet.update({'signal1': condition['rx_state']})

                rainFall_Daily = condition['rainfall_daily']
                rainRate = condition['rain_rate_last']

                rain_this_period = 0
                logdbg(f'Daily rain reset - next reset midnight {str(self.PreviousDatestamp)}')
                if DavisDateStamp > self.PreviousDatestamp:
                    self.rain_previous_period = 0
                    self.PreviousDatestamp = DavisDateStamp
                    ## print(f'Prev Date: {str(self.PreviousDatestamp)}')
                    logdbg(f'Daily rain reset - next reset midnight {str(self.PreviousDatestamp)}')

                if rainFall_Daily is not None:

                    if self.rain_previous_period is not None:
                        rain_this_period = (rainFall_Daily - self.rain_previous_period)

                        if rain_this_period > 0:
                            self.rain_previous_period = rainFall_Daily
                            logdbg(f'Rain this period: +{rain_this_period} buckets.[{round(rain_this_period * self.bucketSize * 25.4 ,1)} mm / {round(rain_this_period * self.bucketSize ,2)} in]')
                            logdbg(f'Set Previous period rain to: {self.rain_previous_period} buckets.[{round(self.rain_previous_period * self.bucketSize * 25.4 ,1)} mm / {round(self.rain_previous_period * self.bucketSize ,2)} in]')


                packet['rain'] = rain_this_period * self.bucketSize
                packet['rainRate'] = rainRate * self.bucketSize


            elif condition['data_structure_type'] == 3:

                if "bar_sea_level" in condition:  # most recent bar sensor reading with elevation adjustment **(inches)**
                    packet['barometer'] = condition['bar_sea_level']
                    #packet.update({'barometer': condition["bar_sea_level"]})

                if "bar_absolute" in condition:  # raw bar sensor reading **(inches)**
                    ##packet.update({'pressure': condition["bar_absolute"]})
                    packet['pressure'] = condition['bar_absolute']

            ## 4 = LSS Temp/Hum Current Conditions record
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
            response = make_request_using_socket(self.Real_Time_URL)
            Req_data = response
            ##print(Req_data)
            self.UPD_CountDown = time.time() + Req_data['data']['duration']
            loginf(f'UDP broadcast ends: {weeutil.weeutil.timestamp_to_string(self.UPD_CountDown)}')

def make_request_using_socket(url):

    try:
        retry_stratagey = Retry(total=3, backoff_factor=1)

        adapter = HTTPAdapter(max_retries=retry_stratagey)
        http = requests.Session()
        http.mount("http://", adapter)

        resp = http.get(url, timeout=3)
        #####print(resp)
        json_data = json.loads(resp.text)
        if json_data["data"] == None:
            print(json_data["error"])
        else:
            return (json_data)
    except requests.Timeout as err:
        print({"message": err})
    except requests.RequestException as err:
        # Max retries exceeded
        print(f'RequestExeption: {err}')



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
