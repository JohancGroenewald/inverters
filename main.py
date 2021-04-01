import time
from argparse import ArgumentParser
from typing import Tuple
from decimal import Decimal
import pprint

import serial
from serial.tools.list_ports import comports

ap = ArgumentParser(description='Query connected inverters',)
ap.add_argument('-l', '--list', action="store_true")
args = ap.parse_args()

BYTE_ORDER = 'big'


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
    MODEL = 'EP2000'

    INDEX = 0

    SENSE = ("0A 03 79 18 00 07 9C 28", 19)
    GET_STATUS = ("0A 03 75 30 00 1B 1E B9", 59)

    GET_SETTINGS = ("0A 03 79 18 00 0A 5D ED", -1)
    SAVE_SETTINGS = ("0A 10 79 18 00 0A 14", -1)

    RESTORE_FACTORY_SETTINGS = ("0A 10 7D 00 00 01 02 00 01 B9 A7", -1)
    REMOTE_RESET = ("0A 10 7D 01 00 01 02 00 01 B8 76", -1)
    REMOTE_SHUTDOWN = ("0A 10 7D 02 00 01 02 00 01 B8 45", -1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.index = Inverter.INDEX
        Inverter.INDEX += 1

    def sense(self) -> dict:
        status = {}
        in_buffer = self._send(EP2000.SENSE)
        if not self._valid_crc(in_buffer):
            return {'error': 'CRC failed'}
        in_buffer = self._preprocess(in_buffer)
        self._translate_sense(in_buffer, status)
        return status

    @staticmethod
    def _translate_sense(in_buffer: bytes, status: dict) -> dict:
        """
          0   1   2    3   4   5   6   7   8   9  10  11  12  13  14  15  16 [ 17  18] = 19 Bytes
        [0A  03  0E]  00  00  00  DC  00  69  00  8D  00  88  00  14  00  00 [ 30  F5]
        [10  03  14]  00  00  00 220  00 105  00 141  00 136  00  20  00  00 [ 48 245]
        """
        device_id = '00 00 00 DC 00 69 00 8D 00 88 00 14 00 00'
        # status['data'] = in_buffer[:]
        status['hex-string'] = ' '.join([f'{byte:02X}' for byte in in_buffer])
        status['detected'] = status['hex-string'] == device_id
        return status

    def status(self) -> dict:
        status = {}
        in_buffer = self._send(EP2000.GET_STATUS)
        if not self._valid_crc(in_buffer):
            return {'error': 'CRC failed'}
        in_buffer = self._preprocess(in_buffer)
        self._translate_status(in_buffer, status)
        return status

    @staticmethod
    def _translate_status(in_buffer: bytes, status: dict) -> dict:
        """
        status['MachineType' : arrRo[0];
        status['SoftwareVersion' : Convert.ToInt16(arrRo[1], 16).ToString();
        status['WorkState' : Enum.GetName(typeof (EPWokrState), (object) Convert.ToInt16(arrRo[2], 16));
        status['BatClass' : Convert.ToInt16(arrRo[3], 16).ToString() + "V";
        status['RatedPower' : Convert.ToInt16(arrRo[4], 16).ToString();
        status['GridVoltage' : ((double) Convert.ToInt16(arrRo[5], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        status['GridFrequency' : ((double) Convert.ToInt16(arrRo[6], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        status['OutputVoltage' : ((double) Convert.ToInt16(arrRo[7], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        status['OutputFrequency' : ((double) Convert.ToInt16(arrRo[8], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        status['LoadCurrent' : ((double) Convert.ToInt16(arrRo[9], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        status['LoadPower' : Convert.ToInt16(arrRo[10], 16).ToString();
        status['LoadPercent' : Convert.ToInt16(arrRo[12], 16).ToString();
        status['LoadState' : Enum.GetName(typeof (EPLoadState), (object) Convert.ToInt16(arrRo[13], 16));
        status['BatteryVoltage' : ((double) Convert.ToInt16(arrRo[14], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        status['BatteryCurrent' : ((double) Convert.ToInt16(arrRo[15], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        status['BatterySoc' : Convert.ToInt16(arrRo[17], 16).ToString();
        status['TransformerTemp' : Convert.ToInt16(arrRo[18], 16).ToString();
        status['AvrState' : Enum.GetName(typeof (EPAVRState), (object) Convert.ToInt16(arrRo[19], 16));
        status['BuzzerState' : Enum.GetName(typeof (EPBuzzerState), (object) Convert.ToInt16(arrRo[20], 16));
        status['Fault' : Ep2000Model.FaultDic[(int) Convert.ToInt16(arrRo[21], 16)];
        status['Alarm' : Convert.ToString(Convert.ToInt16(arrRo[22], 16), 2).PadLeft(4, '0');
        status['ChargeState' : Enum.GetName(typeof (EPChargeState), (object) Convert.ToInt16(arrRo[23], 16));
        status['ChargeFlag' : Enum.GetName(typeof (EPChargeFlag), (object) Convert.ToInt16(arrRo[24], 16));
        status['MainSw' : Enum.GetName(typeof (EPMainSW), (object) Convert.ToInt16(arrRo[25], 16));
        status['DelayType
        """

        data = [
            (int.from_bytes(in_buffer[i:i + 2], byteorder=BYTE_ORDER)) for i in range(0, len(in_buffer), 2)
        ]

        status['meta-data'] = {
            'hex-string': ' '.join([f'{byte:02X}' for byte in in_buffer]),
            'data': data,
            'Model': EP2000.MODEL,
        }

        # ep2000Model.MachineType = arrRo[0];
        index = 0
        status['MachineType'] = (data[index], f'{data[index]}')
        # ep2000Model.SoftwareVersion = Convert.ToInt16(arrRo[1], 16).ToString();
        index += 1
        status['SoftwareVersion'] = (data[index], f'{data[index]}')
        # ep2000Model.WorkState = Enum.GetName(typeof (EPWokrState), (object) Convert.ToInt16(arrRo[2], 16));
        EP_WORK_STATE = {
            1: 'INIT',
            2: 'SELF_CHECK',
            3: 'BACKUP',
            4: 'LINE',
            5: 'STOP',
            6: 'POWER_OFF',
            7: 'GRID_CHG',
            8: 'SOFT_START',
        }
        index += 1
        status['WorkState'] = (data[index], EP_WORK_STATE.get(data[index], 'N/A'))
        # ep2000Model.BatClass = Convert.ToInt16(arrRo[3], 16).ToString() + "V";
        index += 1
        status['BatClass'] = (data[index], data[index])
        # ep2000Model.RatedPower = Convert.ToInt16(arrRo[4], 16).ToString();
        index += 1
        status['RatedPower'] = (data[index], data[index])
        # ep2000Model.GridVoltage = ((double) Convert.ToInt16(arrRo[5], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        status['GridVoltage'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.GridFrequency = ((double) Convert.ToInt16(arrRo[6], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        status['GridFrequency'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.OutputVoltage = ((double) Convert.ToInt16(arrRo[7], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        status['OutputVoltage'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.OutputFrequency = ((double) Convert.ToInt16(arrRo[8], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        status['OutputFrequency'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.LoadCurrent = ((double) Convert.ToInt16(arrRo[9], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        status['LoadCurrent'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.LoadPower = Convert.ToInt16(arrRo[10], 16).ToString();
        index += 1
        status['LoadPower'] = (data[index], data[index])
        # ep2000Model.LoadPercent = Convert.ToInt16(arrRo[12], 16).ToString();
        index += 1
        status['LoadPercent'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.LoadState = Enum.GetName(typeof (EPLoadState), (object) Convert.ToInt16(arrRo[13], 16));
        EP_LOAD_STATE = {
            0: 'LOAD_NORMAL',
            1: 'LOAD_ALARM',
            2: 'OVER_LOAD',
        }
        index += 1
        status['LoadState'] = (data[index], EP_LOAD_STATE.get(data[index], 'N/A'))
        # ep2000Model.BatteryVoltage = ((double) Convert.ToInt16(arrRo[14], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        status['BatteryVoltage'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.BatteryCurrent = ((double) Convert.ToInt16(arrRo[15], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        status['BatteryCurrent'] = (data[index], round(data[index] * 0.1, 1))
        # ep2000Model.BatterySoc = Convert.ToInt16(arrRo[17], 16).ToString();
        index += 1
        status['BatterySoc'] = (data[index], data[index])
        # ep2000Model.TransformerTemp = Convert.ToInt16(arrRo[18], 16).ToString();
        index += 1
        status['TransformerTemp'] = (data[index], data[index])
        # ep2000Model.AvrState = Enum.GetName(typeof (EPAVRState), (object) Convert.ToInt16(arrRo[19], 16));
        index += 1
        status['AvrState'] = (data[index], data[index])
        # ep2000Model.BuzzerState = Enum.GetName(typeof (EPBuzzerState), (object) Convert.ToInt16(arrRo[20], 16));
        index += 1
        status['BuzzerState'] = (data[index], data[index])
        # ep2000Model.Fault = Ep2000Model.FaultDic[(int) Convert.ToInt16(arrRo[21], 16)];
        index += 1
        status['Fault'] = (data[index], data[index])
        # ep2000Model.Alarm = Convert.ToString(Convert.ToInt16(arrRo[22], 16), 2).PadLeft(4, '0');
        index += 1
        status['Alarm'] = (data[index], data[index])
        # ep2000Model.ChargeState = Enum.GetName(typeof (EPChargeState), (object) Convert.ToInt16(arrRo[23], 16));
        index += 1
        status['ChargeState'] = (data[index], data[index])
        # ep2000Model.ChargeFlag = Enum.GetName(typeof (EPChargeFlag), (object) Convert.ToInt16(arrRo[24], 16));
        index += 1
        status['ChargeFlag'] = (data[index], data[index])
        # ep2000Model.MainSw = Enum.GetName(typeof (EPMainSW), (object) Convert.ToInt16(arrRo[25], 16));
        index += 1
        status['MainSw'] = (data[index], data[index])
        # ep2000Model.DelayType = Ep2000Server.Rangelist.FirstOrDefault<EffectiveRange>((Func<EffectiveRange, bool>) (s => s.Kind == "Ep2000Pro" && s.Name == "DelayType" && s.Id == (int) Convert.ToInt16(arrRo[26], 16)))?.Value;
        index += 1
        status['DelayType'] = (data[index], data[index])


        return status

    def _send(self, command: Tuple[str, int]):
        command_string, result_length = command
        out_buffer = bytes.fromhex(command_string)
        count = super().write(out_buffer)
        if count != len(out_buffer):
            raise Inverters.SerialWriteException(f'Bytes written ({len(out_buffer)}) and written count ({count}) mismatch')
        return self._receive(result_length)

    def _receive(self, result_length):
        if result_length == -1:
            bytes_to_read = 100
        else:
            bytes_to_read = result_length
        in_buffer: bytes = super().read(bytes_to_read)
        if result_length == -1:
            result_length = len(in_buffer)
            print(f'PEEK LENGTH: {result_length}')
        if result_length != len(in_buffer):
            raise Inverters.SerialReadException(
                f'Bytes read ({len(in_buffer)}) and result_length ({result_length}) mismatch')
        return in_buffer

    @staticmethod
    def _valid_crc(in_buffer: bytes):
        """
        public bool CRCCheck(byte[] readedBytes)
        {
          byte[] numArray1 = readedBytes;
          byte[] numArray2 = new byte[numArray1.Length - 2];
          int num1 = (int) numArray1[numArray1.Length - 2] + (int) numArray1[numArray1.Length - 1];
          for (int index = 0; index < numArray1.Length - 2; ++index)
              numArray2[index] = numArray1[index];
          byte maxValue1 = byte.MaxValue;
          byte maxValue2 = byte.MaxValue;
          byte num2 = 1;
          byte num3 = 160;
          foreach (byte num4 in numArray2)
          {
            maxValue1 ^= num4;
            for (int index = 0; index <= 7; ++index)
            {
              int num5 = (int) maxValue2;
              byte num6 = maxValue1;
              maxValue2 >>= 1;
              maxValue1 >>= 1;
              if ((num5 & 1) == 1)
                maxValue1 |= (byte) 128;
              if (((int) num6 & 1) == 1)
              {
                maxValue2 ^= num3;
                maxValue1 ^= num2;
              }
            }
          }
          byte[] numArray3 = new byte[2]{ maxValue2, maxValue1 };
          return (int) maxValue2 + (int) maxValue1 == num1;
        }
        """
        crc = True
        # array1 = in_buffer[:]
        # array2 = bytes(len(in_buffer) - 2)
        # check: int = int(in_buffer[-2]) + int(in_buffer[-1])
        # print(int(in_buffer[-2]), int(in_buffer[-1]), check)
        # maxValue1 = int(255).to_bytes(1, byteorder='big')
        # maxValue2 = int(255).to_bytes(1, byteorder='big')
        # num2 = int(1).to_bytes(1, byteorder='big')
        # num3 = int(160).to_bytes(1, byteorder='big')
        #
        # for byte in array2:
        #     maxValue1[0]

        """
        foreach (byte num4 in numArray2)
        {
            maxValue1 ^= num4;
            for (int index = 0; index <= 7; ++index)
            {
                int num5 = (int) maxValue2;
                byte num6 = maxValue1;
                maxValue2 >>= 1;
                maxValue1 >>= 1;
                if ((num5 & 1) == 1)
                maxValue1 |= (byte) 128;
                if (((int) num6 & 1) == 1)
                {
                    maxValue2 ^= num3;
                    maxValue1 ^= num2;
                }
            }
        }
        """

        return crc

    @staticmethod
    def _preprocess(in_buffer: bytes):
        """
        Remove header: first 3 bytes [handshake + data bytes returned]
        Remove CRC   : last 2 bytes
        """
        open = 3
        close = -2
        return in_buffer[open:close]


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
    # DONE: connect to inverters
    # DONE: query inverters
    # TODO: calculate CRC (skip for now)
    # TODO: translate incoming data
    # write status to database
    # exit
    inverters = [
        EP2000(port=port, baudrate=9600, timeout=3.0, write_timeout=1.0) for port in Inverters.port_list()[:1]
    ]
    for i in range(len(inverters)):
        inverter = inverters[i]
        print(inverter)
        sense = inverter.sense()
        pprint.pprint(f'sense {sense}')
        status = inverter.status()
        for key, value in status.items():
            pprint.pprint(f'{key}: {value}')
    pass


if __name__ == '__main__':
    if args.list:
        print(Inverters.list_ports())
    else:
        main()
