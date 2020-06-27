import time
import socket
import os
import json
from multiprocessing import Process

import pprint

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry



current_conditions_url = 'http://192.168.1.47:80/v1/current_conditions'



def make_request_using_socket(url):


    try:
        retry_stratagey = Retry( total=3, backoff_factor=1)

        adapter = HTTPAdapter(max_retries=retry_stratagey)
        http = requests.Session()
        http.mount("http://", adapter)

        resp = http.get(url, timeout=3)
        print(resp)
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


def main():
    global current_conditions_url
    while 1:
        data = make_request_using_socket(current_conditions_url)
        print(data)




if __name__ == "__main__":
    main()