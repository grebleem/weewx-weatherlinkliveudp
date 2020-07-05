import socket
from socket import AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
import struct
import time
import requests
import json

URL = 'http://10.95.35.7:80/v1/real_time?duration=20'


def main():
    global URL
    comsocket = socket.socket(AF_INET, SOCK_DGRAM)
    comsocket.bind(('', 22224))
    comsocket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    comsocket.settimeout(5)
    timeout = comsocket.gettimeout()
    print(f'Timeout is: {timeout}')
    ## resp = requests.get(URL)
    while 1:
        ##print("HTTP Response Code:", resp)
        try:
            data, wherefrom = comsocket.recvfrom(2048)
            json_data = json.loads(data.decode("utf-8"))
            if json_data["conditions"] == None:
                print(json_data["error"])
            else:
                print(json_data)

        except socket.timeout:
            print('Socket Time Out')


    comsocket.close()


if __name__ == "__main__":
    main()