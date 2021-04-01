import time
from argparse import ArgumentParser
from typing import Tuple

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
        """
         0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16 [ 17  18] = 19 Bytes
        0A  03  0E  00  00  00  DC  00  69  00  8D  00  88  00  14  00  00 [ 30  F5]
        10  03  14  00  00  00 220  00 105  00 141  00 136  00  20  00  00 [ 48 245]
        """
        status = {}

        in_buffer = self._send(EP2000.SENSE)
        if not self._valid_crc(in_buffer):
            return 'CRC failed'
        in_buffer = self._preprocess_status(in_buffer)
        self._translate_status(in_buffer, status)
        return status

    def status(self) -> dict:
        """
        [00A 003] 036 000 000 041 044 000 004 000 00C 002 058 008 0E8 001 0F4 008 0EB 001 0F4 000 002 000 020 000 043 000 005 000 000 000 088 000 010 000 000 000 064 000 029 000 000 000 000 000 000 000 000 000 002 000 001 000 000 000 001 0D3 0D9
        [010 003] 054 000 000 065 068 000 004 000 012 002 088 008 232 001 244 008 235 001 244 000 002 000 032 000 067 000 005 000 000 000 136 000 016 000 000 000 100 000 041 000 000 000 000 000 000 000 000 000 002 000 001 000 000 000 001 211 217

        [00A 003] 036 000 000 041 044 000 004 000 00C 002 058 008 0E8 001 0F3 008 0E1 001 0F3 000 009 000 0AB 000 0D6 000 01C 000 000 000 087 000 010 000 000 000 064 000 02B 000 000 000 000 000 000 000 000 000 002 000 001 000 000 000 001 0B6 082
        [010 003] 054 000 000 065 068 000 004 000 012 002 088 008 232 001 243 008 225 001 243 000 009 000 171 000 214 000 028 000 000 000 135 000 016 000 000 000 100 000 043 000 000 000 000 000 000 000 000 000 002 000 001 000 000 000 001 182 130

        [00A 003] 036 000 000 041 044 000 004 000 00C 002 058 008 0E8 001 0F2 008 0EB 001 0F2 000 009 000 0AA 000 0D1 000 01C 000 000 000 087 000 010 000 000 000 064 000 02B 000 000 000 000 000 000 000 000 000 002 000 001 000 000 000 001 06E 0D4
        [010 003] 054 000 000 065 068 000 004 000 012 002 088 008 232 001 242 008 235 001 242 000 009 000 170 000 209 000 028 000 000 000 135 000 016 000 000 000 100 000 043 000 000 000 000 000 000 000 000 000 002 000 001 000 000 000 001 110 212

        """
        status = {}

        in_buffer = self._send(EP2000.GET_STATUS)
        if not self._valid_crc(in_buffer):
            return 'CRC failed'
        in_buffer = self._preprocess_status(in_buffer)
        self._translate_status(in_buffer, status)
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

    def _valid_crc(self, in_buffer: bytes):
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

    def _preprocess_status(self, in_buffer: bytes):
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
        # stringBuilder.Remove(0, 8);
        # start_index, length = 0, 8
        # in_buffer = in_buffer[start_index: start_index + length]

        # string str = stringBuilder.Remove(stringBuilder.Length - 6, 5).ToString().Trim();

        print(' '.join([f'{byte:02X}' for byte in in_buffer]))
        print(' '.join([f'{byte:03X}' for byte in in_buffer]))
        print(' '.join([f'{byte:03}' for byte in in_buffer]))

        return in_buffer

    def _translate_status(self, in_buffer: bytes, status: dict):
        """
        ep2000Model.MachineType = arrRo[0];
        ep2000Model.SoftwareVersion = Convert.ToInt16(arrRo[1], 16).ToString();
        ep2000Model.WorkState = Enum.GetName(typeof (EPWokrState), (object) Convert.ToInt16(arrRo[2], 16));
        ep2000Model.BatClass = Convert.ToInt16(arrRo[3], 16).ToString() + "V";
        ep2000Model.RatedPower = Convert.ToInt16(arrRo[4], 16).ToString();
        ep2000Model.GridVoltage = ((double) Convert.ToInt16(arrRo[5], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        ep2000Model.GridFrequency = ((double) Convert.ToInt16(arrRo[6], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        ep2000Model.OutputVoltage = ((double) Convert.ToInt16(arrRo[7], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        ep2000Model.OutputFrequency = ((double) Convert.ToInt16(arrRo[8], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        ep2000Model.LoadCurrent = ((double) Convert.ToInt16(arrRo[9], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        ep2000Model.LoadPower = Convert.ToInt16(arrRo[10], 16).ToString();
        ep2000Model.LoadPercent = Convert.ToInt16(arrRo[12], 16).ToString();
        ep2000Model.LoadState = Enum.GetName(typeof (EPLoadState), (object) Convert.ToInt16(arrRo[13], 16));
        ep2000Model.BatteryVoltage = ((double) Convert.ToInt16(arrRo[14], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        ep2000Model.BatteryCurrent = ((double) Convert.ToInt16(arrRo[15], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        ep2000Model.BatterySoc = Convert.ToInt16(arrRo[17], 16).ToString();
        ep2000Model.TransformerTemp = Convert.ToInt16(arrRo[18], 16).ToString();
        ep2000Model.AvrState = Enum.GetName(typeof (EPAVRState), (object) Convert.ToInt16(arrRo[19], 16));
        ep2000Model.BuzzerState = Enum.GetName(typeof (EPBuzzerState), (object) Convert.ToInt16(arrRo[20], 16));
        ep2000Model.Fault = Ep2000Model.FaultDic[(int) Convert.ToInt16(arrRo[21], 16)];
        ep2000Model.Alarm = Convert.ToString(Convert.ToInt16(arrRo[22], 16), 2).PadLeft(4, '0');
        ep2000Model.ChargeState = Enum.GetName(typeof (EPChargeState), (object) Convert.ToInt16(arrRo[23], 16));
        ep2000Model.ChargeFlag = Enum.GetName(typeof (EPChargeFlag), (object) Convert.ToInt16(arrRo[24], 16));
        ep2000Model.MainSw = Enum.GetName(typeof (EPMainSW), (object) Convert.ToInt16(arrRo[25], 16));
        ep2000Model.DelayType = Ep2000Server.Rangelist.FirstOrDefault<EffectiveRange>((Func<EffectiveRange, bool>) (s => s.Kind == "Ep2000Pro" && s.Name == "DelayType" && s.Id == (int) Convert.ToInt16(arrRo[26], 16)))?.Value;

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
    # DONE: connect to inverters
    # DONE: query inverters
    # TODO: calculate CRC (skip for now)
    # TODO: translate incoming data
    # write status to database
    # exit
    inverters = [
        EP2000(port=port, baudrate=9600, timeout=3.0, write_timeout=1.0) for port in Inverters.port_list()
    ]
    for inverter in inverters:
        print(inverter)
        report = inverter.status()
        print(f'report {report}')
    pass


if __name__ == '__main__':
    if args.list:
        print(Inverters.list_ports())
    else:
        main()
