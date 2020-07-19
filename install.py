# Installer file for WeatherLink Live (WeatherLinkLiveUDP) driver for WeeWX
# Copyright 2020 Bastiaan Meelberg
# Distributed under the terms of the GNU Public License (GPLv3)

from setup import ExtensionInstaller

def loader():
    return weatherlinkliveudpInstaller()

class weatherlinkliveudpInstaller(ExtensionInstaller):
    def __init__(self):
        super(weatherlinkliveudpInstaller, self).__init__(
            version='0.2.6',
            name='WeatherLinkLiveUDP',
            description='Periodically poll weather data from a WeatherLink Live device',
            author="Bastiaan Meelberg",
            config={
                'weatherlinkliveudp': {
                    'wll_ip': '1.2.3.4',
                    'poll_interval': 30,
                    'driver': 'user.weatherlinkliveudp'
                }
            },
            files=[('bin/user', ['bin/user/weatherlinkliveudp.py'])]

        )
