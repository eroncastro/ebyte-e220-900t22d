from time import sleep_ms


class RawEbyteE220900T22D:

    MAX_READ_RETRIES = 10

    def __init__(self, uart, m0, m1, aux=None):
        self.uart = uart
        self.m0 = m0
        self.m1 = m1
        self.aux = aux

    def read_register(self, starting_address, length):
        self._clear_uart()

        self.uart.write(bytearray([0xc1, starting_address, length]))
        return self._read_response()

    def set_register(self, starting_address, length, *values):
        self._clear_uart()

        command = bytearray([0xc0, starting_address, length])
        command.extend(bytearray(values))
        self.uart.write(command)

        return self._read_response()

    def set_mode(self, mode):
        if self.m0 is None or self.m1 is None:
            raise AttributeError('m0 pin or m1 pin is not set.')

        try:
            m0, m1 = mode
            self.m0.value(m0)
            self.m1.value(m1)
            sleep_ms(20)  # Wait for module to be ready after mode change
        except:
            raise ValueError('Invalid mode.')

    def _wrong_format(self, response):
        return response and all(el == 0xff for el in list(response))

    def _check_response(self, response):
        if self._wrong_format(response):
            raise ValueError('Wrong command format: check starting_address and length.')

    def _read_response(self):
        for _ in range(self.MAX_READ_RETRIES + 1):
            response = self.uart.read()

            if response is not None:
                self._check_response(response)
                return response

            sleep_ms(100)

        self._check_response(None)
        return None

    def _clear_uart(self):
        while self.uart.read():
            continue


class EbyteE220900T22D(RawEbyteE220900T22D):
    class OperationMode:
        NORMAL = (0, 0)
        WOR = (1, 0)
        CONFIGURATION = (0, 1)
        DEEP_SLEEP = (1, 1)

    SERIAL_PORT_RATE = {
        1200: 0b000,
        2400: 0b001,
        4800: 0b010,
        9600: 0b011,
        19200: 0b100,
        38400: 0b101,
        57600: 0b110,
        115200: 0b111
    }

    SERIAL_PARITY_BIT = {
        '8N1': 0b00,
        '8O1': 0b01,
        '8E1': 0b10,
    }

    AIR_DATA_RATE = {
        0.3: 0b000,
        1.2: 0b001,
        2.4: 0b010,
        4.8: 0b011,
        9.6: 0b100,
        19.2: 0b101,
        38.4: 0b110,
        62.5: 0b111
    }

    SUB_PACKET_LENGTH = {
        32: 0b11,
        64: 0b10,
        128: 0b01,
        240: 0b00,
    }

    AMBIENT_NOISE_ENABLED = {
        True: 1,
        False: 0
    }

    TRANSMITTING_POWER = {
        10: 0b11,
        13: 0b10,
        17: 0b01,
        22: 0b00,
    }

    MAX_CHANNEL = 80
    MAX_MODULE_ADDRESS = 65535
    MAX_NETWORK_ID = 255
    MIN_FREQUENCY = 850.125
    MAX_FREQUENCY = 930.125
    MAX_READ_RETRIES = 10

    def __init__(self,
                 uart,
                 m0,
                 m1,
                 aux=None):
        super().__init__(uart, m0, m1, aux)

        # Switch to configuration mode to read registers.
        # Deep sleep mode is the configuration mode, despite the docs.
        self.set_deep_sleep_mode()

        self._module_address = self._saved_module_address()
        self._network_id = self._saved_network_id()
        self._serial_port_rate = self._saved_serial_port_rate()
        self._serial_parity_bit = self._saved_serial_parity_bit()
        self._air_data_rate = self._saved_air_data_rate()
        self._sub_packet_length = self._saved_sub_packet_length()
        self._ambient_noise_enabled = self._saved_ambient_noise_enabled()
        self._transmitting_power = self._saved_transmitting_power()
        self._channel = self._saved_channel()

        # Set to normal mode for operation
        self.set_normal_mode()

    def __repr__(self):
        # Explicit `+` (not adjacent-literal concatenation) between these
        # f-strings: MicroPython 1.17 doesn't support implicit concatenation
        # of adjacent f-string literals.
        return (f'EbyteE220900T22D(' +
                f'uart={self.uart}, ' +
                f'm0={self.m0}, ' +
                f'm1={self.m1}, ' +
                f'aux={self.aux}, ' +
                f'module_address={self.module_address}, ' +
                f'network_id={self.network_id}, ' +
                f'serial_port_rate={self.serial_port_rate}, ' +
                f'serial_parity_bit={self.serial_parity_bit}, ' +
                f'air_data_rate={self.air_data_rate}, ' +
                f'sub_packet_length={self.sub_packet_length}, ' +
                f'ambient_noise_enabled={self.ambient_noise_enabled}, ' +
                f'transmitting_power={self.transmitting_power}, ' +
                f'channel={self.channel}, ' +
                f'frequency={self.frequency})')

    def set_normal_mode(self):
        self.set_mode(self.OperationMode.NORMAL)

    def set_wor_mode(self):
        self.set_mode(self.OperationMode.WOR)

    def set_configuration_mode(self):
        self.set_mode(self.OperationMode.CONFIGURATION)

    def set_deep_sleep_mode(self):
        self.set_mode(self.OperationMode.DEEP_SLEEP)

    @property
    def module_address(self):
        return self._module_address

    @module_address.setter
    def module_address(self, value):
        if type(value) != int or value < 0 or value > self.MAX_MODULE_ADDRESS:
            raise ValueError(
                f'Field module_address must be an int between 0 and {self.MAX_MODULE_ADDRESS}.')

        high, low = value.to_bytes(2, 'big')
        self.set_register(0x00, 0x02, high, low)
        self._module_address = value

    def _saved_module_address(self):
        return self._saved_value(0x00, 0x02)

    @property
    def network_id(self):
        return self._network_id

    @network_id.setter
    def network_id(self, value):
        if type(value) != int or value < 0 or value > self.MAX_NETWORK_ID:
            raise ValueError(
                f'Field network_id must be an int between 0 and {self.MAX_NETWORK_ID}.')

        self.set_register(0x02, 0x01, value)
        self._network_id = value

    def _saved_network_id(self):
        return self._saved_value(0x02, 0x01)

    @property
    def serial_port_rate(self):
        return self._serial_port_rate

    @serial_port_rate.setter
    def serial_port_rate(self, value):
        if type(value) != int or not value in self.SERIAL_PORT_RATE:
            values = ', '.join(map(str, self.SERIAL_PORT_RATE.keys()))
            raise ValueError(
                f'Field serial_port_rate must be one of the following values: {values}.')

        port_rate_bin = self.SERIAL_PORT_RATE[value]

        saved_value = self._saved_value(0x03, 0x01)
        new_value = port_rate_bin << 5 + (0b00011111 & saved_value)
        self.set_register(0x03, 0x01, new_value)

        self._serial_port_rate = value

    def _saved_serial_port_rate(self):
        value = bin(self._saved_value(0x03, 0x01))[2:]
        rate_bin = int(('0' * (8 - len(value)) + value)[0:3], 2)

        for k in self.SERIAL_PORT_RATE:
            if self.SERIAL_PORT_RATE[k] == rate_bin:
                return k

    @property
    def serial_parity_bit(self):
        return self._serial_parity_bit

    @serial_parity_bit.setter
    def serial_parity_bit(self, value):
        if not value in self.SERIAL_PARITY_BIT:
            values = ', '.join(self.SERIAL_PARITY_BIT.keys())
            raise ValueError(
                f'Field serial_parity_bit must be one of the following values: {values}.')

        serial_parity_bit_bin = self.SERIAL_PARITY_BIT[value]

        saved_value = self._saved_value(0x03, 0x01)
        new_value = serial_parity_bit_bin << 3 + (0b11100111 & saved_value)
        self.set_register(0x03, 0x01, new_value)
        self._serial_parity_bit = value

    def _saved_serial_parity_bit(self):
        value = bin(self._saved_value(0x03, 0x01))[2:]
        serial_parity_bit_bin = int(('0' * (8 - len(value)) + value)[3:5], 2)

        for k in self.SERIAL_PARITY_BIT:
            if self.SERIAL_PARITY_BIT[k] == serial_parity_bit_bin:
                return k

    @property
    def air_data_rate(self):
        return self._air_data_rate

    @air_data_rate.setter
    def air_data_rate(self, value):
        if not value in self.AIR_DATA_RATE:
            values = ', '.join(map(str, self.AIR_DATA_RATE.keys()))
            raise ValueError(
                f'Field air_data_rate must be one of the following values: {values}.')

        air_data_rate_bin = self.AIR_DATA_RATE[value]

        saved_value = self._saved_value(0x03, 0x01)
        new_value = air_data_rate_bin + (0b11111000 & saved_value)
        self.set_register(0x03, 0x01, new_value)
        self._air_data_rate = value

    def _saved_air_data_rate(self):
        value = bin(self._saved_value(0x03, 0x01))[2:]
        air_data_rate_bin = int(('0' * (8 - len(value)) + value)[5:], 2)

        for k in self.AIR_DATA_RATE:
            if self.AIR_DATA_RATE[k] == air_data_rate_bin:
                return k

    @property
    def sub_packet_length(self):
        return self._sub_packet_length

    @sub_packet_length.setter
    def sub_packet_length(self, value):
        if type(value) != int or not value in self.SUB_PACKET_LENGTH:
            values = ', '.join(map(str, self.SUB_PACKET_LENGTH.keys()))
            raise ValueError(
                f'Field sub_packet_length must be one of the following values: {values}.')

        sub_packet_length_bin = self.SUB_PACKET_LENGTH[value]

        saved_value = self._saved_value(0x04, 0x01)
        new_value = sub_packet_length_bin << 6 + (0b00111111 & saved_value)
        self.set_register(0x04, 0x01, new_value)
        self._air_data_rate = value

    def _saved_sub_packet_length(self):
        value = bin(self._saved_value(0x04, 0x01))[2:]
        sub_packet_length_bin = int(('0' * (8 - len(value)) + value)[0:2], 2)

        for k in self.SUB_PACKET_LENGTH:
            if self.SUB_PACKET_LENGTH[k] == sub_packet_length_bin:
                return k

    @property
    def ambient_noise_enabled(self):
        return self._ambient_noise_enabled

    @ambient_noise_enabled.setter
    def ambient_noise_enabled(self, value):
        if type(value) != bool:
            raise ValueError('Field ambient_noise_enabled must be a bool.')

        ambient_noise_enabled = self.AMBIENT_NOISE_ENABLED[value]

        saved_value = self._saved_value(0x04, 0x01)
        new_value = ambient_noise_enabled << 5 + (0b11011111 & saved_value)
        self.set_register(0x04, 0x01, new_value)
        self._ambient_noise_enabled = value

    def _saved_ambient_noise_enabled(self):
        value = bin(self._saved_value(0x04, 0x01))[2:]
        ambient_noise_enabled = int(('0' * (8 - len(value)) + value)[2:3], 2)

        for k in self.AMBIENT_NOISE_ENABLED:
            if self.AMBIENT_NOISE_ENABLED[k] == ambient_noise_enabled:
                return k

    @property
    def transmitting_power(self):
        return self._transmitting_power

    @transmitting_power.setter
    def transmitting_power(self, value):
        if type(value) != int or not value in self.TRANSMITTING_POWER:
            values = ', '.join(map(str, self.TRANSMITTING_POWER.keys()))
            raise ValueError(
                f'Field transmitting_power must be one of the following values: {values}.')

        transmitting_power_bin = self.TRANSMITTING_POWER[value]

        saved_value = self._saved_value(0x04, 0x01)
        new_value = transmitting_power_bin + (0b11111100 & saved_value)
        self.set_register(0x04, 0x01, new_value)
        self._transmitting_power = value

    def _saved_transmitting_power(self):
        value = bin(self._saved_value(0x04, 0x01))[2:]
        transmitting_power = int(('0' * (8 - len(value)) + value)[6:], 2)

        for k in self.TRANSMITTING_POWER:
            if self.TRANSMITTING_POWER[k] == transmitting_power:
                return k

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        if type(value) != int or value < 0 or value > self.MAX_CHANNEL:
            raise ValueError(f'Field channel must be an int from 0 to {self.MAX_CHANNEL}.')

        self.set_register(0x05, 0x01, value)
        self._channel = value

    def _saved_channel(self):
        return self._saved_value(0x05, 0x01)

    @property
    def frequency(self):
        return self.MIN_FREQUENCY + self._channel

    @frequency.setter
    def frequency(self, value):
        valid_types = (float, int)

        if (type(value) not in valid_types or
            value < self.MIN_FREQUENCY or
            value > self.MAX_FREQUENCY):
            raise ValueError(
                f'Field frequency must be a number from {self.MIN_FREQUENCY} to {self.MAX_FREQUENCY}.')

        self._channel = round(value - self.MIN_FREQUENCY)

    def _saved_value(self, starting_address, length):
        value = self.read_register(starting_address, length)[3:]
        return int.from_bytes(value, 'big')

    def receive(self):
        self.set_normal_mode()

        response = self._read_response()

        if response is None:
            return None

        target_address = int.from_bytes(response[0:2], 'big')
        target_channel = response[2]
        data = response[3:]

        return target_address, target_channel, data

    def transmit(self, data, target_channel, target_address=None, broadcast=False):
        if broadcast or target_address is None:
            target_address = 0xFFFF
        elif not isinstance(target_address, int) or not (0 <= target_address <= self.MAX_MODULE_ADDRESS):
            raise ValueError(f'target_address must be an int between 0 and {self.MAX_MODULE_ADDRESS}, or None for broadcast.')

        if not isinstance(target_channel, int) or not (0 <= target_channel <= self.MAX_CHANNEL):
            raise ValueError(f'target_channel must be an int between 0 and {self.MAX_CHANNEL}.')

        if not isinstance(data, (bytes, str)):
            raise ValueError('data must be bytes or str.')

        if isinstance(data, str):
            data = data.encode('utf-8')

        self.set_normal_mode()

        packet = target_address.to_bytes(2, 'big') + bytes([target_channel]) + data

        self._clear_uart()
        self.uart.write(packet)
