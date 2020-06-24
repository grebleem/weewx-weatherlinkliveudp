# Installer file for WeatherLink Live (WeatherLinkLiveUDP) driver for WeeWX
# Copyright 2020 Bastiaan Meelberg
# Distributed under the terms of the GNU Public License (GPLv3)

from setup import ExtensionInstaller

def loader():
    return weatherlinkliveudp()

class weatherlinkliveudp(ExtensionInstaller):
    def __init__(self):
        super(weatherlinkliveudp, self).__init__(
            version="0.2",
            name='weatherlinkliveudp',
            description='Periodically poll weather data from a WeatherLink Live device',
            author="Bastiaan Meelberg",
            config={
                'WeatherLinkLiveUDP': {
                    'wll_ip': '1.2.3.4',
                    'poll_interval': 15,
                    'ISS_id': 1,
                    'driver': 'user.weatherlinkliveudp'
                }
            },
            files=[('bin/user', ['bin/user/weatherlinkliveudp.py'])])
