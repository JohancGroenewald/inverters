import time
from argparse import ArgumentParser

import serial
from serial.tools.list_ports import comports

import pprint

ap = ArgumentParser(description='Query connected inverters',)
ap.add_argument('-l', '--list', action="store_true")
args = ap.parse_args()


class Inverter:

    @staticmethod
    def list_ports():
        ports = comports()
        for port in ports:
            attributes = [
                'description', 'device', 'hwid', 'interface', 'location', 'manufacturer', 'name', 'pid',
                'product', 'serial_number', 'vid', 'apply_usb_info', 'usb_description', 'usb_info'
            ]
            pprint.pprint(port)


class EP2000(Inverter):
    pass


class Inverter__(serial.Serial):
    INDEX = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.index = Inverter.INDEX
        Inverter.INDEX += 1

    def command(self, out_buffer: bytes, result_length: int) -> list:
        count = super().write(out_buffer)
        in_buffer: bytes = super().read(result_length)
        return self.handle_com_returned(in_buffer)

    @staticmethod
    def handle_com_returned(in_buffer: bytes) -> list:
        """
            public string[] HandleComReturned(/*Parameter with token 0800003F*/string hexstrg)
            {
              StringBuilder stringBuilder = new StringBuilder(hexstrg);
              stringBuilder.Remove(0, 8);
              string str = stringBuilder.Remove(stringBuilder.Length - 6, 5).ToString().Trim();
              for (int startIndex = str.Length - 1; startIndex >= 0; --startIndex)
              {
                if (startIndex % 6 == 2)
                  str = str.Remove(startIndex, 1);
              }
              return str.Split(new char[1]{ ' ' });
            }
        """
        data = ' '.join([f'{byte:02X}' for byte in in_buffer])
        header = ' '.join([f'{byte:02X}' for byte in in_buffer[:8]])
        in_buffer = in_buffer[8:]
        start, stop = len(in_buffer) - 6, len(in_buffer) - 6 + 5
        discard = ' '.join([f'{byte:02X}' for byte in in_buffer[start: stop]])
        in_buffer = in_buffer[:start] + in_buffer[stop:]
        buffer = [
            data, header, discard, ' '.join([f'{byte:02X}' for byte in in_buffer])
        ]
        return buffer

    def __str__(self):
        return f'Inverter(index={self.index}, port={super().port})'


def main():
    # connect to inverters
    # query inverters
    # write status to database
    # exit
    inverters = [
        Inverter__(port='/dev/cuaU0', baudrate=9600, timeout=3.0, write_timeout=1.0),
        Inverter__(port='/dev/cuaU1', baudrate=9600, timeout=3.0, write_timeout=1.0),
        Inverter__(port='/dev/cuaU2', baudrate=9600, timeout=3.0, write_timeout=1.0),
    ]
    """
    reset         :    "0A 10 7D 00 00 01 02 00 01 B9 A7"
    SaveReadinData:    "0A 10 79 18 00 0A 14"
    string textSend1 = "0A 03 75 30 00 1B 1E B9";
    string textSend2 = "0A 03 79 18 00 0A 5D ED";
    """
    commands = {
        'info': ("0A 03 75 30 00 1B 1E B9", 59)
    }
    for inverter in inverters:
        print(inverter)
        command, result_length = commands['info']
        out_buffer = bytes.fromhex(command)
        in_buffer: list = inverter.command(out_buffer, result_length)
        for i, line in enumerate(in_buffer):
            print(f'in buffer[{i}] {line}')
    pass


if __name__ == '__main__':
    if args.list:
        Inverter.list_ports()
    else:
        main()
