# WeatherLinkLiveUDP
Weewx Driver for The WeatherLink Live (WLL). It implements a HTTP interface for getting current weather data and can support continuous requests as often as every 10 seconds.
Also it collects a real-time 2.5 sec broadcast for wind speed and rain over UDP port 22222.

[See Davis weatherlink-live-local-api](https://weatherlink.github.io/weatherlink-live-local-api/)

To see a live demo of this plugin in vist [meteo-otterlo.nl](https://meteo-otterlo.nl), it features the [Belchertown weewx skin](https://github.com/poblabs/weewx-belchertown#belchertown-weewx-skin) from [Pat O'Brien](https://github.com/poblabs) with a MQTT broker to display the 2.5 seconds wind and rain data.

### Installation


1) Download the driver

```
wget -O weatherlinkliveudp.zip https://github.com/grebleem/WeatherLinkLiveUDP/archive/master.zip
```

2) Install the driver

```
sudo wee_extension --install weatherlinkliveudp.zip
``` 

4) Set the `station_type` to `WeatherLinkLiveUDP` and modify the `[WeatherLinkLiveUDP]` stanza in `weewx.conf`. If there are multilple stations connected to the WLL do a `http://<wll_ip>:80/v1/real_time` in an browers and and look in the JSON for the correct `lsid`. Use this to set the `lsid_ss`. See the [Davis](https://weatherlink.github.io/weatherlink-live-local-api/) documentation for more information :
```
[Station]

    # Set the type of station.
    station_type = WeatherLinkLiveUDP
```
```
The WLL can get dat from up to eight transmitters. If multiple transmitters e.g. extra ISS for wind, extra temp sensor, requires the lsid_iss
[WeatherLinkLiveUDP]
    wll_ip = 192.168.1.47
    poll_interval = 10              # number of seconds
    lsid_iss = 242741               # Optional
    driver = user.weatherlinkliveudp
```

4) Restart WeeWX

```
sudo systemctl stop weewx
sudo systemctl start weewx
```

Note: The driver requires the Python `requests` library. To install it:

```
sudo apt-get update 
sudo apt-get install python-requests
```
or us pip
```
pip install requests
```
