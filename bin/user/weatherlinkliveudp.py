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

import socket
from socket import AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
import time

import requests
import json

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import weewx.drivers
import datetime
import weeutil.weeutil

DRIVER_NAME = 'WeatherLinkLiveUDP'
DRIVER_VERSION = '0.2.7'

MM2INCH = 1 / 25.4

# Open UDP Socket
comsocket = socket.socket(AF_INET, SOCK_DGRAM)
comsocket.bind(('', 22222))
comsocket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
comsocket.settimeout(5)

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


class RainBarrel:
    def __init__(self):
        self.bucketsize = 0.0
        self.rain_previous_period = 0
        self.previous_day = None

        self.rain = 0

    # rain collector type/size **(0: Reserved, 1: 0.01", 2: 0.2 mm, 3:  0.1 mm, 4: 0.001")*
    def set_up_bucket_size(self, data):

        type = data['rain_size']
        if 1 <= type <= 4:

            if type == 1:
                self.bucketsize = 0.01
                logdbg(f'Bucketsize is set at 0.1 in')

            elif type == 2:
                self.bucketsize = 0.2 * MM2INCH
                logdbg(f'Bucketsize is set at 0.2 mm')

            elif type == 3:
                self.bucketsize = 0.1 * MM2INCH
                logdbg(f'Bucketsize is set at 0.1 mm')

            elif type == 4:
                self.bucketsize = 0.001
                logdbg(f'Bucketsize is set at 0.001 in')

    def set_rain_previous_period(self, data):
        self.rain_previous_period = data
        logdbg(
            f'({weeutil.weeutil.timestamp_to_string(time.time())}) Previous rain is set at: {(self.rain_previous_period)} buckets [{round(self.rain_previous_period * self.bucketsize * 25.4, 1)} mm / {round(self.rain_previous_period * self.bucketsize, 2)} in]')

    def empty_rain_barrel(self):
        self.rain = 0

    def set_rain_previous_date(self, data):
        # Send to DEBUG
        self.previous_date_stamp = data
        logdbg(
            f'({weeutil.weeutil.timestamp_to_string(time.time())}) Rain daily reset midnight: {str(self.previous_date_stamp.day)}')


class WWLstation():
    def __init__(self):
        self.poll_interval = 10
        self.txid_iss = None
        self.extra1 = None

        self.davis_date_stamp = None

        self.real_rime_url = None
        self.current_conditions_url = None

        self.davis_packet = dict()
        self.davis_packet['rain'] = 0
        self.udp_countdown = 0

    rainbarrel = RainBarrel()

    def set_poll_interval(self, data):
        self.poll_interval = data
        if self.poll_interval < 10:
            logerr('Unable to set Poll Interval (minimal 10 s.)')
        loginf('HTTP polling interval is %s' % self.poll_interval)

    def set_txid(self, data):
        if data:
            self.txid_iss = int(data)
            loginf(f'tx id of ISS is {self.txid_iss}')

    def set_extra1(self, data):
        if data:
            self.extra1 = int(data)
            loginf(f'Extra sensor is using id: {self.extra1}')

    def decode_data_wll(self, data):

        iss_data = None
        leaf_soil_data = None
        lss_bar_data = None
        lss_temp_hum_data = None
        iss_udp_data = None
        extra_data1 = None

        timestamp = data['ts']
        self.davis_date_stamp = datetime.datetime.fromtimestamp(timestamp)

        packet = dict()

        packet['dateTime'] = timestamp
        packet['usUnits'] = weewx.US

        for condition in data['conditions']:
            # 1 = ISS Current Conditions record
            # 2 = Leaf/Soil Moisture Current Conditions record
            # 3 = LSS BAR Current Conditions record
            # 4 = LSS Temp/Hum Current Conditions record

            if condition.get('txid') == self.txid_iss and condition.get('data_structure_type') == 1:
                iss_data = condition
            if condition.get('data_structure_type') == 2:
                leaf_soil_data = condition

            if condition.get('data_structure_type') == 3:
                lss_bar_data = condition

            if condition.get('data_structure_type') == 4:
                lss_temp_hum_data = condition

            if condition.get('txid') == self.txid_iss and condition.get('data_structure_type') == 1 and not condition.get('temp'):
                iss_udp_data = condition

            # If extra sensor are requested, try to find them
            if self.extra1 and condition.get('txid') == self.extra1:
                extra_data1 = condition

        # Get UDP data
        if iss_udp_data:
            # most recent valid wind speed **(mph)**
            packet['windSpeed'] = iss_udp_data['wind_speed_last']

            # most recent valid wind direction **(°degree)**
            packet['windDir'] = iss_udp_data['wind_dir_last']

            # maximum wind speed over last 10 min **(mph)**
            packet['windGust'] = iss_udp_data['wind_speed_hi_last_10_min']

            # gust wind direction over last 10 min **(°degree)**
            packet['windGustDir'] = iss_udp_data["wind_dir_at_hi_speed_last_10_min"]

            # Rain
            self.rainbarrel.rain = iss_udp_data['rainfall_daily']
            packet['rainRate'] = iss_udp_data['rain_rate_last'] * self.rainbarrel.bucketsize

            self.calculate_rain()

            packet['rain'] = self.davis_packet['rain']
            if packet['rain'] > 0:
                logdbg(f"UDP rain detect: {self.davis_packet['rain'] / self.rainbarrel.bucketsize} buckets -> {self.davis_packet['rain']} in")

        # Get HTTP data
        if iss_data and iss_data.get('temp'):
            # most recent valid wind speed **(mph)**
            packet['windSpeed'] = iss_data['wind_speed_last']

            # most recent valid wind direction **(°degree)**
            packet['windDir'] = iss_data['wind_dir_last']

            # maximum wind speed over last 10 min **(mph)**
            packet['windGust'] = iss_data['wind_speed_hi_last_10_min']

            # gust wind direction over last 10 min **(°degree)**
            packet['windGustDir'] = iss_data["wind_dir_at_hi_speed_last_10_min"]

            # most recent valid temperature **(°F)**
            packet['outTemp'] = iss_data['temp']

            # most recent valid humidity **(%RH)**
            packet['outHumidity'] = iss_data['hum']

            # **(°F)**
            packet['dewpoint'] = iss_data['dew_point']

            # **(°F)**
            packet['heatindex'] = iss_data['heat_index']

            # **(°F)**
            packet['windchill'] = iss_data['wind_chill']

            # most recent solar radiation **(W/m²)**
            packet['radiation'] = iss_data['solar_rad']

            # most recent UV index **(Index)**
            packet['UV'] = iss_data['uv_index']

            # transmitter battery status flag **(no unit)**
            packet['txBatteryStatus'] = iss_data['trans_battery_flag']

            # configured radio receiver state **(no unit)**
            packet['signal1'] = iss_data['rx_state']

            self.rainbarrel.rain = iss_data['rainfall_daily']
            packet['rainRate'] = iss_data['rain_rate_last'] * self.rainbarrel.bucketsize

            self.calculate_rain()

            packet['rain'] = self.davis_packet['rain']
            if packet['rain'] > 0:
                logdbg(f"HTTP rain detect: {packet['rain'] / self.rainbarrel.bucketsize} buckets -> {packet['rain']} in")

        if lss_bar_data:
            # most recent bar sensor reading with elevation adjustment **(inches)**
            packet['barometer'] = lss_bar_data['bar_sea_level']
            packet['pressure'] = lss_bar_data['bar_absolute']

        if lss_temp_hum_data:
            # most recent valid inside temp **(°F)**
            packet['inTemp'] = lss_temp_hum_data['temp_in']
            # most recent valid inside humidity **(%RH)**
            packet['inHumidity'] = lss_temp_hum_data['hum_in']
            # **(°F)**
            packet['inDewpoint'] = lss_temp_hum_data['dew_point_in']

        if extra_data1:
            if extra_data1.get('temp'):
                packet['extraTemp1'] = extra_data1['temp']
            if extra_data1.get('hum'):
                packet['extraHumid1'] = extra_data1['hum']

        return (packet)

    def calculate_rain(self):

        if self.davis_date_stamp.day != self.rainbarrel.previous_date_stamp.day:
            self.rainbarrel.previous_date_stamp = self.davis_date_stamp
            # Reset Previous rain at Midnight
            self.rainbarrel.set_rain_previous_period(0)
            logdbg(f'({weeutil.weeutil.timestamp_to_string(time.time())}) Daily rain reset - next reset midnight {str(self.rainbarrel.previous_date_stamp.day)}')

        if self.rainbarrel.rain < self.rainbarrel.rain_previous_period:
            logdbg('({weeutil.weeutil.timestamp_to_string(time.time())}) Negative Rain')
        rain_now = self.rainbarrel.rain - self.rainbarrel.rain_previous_period
        if rain_now > 0:
            logdbg(f'({weeutil.weeutil.timestamp_to_string(time.time())}) rainbarrel.rain: {self.rainbarrel.rain} - rain_previous_period: {self.rainbarrel.rain_previous_period}.')
            self.rainbarrel.rain_previous_period = self.rainbarrel.rain
            # Empty Barrel
            self.rainbarrel.empty_rain_barrel()

            logdbg(f'({weeutil.weeutil.timestamp_to_string(time.time())}) Rain this period: +{rain_now} buckets.[{round(rain_now * self.rainbarrel.bucketsize * 25.4, 1)} mm / {round(rain_now * self.rainbarrel.bucketsize, 2)} in]')
            logdbg(f'Set Previous period rain to: {self.rainbarrel.rain_previous_period} buckets.[{round(self.rainbarrel.rain_previous_period * self.rainbarrel.bucketsize * 25.4, 1)} mm / {round(self.rainbarrel.rain_previous_period * self.rainbarrel.bucketsize, 2)} in]')

        self.davis_packet['rain'] = rain_now * self.rainbarrel.bucketsize

    def check_udp_broascast(self):
        if (self.udp_countdown - 360) < time.time():
            response = make_request_using_socket(self.real_rime_url)
            if response is None:
                logerr('Unable to connect to Weather Link Live')
            elif response.get('data'):
                Req_data = response
                self.udp_countdown = time.time() + Req_data['data']['duration']
                loginf(f'UDP check at: {weeutil.weeutil.timestamp_to_string(self.udp_countdown)}')


class WeatherLinkLiveUDPDriver(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from a WeatherLink Live
    """

    def __init__(self, **stn_dict):
        # Show Diver version
        loginf('WLL UDP driver version is %s' % DRIVER_VERSION)

        self.station = WWLstation()

        self.station.set_poll_interval(float(stn_dict.get('poll_interval', 10)))

        self.wll_ip = stn_dict.get('wll_ip', '192.168.1.47')

        if self.wll_ip is None:
            logerr("No Weatherlink Live IP provided")

        self.station.set_extra1(stn_dict.get('extra_id'))

        # Tells the WW to begin broadcasting UDP data and continue for 1 hour seconds
        self.station.real_rime_url = f'http://{self.wll_ip}:80/v1/real_time?duration=3600'
        self.station.current_conditions_url = f'http://{self.wll_ip}:80/v1/current_conditions'

        # Make First Contact with WLL
        response = make_request_using_socket(self.station.current_conditions_url)

        if response is None:
            logerr('Unable to connect to Weather Link Live')
        elif response.get('data'):

            data = response['data']

            main_condition = data['conditions'][0]
            self.station.set_txid(data['conditions'][0]['txid'])

            # Set Bucket Size
            self.station.rainbarrel.set_up_bucket_size(main_condition)

            # Check current rain for the day and set it
            self.station.rainbarrel.set_rain_previous_period(main_condition['rainfall_daily'])

            # Set date for previous rain
            self.station.rainbarrel.set_rain_previous_date(datetime.datetime.fromtimestamp(data['ts']))

    @property
    def hardware_name(self):
        return "WeatherLinkLiveUDP"

    def genLoopPackets(self):

        # Start Loop
        while True:
            # Get Current Conditions
            current_conditions = make_request_using_socket(self.station.current_conditions_url)
            if current_conditions is None:
                logerr('No current conditions from wll. Check ip address.')
            elif current_conditions.get('data'):
                packet = self.station.decode_data_wll(current_conditions['data'])
                yield packet

            # Check if UDP is still on
            self.station.check_udp_broascast()

            # Set timer to listen to UDP
            self.timeout = time.time() + self.station.poll_interval

            # Listen for UDP Broadcast for the duration of the poll interval
            while time.time() < self.timeout:
                try:
                    data, wherefrom = comsocket.recvfrom(2048)
                    UDP_data = json.loads(data.decode("utf-8"))
                    if UDP_data["conditions"] is None:
                        logdbg(UDP_data["error"])
                    else:
                        packet =self.station.decode_data_wll(UDP_data)
                        # Yield UDP
                        yield packet
                except socket.timeout:
                    logerr('UDP Socket Time Out')
                    # Reset Countdown to Switch UDP back on.
                    self.station.udp_countdown = 0
                    self.station.check_udp_broascast()


def make_request_using_socket(url):
    try:
        retry_strategy = Retry(total=3, backoff_factor=1)

        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("http://", adapter)

        resp = http.get(url, timeout=3)

        json_data = json.loads(resp.text)
        if json_data["data"] is None:
            logerr(json_data["error"])
        else:
            return (json_data)
    except requests.Timeout as err:
        logerr({"message": err})
    except requests.RequestException as err:
        # Max retries exceeded
        logerr(f'RequestExeption: {err}')


# To test this driver, run it directly as follows:
#   PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/weatherlinkliveudp.py
if __name__ == "__main__":
    import optparse

    import weeutil.logger
    import weewx

    weewx.debug = 1
    weeutil.logger.setup('WeatherLinkLiveUDP', {})
    usage = """Usage:%prog --wll_ip= [options] [--help] [--version]"""

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--version', dest='version', action='store_true',
                      help='Display driver version')
    #
    parser.add_option('--wll_ip', dest='wll_ip', metavar='wll_ip',
                      help='ip address from Weather Link Live')

    (options, args) = parser.parse_args()

    if options.version:
        print("Weatherlink Liver version %s" % DRIVER_VERSION)
        exit(0)

    driver = WeatherLinkLiveUDPDriver()
    for packet in driver.genLoopPackets():
        print(weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet)
