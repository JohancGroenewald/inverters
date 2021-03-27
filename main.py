import time
from argparse import ArgumentParser

import serial
from serial.tools.list_ports import comports

ap = ArgumentParser(description='Query connected inverters',)
ap.add_argument('-l', '--list', action="store_true")
args = ap.parse_args()


def list_ports():
    ports = comports()
    for port in ports:
        attributes = [
            'description', 'device', 'hwid', 'interface', 'location', 'manufacturer', 'name', 'pid',
            'product', 'serial_number', 'vid', 'apply_usb_info', 'usb_description', 'usb_info'
        ]
        for attribute in attributes:
            if hasattr(port, attribute):
                value = getattr(port, attribute, None)
                if callable(value):
                    print(f'{attribute}: {value()}')
                else:
                    print(f'{attribute}: {value}')


def main():
    # connect to inverters
    # query inverters
    # write status to database
    # exit
    pass


if __name__ == '__main__':
    if args.list:
        list_ports()
    else:
        main()
