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
# Beta AirLink

"""

Weewx Driver for The WeatherLink Live (WLL).
It implements a HTTP interface for getting current weather data and can support continuous requests as often as every 10 seconds.
Also it collects a real-time 2.5 sec broadcast for wind speed and rain over UDP port 22222.

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
# import sys

DRIVER_NAME = 'WeatherLinkLiveUDP'
DRIVER_VERSION = '0.3.0'

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
                logdbg('Bucketsize is set at 0.01 in')

            elif type == 2:
                self.bucketsize = 0.2 * MM2INCH
                logdbg('Bucketsize is set at 0.2 mm')

            elif type == 3:
                self.bucketsize = 0.1 * MM2INCH
                logdbg('Bucketsize is set at 0.1 mm')

            elif type == 4:
                self.bucketsize = 0.001
                logdbg('Bucketsize is set at 0.001 in')

    def set_rain_previous_period(self, data):
        self.rain_previous_period = data
        logdbg('({}) Previous rain is set at: {} buckets [{} mm / {} in]'
               .format(weeutil.weeutil.timestamp_to_string(time.time()),
                       (self.rain_previous_period),
                       round(self.rain_previous_period * self.bucketsize * 25.4, 1),
                       round(self.rain_previous_period * self.bucketsize, 2)))

    def empty_rain_barrel(self):
        self.rain = 0

    def set_rain_previous_date(self, data):
        # Setting the current date to Midnight for rain reset
        data += datetime.timedelta(days=1)
        data = data.replace(hour=0, minute=0, second=0, microsecond=0)
        self.previous_date_stamp = data
        logdbg('({}) Rain daily reset: {}'
               .format(weeutil.weeutil.timestamp_to_string(time.time()),
                       str(self.previous_date_stamp)))


class WllStation:
    def __init__(self):
        self.poll_interval = 10
        self.txid_iss = None
        self.extra1 = None

        self.davis_date_stamp = None
        self.system_date_stamp = None

        self.real_rime_url = None
        self.current_conditions_url = None
        self.current_air_conditions_url = None

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
            loginf('tx id of ISS is {}'.format(self.txid_iss))

    def set_extra1(self, data):
        if data:
            self.extra1 = int(data)
            loginf('Extra sensor is using id: {}'.format(self.extra1))

    def decode_data_wll(self, data):

        iss_data = None
        leaf_soil_data = None
        lss_bar_data = None
        lss_temp_hum_data = None
        iss_udp_data = None
        extra_data1 = None
        # air_data = None

        # self.current_davis_data = data

        timestamp = data['ts']
        self.davis_date_stamp = datetime.datetime.fromtimestamp(timestamp)
        self.system_date_stamp = datetime.datetime.now()

        packet = dict()

        packet['dateTime'] = timestamp
        packet['usUnits'] = weewx.US

        for condition in data['conditions']:
            # 1 = ISS Current Conditions record
            # 2 = Leaf/Soil Moisture Current Conditions record
            # 3 = LSS BAR Current Conditions record
            # 4 = LSS Temp/Hum Current Conditions record
            # 6 = AirLink data

            if condition.get('txid') == self.txid_iss and condition.get('data_structure_type') == 1:
                iss_data = condition

            if condition.get('data_structure_type') == 2:
                leaf_soil_data = condition

            if condition.get('data_structure_type') == 3:
                lss_bar_data = condition

            if condition.get('data_structure_type') == 4:
                lss_temp_hum_data = condition

            if condition.get('data_structure_type') == 6:
                air_data = condition

            if condition.get('txid') == self.txid_iss and condition.get(
                    'data_structure_type') == 1 and not condition.get('temp'):
                iss_udp_data = condition

            # If extra sensor are requested, try to find them
            if self.extra1 and condition.get('txid') == self.extra1:
                extra_data1 = condition

        # Get UDP data
        if iss_udp_data:

            # most recent valid wind speed **(mph)**
            packet['windSpeed'] = iss_udp_data['wind_speed_last']

            # most recent valid wind direction **(degree)**
            packet['windDir'] = iss_udp_data['wind_dir_last']

            # Rain
            ## Fix: Check for NoneType
            self.rainbarrel.rain = iss_udp_data['rainfall_daily']

            if iss_udp_data['rain_rate_last'] is None:
                logdbg("Error: UDP->rain_rate_last not defined")
            else:
                packet['rainRate'] = iss_udp_data['rain_rate_last'] * self.rainbarrel.bucketsize

            self.calculate_rain()

            packet['rain'] = self.davis_packet['rain']

            if packet['rain'] > 0:
                logdbg('UDP rain detect: {} buckets -> {} in'
                       .format(self.davis_packet['rain'] / self.rainbarrel.bucketsize,
                               self.davis_packet['rain']))

        # Get HTTP data
        if iss_data and iss_data.get('temp'):
            # most recent valid wind speed **(mph)**
            packet['windSpeed'] = iss_data['wind_speed_last']

            # most recent valid wind direction **(degree)**
            packet['windDir'] = iss_data['wind_dir_last']

            # maximum wind speed over last 2 min **(mph)**
            packet['windGust'] = iss_data['wind_speed_hi_last_2_min']

            # gust wind direction over last 2 min **(degree)**
            packet['windGustDir'] = iss_data["wind_dir_at_hi_speed_last_2_min"]

            # wind speed and direction average for the last 10 minutes
            # (not recorded in archive but used elsewhere)
            packet['windSpeed10'] = iss_data["wind_speed_avg_last_10_min"]
            packet['windDir10'] = iss_data["wind_dir_scalar_avg_last_10_min"]
            
            # most recent valid temperature **(F)**
            packet['outTemp'] = iss_data['temp']

            # most recent valid humidity **(%RH)**
            packet['outHumidity'] = iss_data['hum']

            # **(F)**
            packet['dewpoint'] = iss_data['dew_point']

            # **(F)**
            packet['heatindex'] = iss_data['heat_index']

            # **(F)**
            packet['windchill'] = iss_data['wind_chill']
            
            # **(F)**
            packet['THSW'] = iss_data['thsw_index']
            
            packet['outWetbulb'] = iss_data['wet_bulb']

            # most recent solar radiation **(W/m)**
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
                logdbg('HTTP rain detect: {} buckets -> {} in'
                       .format(packet['rain'] / self.rainbarrel.bucketsize,
                               packet['rain']))

        if lss_bar_data:
            # most recent bar sensor reading with elevation adjustment **(inches)**
            packet['altimeter'] = lss_bar_data['bar_sea_level']
            packet['pressure'] = lss_bar_data['bar_absolute']

        if lss_temp_hum_data:
            # most recent valid inside temp **(F)**
            packet['inTemp'] = lss_temp_hum_data['temp_in']
            # most recent valid inside humidity **(%RH)**
            packet['inHumidity'] = lss_temp_hum_data['hum_in']
            # **(F)**
            packet['inDewpoint'] = lss_temp_hum_data['dew_point_in']

        if extra_data1:
            if extra_data1.get('temp'):
                packet['extraTemp1'] = extra_data1['temp']
            if extra_data1.get('hum'):
                packet['extraHumid1'] = extra_data1['hum']

        # if air_data:
        #     # pm10_0
        #     # double
        #     # pm1_0
        #     # double
        #     # pm2_5
        #     packet['pm1_0'] = air_data['pm_1']
        #     packet['pm2_5'] = air_data['pm_2p5']
        #     packet['pm10_0'] = air_data['pm_10']

        return packet

    def decode_air_data_wll(self, data):

        air_packet = dict()

        for condition in data['conditions']:
            # 6 = AirLink data

            if condition.get('data_structure_type') == 6:

                air_packet['pm1_0'] = condition['pm_1_last']
                air_packet['pm2_5'] = condition['pm_2p5_last']
                air_packet['pm10_0'] = condition['pm_10_last']

        return air_packet

    def calculate_rain(self):
        if self.davis_date_stamp.timestamp() > self.rainbarrel.previous_date_stamp.timestamp():

            # Reset Previous rain at Midnight
            logdbg('Previous: {}'.format(self.rainbarrel.previous_date_stamp))
            logdbg('Davis:   {}'.format(self.davis_date_stamp))
            logdbg('System:   {}'.format(self.system_date_stamp))
            logdbg('daily rain Davis:     {}'.format(self.rainbarrel.rain))
            logdbg('prev. before reset:   {}'.format(self.rainbarrel.rain_previous_period))

            self.rainbarrel.set_rain_previous_date(self.davis_date_stamp)
            self.rainbarrel.set_rain_previous_period(0)

            logdbg('prev after reset:     {}'.format(self.rainbarrel.rain_previous_period))
            logdbg('({}) Daily rain reset - next reset midnight {}'
                   .format(weeutil.weeutil.timestamp_to_string(time.time()), str(self.rainbarrel.previous_date_stamp)))

        if self.rainbarrel.rain < self.rainbarrel.rain_previous_period:
            logdbg('({}) Negative Rain'.format(weeutil.weeutil.timestamp_to_string(time.time())))

        rain_now = self.rainbarrel.rain - self.rainbarrel.rain_previous_period
        if rain_now > 0:
            logdbg('({}) rainbarrel.rain: {} - rain_previous_period: {}.'
                   .format(weeutil.weeutil.timestamp_to_string(time.time()),
                           self.rainbarrel.rain,
                           self.rainbarrel.rain_previous_period))

            self.rainbarrel.rain_previous_period = self.rainbarrel.rain
            # Empty Barrel
            self.rainbarrel.empty_rain_barrel()

            logdbg('({}) Rain this period: +{} buckets.[{} mm / {} in]'
                   .format(weeutil.weeutil.timestamp_to_string(time.time()),
                           rain_now,
                           round(rain_now * self.rainbarrel.bucketsize * 25.4, 1),
                           round(rain_now * self.rainbarrel.bucketsize, 2)))
            logdbg('Set Previous period rain to: {} buckets.[{} mm / {} in]'
                   .format(self.rainbarrel.rain_previous_period,
                           round(self.rainbarrel.rain_previous_period * self.rainbarrel.bucketsize * 25.4, 1),
                           round(self.rainbarrel.rain_previous_period * self.rainbarrel.bucketsize, 2)))

        self.davis_packet['rain'] = rain_now * self.rainbarrel.bucketsize

    def check_udp_broascast(self):
        if (self.udp_countdown - 360) < time.time():
            response = make_request_using_socket(self.real_rime_url)
            if response is None:
                logerr('Unable to connect to Weather Link Live')
            elif response.get('data'):
                Req_data = response
                self.udp_countdown = time.time() + Req_data['data']['duration']
                logdbg('UDP check at: {}'.format(weeutil.weeutil.timestamp_to_string(self.udp_countdown)))


class WeatherLinkLiveUDPDriver(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from a WeatherLink Live
    """

    def __init__(self, **stn_dict):
        # Show Diver version
        loginf('WLL UDP driver version is %s' % DRIVER_VERSION)

        self.station = WllStation()

        self.station.set_poll_interval(float(stn_dict.get('poll_interval', 10)))

        self.wll_ip = stn_dict.get('wll_ip', '192.168.1.47')

        self.wll_air_ip = stn_dict.get('wll_air_ip', '192.168.1.199')

        if self.wll_ip is None:
            logerr("No Weatherlink Live IP provided")

        self.station.set_extra1(stn_dict.get('extra_id'))

        # Tells the WW to begin broadcasting UDP data and continue for 1 hour seconds
        self.station.real_rime_url = 'http://{}/v1/real_time?duration=3600'.format(self.wll_ip)

        self.station.current_conditions_url = 'http://{}/v1/current_conditions'.format(self.wll_ip)

        if self.wll_air_ip is not None:
            self.station.current_air_conditions_url = 'http://{}/v1/current_conditions'.format(self.wll_air_ip)
            # print(self.station.current_air_conditions_url)

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

    def test_midnight(self):
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        start = '00:00:00'
        end = '00:00:05'
        if start < current_time < end:
            logdbg('Midnight nap')
            logdbg(current_time)
            return True
        else:
            return False

    def genLoopPackets(self):

        # Start Loop
        while True:
            # Sleep for 5 seconds at midnight
            if self.test_midnight():
                logdbg("Midnight, no HTTP packet.")
            else:
                # Get Current Conditions
                current_conditions = make_request_using_socket(self.station.current_conditions_url)
                if current_conditions is None:
                    logerr('No current conditions from wll. Check ip address.')
                elif current_conditions.get('data'):
                    packet = self.station.decode_data_wll(current_conditions['data'])
                    #yield packet

                # Get Air Conditions
                if self.station.current_air_conditions_url is not None:
                    current_air_conditions = make_request_using_socket(self.station.current_air_conditions_url)
                    if current_air_conditions is None:
                        logerr('No current air conditions from wll. Check ip address.')
                    elif current_air_conditions.get('data'):
                        packet.update(self.station.decode_air_data_wll(current_air_conditions['data']))

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
                        if self.test_midnight():
                            logdbg("Midnight, no UDP packet.")
                        else:
                            packet = self.station.decode_data_wll(UDP_data)
                            # Yield UDP
                            yield packet
                # Catch json decoder faults
                except json.JSONDecodeError:
                    logging.info(
                        "Message was ignored because it was not valid JSON.",
                    )

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
            return json_data
    except requests.Timeout as err:
        logerr({"message": err})
    except requests.RequestException as err:
        # Max retries exceeded
        logerr('Request Exception: {}'.format(err))


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
