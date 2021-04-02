import datetime
from argparse import ArgumentParser
from typing import Tuple
import os
import json

from tabulate import tabulate
import serial
from serial.tools.list_ports import comports


class PathDoesNotExistError(Exception):
    """Raised if the log path does not exist"""
    pass


BYTE_ORDER = 'big'
NEWLINE = '\n'
DEFAULT_LOG_PATH = 'log'
SENSE_LOG_FILE_MASK = 'log-sense-date.log'
STATUS_LOG_FILE_MASK = 'log-status-date.log'
SETUP_LOG_FILE_MASK = 'log-setup-date.log'

ap = ArgumentParser(description='Query connected inverters',)
ap.add_argument('--list', action="store_true")
ap.add_argument('--basic', action="store_true")
ap.add_argument('--sense', action="store_true")
ap.add_argument('--status', action="store_true")
ap.add_argument('--setup', action="store_true")
ap.add_argument('--print', action="store_true")
ap.add_argument('--log', action="store_true")
ap.add_argument('--log-path', default=DEFAULT_LOG_PATH)
args = ap.parse_args()

if args.list:
    # args.list
    args.basic = False
    args.sense = False
    args.status = False
    args.setup = False
    args.print = False
    args.log = False
if args.log:
    args.log_path = os.path.abspath(args.log_path)
    if os.path.isfile(args.log_path):
        raise NotADirectoryError(f'{args.log_path}')
    if not os.path.isdir(args.log_path):
        raise PathDoesNotExistError(f'{args.log_path}')
if args.basic:
    # args.list
    # args.basic
    args.sense = False
    args.status = True
    args.setup = False
    args.print = True
    # args.log

BASIC_STATUS = [
    'WorkState',
    'LoadPower',
    'LoadPercent',
    'BatteryVoltage',
    'BatteryCurrent',
    'BatteryCapacity',
    'TransformerTemp',
    'ChargeFlag',
    'MainSwitch',
]


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


class EP2000Enums:
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
    EP_LOAD_STATE = {
        0: 'LOAD_NORMAL',
        1: 'LOAD_ALARM',
        2: 'OVER_LOAD',
    }
    EP_AVR_STATE = {
        0: 'AVR_BYPASS',
        1: 'AVR_STEPDWON',
        2: 'AVR_BOOST'
    }
    EP_BUZZER_STATE = {
        0: 'BUZZ_OFF',
        1: 'BUZZ_BLEW',
        2: 'BUZZ_ALARM',
    }
    FAULT_DICTIONARY = {
        0: "",
        1: "Fan is locked when inverter is off",
        2: "Inverter transformer over temperature",
        3: "battery voltage is too high",
        4: "battery voltage is too low",
        5: "Output short circuited",
        6: "Inverter output voltage is high",
        7: "Overload time out",
        8: "Inverter bus voltage is too high",
        9: "Bus soft start failed",
        11: "Main relay failed",
        21: "Inverter output voltage sensor error",
        22: "Inverter grid voltage sensor error",
        23: "Inverter output current sensor error",
        24: "Inverter grid current sensor error",
        25: "Inverter load current sensor error",
        26: "Inverter grid over current error",
        27: "Inverter radiator over temperature",
        31: "Solar charger battery voltage class error",
        32: "Solar charger current sensor error",
        33: "Solar charger current is uncontrollable",
        41: "Inverter grid voltage is low",
        42: "Inverter grid voltage is high",
        43: "Inverter grid under frequency",
        44: "Inverter grid over frequency",
        51: "Inverter over current protection error",
        52: "Inverter bus voltage is too low",
        53: "Inverter soft start failed",
        54: "Over DC voltage in AC output",
        56: "Battery connection is open",
        57: "Inverter control current sensor error",
        58: "Inverter output voltage is too low",
        61: "Fan is locked when inverter is on.",
        62: "Fan2 is locked when inverter is on.",
        63: "Battery is over-charged.",
        64: "Low battery",
        67: "Overload",
        70: "Output power Derating",
        72: "Solar charger stops due to low battery",
        73: "Solar charger stops due to high PV voltage",
        74: "Solar charger stops due to over load",
        75: "Solar charger over temperature",
        76: "PV charger communication error",
        77: "Parameter error"
    }
    EP_CHARGE_STATE = {
        0: 'CC',
        1: 'CV',
        2: 'FV',
    }
    EP_CHARGE_FLAG = {
        0: 'UN_CHARGE',
        1: 'CHARGED',
    }
    EP_MAIN_SWITCH = {
        0: 'OFF',
        1: 'ON',
    }
    DELAY_TYPE = {
        0: 'STANDARD',
        1: 'LONG_DELAY',
    }
    GRID_FREQUENCY_TYPE = {
        0: '50',
        1: '60',
    }
    EP_BUZZER_SILENCE = {
        0: 'NORMAL',
        1: 'SILENCE',
    }
    STATE = {
        0: 'DISABLE',
        1: 'ENABLE',
    }
    STATE_INVERTED = {
        0: 'ENABLE',
        1: 'DISABLE',
    }


class EP2000(serial.Serial):
    MODEL = 'EP2000'

    INDEX = 0

    SENSE = ("0A 03 79 18 00 07 9C 28", 19)
    STATUS = ("0A 03 75 30 00 1B 1E B9", 59)

    READ_SETUP = ("0A 03 79 18 00 0A 5D ED", 25)
    WRITE_SETUP = ("0A 10 79 18 00 0A 14", -1)

    RESTORE_FACTORY_SETTINGS = ("0A 10 7D 00 00 01 02 00 01 B9 A7", -1)
    REMOTE_RESET = ("0A 10 7D 01 00 01 02 00 01 B8 76", -1)
    REMOTE_SHUTDOWN = ("0A 10 7D 02 00 01 02 00 01 B8 45", -1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.index = self.INDEX
        self.INDEX += 1

    def sense(self) -> dict:
        report = {}
        in_buffer = self._send(EP2000.SENSE)
        if not self._valid_crc(in_buffer):
            return {'error': 'CRC failed'}
        in_buffer = self._preprocess(in_buffer)
        self._translate_sense(in_buffer, report)
        return report

    @staticmethod
    def _translate_sense(in_buffer: bytes, report: dict) -> dict:
        """
          0   1   2    3   4   5   6   7   8   9  10  11  12  13  14  15  16 [ 17  18] = 19 Bytes
        [0A  03  0E]  00  00  00  DC  00  69  00  8D  00  88  00  14  00  00 [ 30  F5]
        [10  03  14]  00  00  00 220  00 105  00 141  00 136  00  20  00  00 [ 48 245]
        """
        device_id = '00 00 00 DC 00 69 00 8D 00 88 00 14 00 00'
        # report['data'] = in_buffer[:]
        report['hex-string'] = ' '.join([f'{byte:02X}' for byte in in_buffer])
        report['detected'] = report['hex-string'] == device_id
        return report

    def status(self) -> dict:
        report = {}
        in_buffer = self._send(EP2000.STATUS)
        if not self._valid_crc(in_buffer):
            return {'error': 'CRC failed'}
        in_buffer = self._preprocess(in_buffer)
        self._translate_status(in_buffer, report)
        return report

    @staticmethod
    def _translate_status(in_buffer: bytes, report: dict) -> dict:
        data = [
            (int.from_bytes(in_buffer[i:i + 2], byteorder=BYTE_ORDER)) for i in range(0, len(in_buffer), 2)
        ]
        report['meta-data'] = {
            'hex-string': ' '.join([f'{byte:02X}' for byte in in_buffer]),
            'data': data,
            'Model': EP2000.MODEL,
        }
        # ep2000Model.MachineType = arrRo[0];
        index = 0
        report['MachineType'] = (index, data[index], data[index], '')
        # ep2000Model.SoftwareVersion = Convert.ToInt16(arrRo[1], 16).ToString();
        index += 1
        report['SoftwareVersion'] = (index, data[index], data[index], '')
        # ep2000Model.WorkState = Enum.GetName(typeof (EPWokrState), (object) Convert.ToInt16(arrRo[2], 16));
        index += 1
        report['WorkState'] = (index, data[index], EP2000Enums.EP_WORK_STATE.get(data[index], 'N/A'), '')
        # ep2000Model.BatClass = Convert.ToInt16(arrRo[3], 16).ToString() + "V";
        index += 1
        report['BatClass'] = (index, data[index], data[index], 'V')
        # ep2000Model.RatedPower = Convert.ToInt16(arrRo[4], 16).ToString();
        index += 1
        report['RatedPower'] = (index, data[index], data[index], 'W')
        # ep2000Model.GridVoltage = ((double) Convert.ToInt16(arrRo[5], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        report['GridVoltage'] = (index, data[index], round(data[index] * 0.1, 1), 'V')
        # ep2000Model.GridFrequency = ((double) Convert.ToInt16(arrRo[6], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        report['GridFrequency'] = (index, data[index], round(data[index] * 0.1, 1), 'Hz')
        # ep2000Model.OutputVoltage = ((double) Convert.ToInt16(arrRo[7], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        report['OutputVoltage'] = (index, data[index], round(data[index] * 0.1, 1), 'V')
        # ep2000Model.OutputFrequency = ((double) Convert.ToInt16(arrRo[8], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        report['OutputFrequency'] = (index, data[index], round(data[index] * 0.1, 1), 'Hz')
        # ep2000Model.LoadCurrent = ((double) Convert.ToInt16(arrRo[9], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        report['LoadCurrent'] = (index, data[index], round(data[index] * 0.1, 1), 'A')
        # ep2000Model.LoadPower = Convert.ToInt16(arrRo[10], 16).ToString();
        index += 1
        report['LoadPower'] = (index, data[index], data[index], 'W')
        # Apparent Power
        index += 1
        report[f'ApparentPower'] = (index, data[index], data[index], 'VA')
        # ep2000Model.LoadPercent = Convert.ToInt16(arrRo[12], 16).ToString();
        index += 1
        report['LoadPercent'] = (index, data[index], data[index], '%')
        # ep2000Model.LoadState = Enum.GetName(typeof (EPLoadState), (object) Convert.ToInt16(arrRo[13], 16));
        index += 1
        report['LoadState'] = (index, data[index], EP2000Enums.EP_LOAD_STATE.get(data[index], 'N/A'), '')
        # ep2000Model.BatteryVoltage = ((double) Convert.ToInt16(arrRo[14], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        report['BatteryVoltage'] = (index, data[index], round(data[index] * 0.1, 1), 'V')
        # ep2000Model.BatteryCurrent = ((double) Convert.ToInt16(arrRo[15], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture);
        index += 1
        report['BatteryCurrent'] = (index, data[index], round(data[index] * 0.1, 1), 'A')
        # Undocumented 16
        index += 1
        report[f'Undocumented:{index}'] = (index, data[index], data[index], '')
        # ep2000Model.BatterySoc = Convert.ToInt16(arrRo[17], 16).ToString();
        index += 1
        report['BatteryCapacity'] = (index, data[index], data[index], '%')
        # ep2000Model.TransformerTemp = Convert.ToInt16(arrRo[18], 16).ToString();
        index += 1
        report['TransformerTemp'] = (index, data[index], data[index], 'C')
        # ep2000Model.AvrState = Enum.GetName(typeof (EPAVRState), (object) Convert.ToInt16(arrRo[19], 16));
        index += 1
        report['AvrState'] = (index, data[index], EP2000Enums.EP_AVR_STATE.get(data[index], 'N/A'), '')
        # ep2000Model.BuzzerState = Enum.GetName(typeof (EPBuzzerState), (object) Convert.ToInt16(arrRo[20], 16));
        index += 1
        report['BuzzerState'] = (index, data[index], EP2000Enums.EP_BUZZER_STATE.get(data[index], 'N/A'), '')
        # ep2000Model.Fault = Ep2000Model.FaultDic[(int) Convert.ToInt16(arrRo[21], 16)];
        index += 1
        report['Fault'] = (index, data[index], EP2000Enums.FAULT_DICTIONARY.get(data[index], 'N/A'), '')
        # ep2000Model.Alarm = Convert.ToString(Convert.ToInt16(arrRo[22], 16), 2).PadLeft(4, '0');
        index += 1
        report['Alarm'] = (index, data[index], f'{data[index]:04}', '')
        # ep2000Model.ChargeState = Enum.GetName(typeof (EPChargeState), (object) Convert.ToInt16(arrRo[23], 16));
        index += 1
        report['ChargeState'] = (index, data[index], EP2000Enums.EP_CHARGE_STATE.get(data[index], 'N/A'), '')
        # ep2000Model.ChargeFlag = Enum.GetName(typeof (EPChargeFlag), (object) Convert.ToInt16(arrRo[24], 16));
        index += 1
        report['ChargeFlag'] = (index, data[index], EP2000Enums.EP_CHARGE_FLAG.get(data[index], 'N/A'), '')
        # ep2000Model.MainSw = Enum.GetName(typeof (EPMainSW), (object) Convert.ToInt16(arrRo[25], 16));
        index += 1
        report['MainSwitch'] = (index, data[index], EP2000Enums.EP_MAIN_SWITCH.get(data[index], 'N/A'), '')
        # ep2000Model.DelayType = Ep2000Server.Rangelist.FirstOrDefault<EffectiveRange>(
        # (Func<EffectiveRange, bool>) (s => s.Kind == "Ep2000Pro" && s.Name == "DelayType" && s.Id == (int) Convert.ToInt16(arrRo[26], 16)))?.Value;
        # ep2000Model.DelayType = Ep2000Server.Rangelist.FirstOrDefault<EffectiveRange>(new Func<EffectiveRange, bool>((object) cDisplayClass40, __methodptr(\u003CGetDataFromProt\u003Eb__0)))?.Value;
        index += 1
        report['DelayType'] = (index, data[index], EP2000Enums.DELAY_TYPE.get(data[index], 'N/A'), '')
        return report

    def read_setup(self) -> dict:
        report = {}
        in_buffer = self._send(EP2000.READ_SETUP)
        if not self._valid_crc(in_buffer):
            return {'error': 'CRC failed'}
        in_buffer = self._preprocess(in_buffer)
        self._translate_setup(in_buffer, report)
        return report

    @staticmethod
    def _translate_setup(in_buffer: bytes, report: dict) -> dict:
        data = [
            (int.from_bytes(in_buffer[i:i + 2], byteorder=BYTE_ORDER)) for i in range(0, len(in_buffer), 2)
        ]
        report['meta-data'] = {
            'hex-string': ' '.join([f'{byte:02X}' for byte in in_buffer]),
            'data': data,
            'Model': EP2000.MODEL,
        }
        # ep2000Model.GridFrequencyType = Ep2000Server.Rangelist.FirstOrDefault<EffectiveRange>(new Func<EffectiveRange, bool>((object) cDisplayClass40, __methodptr(\u003CGetDataFromProt\u003Eb__1)))?.Value;
        index = 0
        report['GridFrequencyType'] = (index, data[index], EP2000Enums.GRID_FREQUENCY_TYPE.get(data[index], 'N/A'), 'Hz')
        # ep2000Model.GridVoltageType = Convert.ToInt16(cDisplayClass40.arrRw[1], 16).ToString() + " V";
        index += 1
        report['GridVoltageType'] = (index, data[index], data[index], 'V')
        # ep2000Model.BatteryLowVoltage = ((double) Convert.ToInt16(cDisplayClass40.arrRw[2], 16) * 0.1).ToString("F1") + "V";
        index += 1
        report['BatteryLowVoltage'] = (index, data[index], round(data[index] * 0.1, 1), 'V')
        # ep2000Model.ConstantChargeVoltage = ((double) Convert.ToInt16(cDisplayClass40.arrRw[3], 16) * 0.1).ToString("F1") + "V";
        index += 1
        report['ConstantChargeVoltage'] = (index, data[index], round(data[index] * 0.1, 1), 'V')
        # ep2000Model.FloatChargeVoltage = ((double) Convert.ToInt16(cDisplayClass40.arrRw[4], 16) * 0.1).ToString((IFormatProvider) CultureInfo.InvariantCulture) + "V";
        index += 1
        report['FloatChargeVoltage'] = (index, data[index], round(data[index] * 0.1, 1), 'V')
        # ep2000Model.BulkChargeCurrent = Convert.ToInt16(cDisplayClass40.arrRw[5], 16).ToString((IFormatProvider) CultureInfo.InvariantCulture) + "A";
        index += 1
        report['BulkChargeCurrent'] = (index, data[index], data[index], 'A')
        # ep2000Model.BuzzerSilence = Enum.GetName(typeof (EPBuzzerSilence), (object) Convert.ToInt16(cDisplayClass40.arrRw[6], 16));
        index += 1
        report['BuzzerSilence'] = (index, data[index], EP2000Enums.EP_BUZZER_SILENCE.get(data[index], 'N/A'), '')
        # ep2000Model.EnableGridCharge = Convert.ToInt16(cDisplayClass40.arrRw[7], 16) == (short) 0 ? "Enable" : "Disable";
        index += 1
        report['EnableGridCharge'] = (index, data[index], EP2000Enums.STATE_INVERTED.get(data[index], 'N/A'), '')
        # ep2000Model.EnableKeySound = Convert.ToInt16(cDisplayClass40.arrRw[8], 16) == (short) 0 ? "Enable" : "Disable";
        index += 1
        report['EnableKeySound'] = (index, data[index], EP2000Enums.STATE_INVERTED.get(data[index], 'N/A'), '')
        # ep2000Model.EnableBacklight = Convert.ToInt16(cDisplayClass40.arrRw[9], 16) == (short) 0 ? "Disable" : "Enable";
        index += 1
        report['EnableBacklight'] = (index, data[index], EP2000Enums.STATE.get(data[index], 'N/A'), '')
        return report

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
            print(f'SERIAL RECEIVE PEEK LENGTH: {result_length}')
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


def main():
    # -----------------------------------------------------------------------------------------------------------------
    # DONE: list available serial ports
    # DONE: connect to inverters
    # DONE: query inverters
    # TODO: calculate CRC (skip for now)
    # DONE: translate incoming data
    # TODO: write status to log
    # TODO: write status to database
    # exit
    # -----------------------------------------------------------------------------------------------------------------
    inverters = [
        EP2000(port=port, baudrate=9600, timeout=3.0, write_timeout=1.0) for port in Inverters.port_list()
    ]
    # -----------------------------------------------------------------------------------------------------------------
    for i in range(len(inverters)):
        timestamp = datetime.datetime.now().timestamp()
        inverter = inverters[i]
        if args.print:
            print(inverter)
        # -------------------------------------------------------------------------------------------------------------
        if args.sense:
            report = inverter.sense()
            if args.print:
                print(tabulate(
                    [[key, value] for key, value in report.items()],
                    headers=['Name', 'Value'], tablefmt='psql'
                ))
            if args.log:
                buffer = [f'{timestamp}', f'{inverter.port}']
                buffer.extend([
                    f'{key}:{value}'
                    for key, value in report.items()
                ])
                unc = os.path.join(args.log_path, SENSE_LOG_FILE_MASK)
                with open(unc, 'a') as f:
                    f.write(','.join(buffer))
                    f.write(NEWLINE)
        # -------------------------------------------------------------------------------------------------------------
        if args.status:
            report = inverter.status()
            if args.print and not args.basic:
                print(tabulate(
                    [
                        ([key] + list(value))
                        for key, value in report.items()
                        if key != 'meta-data'
                    ],
                    headers=['Key', 'Index', 'Raw', 'Value', 'Unit'],
                    tablefmt='psql'
                ))
            elif args.print and args.basic:
                print(tabulate(
                    [
                        ([key] + list(value))
                        for key, value in report.items()
                        if key in BASIC_STATUS
                    ],
                    headers=['Key', 'Index', 'Raw', 'Value', 'Unit'],
                    tablefmt='psql'
                ))
            if args.log:
                buffer = [f'{timestamp}', f'{inverter.port}']
                buffer.extend([
                    f'{key}:{",".join(list(value))}'
                    for key, value in report.items()
                    if key != 'meta-data'
                ])
                unc = os.path.join(args.log_path, STATUS_LOG_FILE_MASK)
                with open(unc, 'a') as f:
                    f.write(','.join(buffer))
                    f.write(NEWLINE)
        # -------------------------------------------------------------------------------------------------------------
        if args.setup:
            report = inverter.read_setup()
            if args.print:
                print(tabulate(
                    [([key] + list(value)) for key, value in report.items() if key != 'meta-data'],
                    headers=['Key', 'Index', 'Raw', 'Value', 'Unit'],
                    tablefmt='psql'
                ))
            if args.log:
                buffer = [f'{timestamp}', f'{inverter.port}']
                buffer.extend([
                    f'{key}:{",".join(list(value))}'
                    for key, value in report.items()
                    if key != 'meta-data'
                ])
                unc = os.path.join(args.log_path, SETUP_LOG_FILE_MASK)
                with open(unc, 'a') as f:
                    f.write(','.join(buffer))
                    f.write(NEWLINE)
    # -----------------------------------------------------------------------------------------------------------------


if __name__ == '__main__':
    if args.list:
        print(Inverters.list_ports())
    else:
        main()
