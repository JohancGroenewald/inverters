import time
from argparse import ArgumentParser
from typing import Tuple,

import serial
from serial.tools.list_ports import comports

ap = ArgumentParser(description='Query connected inverters',)
ap.add_argument('-l', '--list', action="store_true")
args = ap.parse_args()


class Inverters:

    class SerialWriteException(Exception):
        """Raised when bytes written does not agree with the return count"""
        pass

    class SerialReadException(Exception):
        """Raised when bytes read does not agree with the result length"""
        pass

    @staticmethod
    def list_ports():
        """
        apply_usb_info,
        description,
        device,
        hwid,
        interface,
        location,
        manufacturer,
        name,
        pid,
        product,
        serial_number,
        usb_description,
        usb_info,
        vid
        """
        attributes = [attribute.strip() for attribute in Inverters.list_ports.__doc__.split(',')]
        buffer = []
        padding = 18
        for port in comports():
            for attribute in attributes:
                if hasattr(port, attribute):
                    value = getattr(port, attribute, None)
                    if callable(value):
                        buffer.append(f'{attribute:{padding}} {str(value())}')
                    else:
                        buffer.append(f'{attribute:{padding}} {str(value)}')
            buffer.append('-' * 40)
        return '\n'.join(buffer)

    @staticmethod
    def port_list():
        ports = []
        for port in comports():
            ports.append(port.device)
        return ports


class EP2000(serial.Serial):
    """
    reset         :    "0A 10 7D 00 00 01 02 00 01 B9 A7"
    SaveReadinData:    "0A 10 79 18 00 0A 14"
    string textSend1 = "0A 03 75 30 00 1B 1E B9";
    string textSend2 = "0A 03 79 18 00 0A 5D ED";
    """
    INDEX = 0
    GET_INFO = ("0A 03 75 30 00 1B 1E B9", 59)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.index = Inverter.INDEX
        Inverter.INDEX += 1

    def send(self, command: Tuple[str, int]):
        command_string, result_length = command
        out_buffer = bytes.fromhex(command_string)
        count = super().write(out_buffer)
        if count != len(out_buffer):
            raise Inverters.SerialWriteException(f'Bytes written ({len(out_buffer)}) and written count ({count}) mismatch')
        return self._receive(result_length)

    def _receive(self, result_length):
        in_buffer: bytes = super().read(result_length)
        if result_length != len(in_buffer):
            raise Inverters.SerialReadException(
                f'Bytes read ({len(in_buffer)}) and result_length ({result_length}) mismatch')
        return in_buffer

    def translate(self):
        pass


class Inverter(serial.Serial):
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
    # DONE: list available serial ports
    # connect to inverters
    # query inverters
    # write status to database
    # exit
    inverters = [
        EP2000(port=port, baudrate=9600, timeout=3.0, write_timeout=1.0) for port in Inverters.port_list()
    ]

    commands = {
        'info': ("0A 03 75 30 00 1B 1E B9", 59)
    }
    for inverter in inverters:
        print(inverter)
        in_buffer = inverter.send(inverter.GET_INFO)
        print(f'in buffer {in_buffer}')
    pass


if __name__ == '__main__':
    if args.list:
        print(Inverters.list_ports())
    else:
        main()
