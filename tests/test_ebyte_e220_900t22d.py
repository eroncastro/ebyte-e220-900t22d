import pytest

from ebyte_e220_900t22d import EbyteE220900T22D, RawEbyteE220900T22D
from fakes import FakePin, FakeUART


def reg_response(addr, payload):
    """Build a fake register-read reply: [0xC1, addr, len, *payload]."""
    payload = bytes(payload)
    return bytes([0xC1, addr, len(payload)]) + payload


# REG0 (address 0x02) = 0x62 = 0b01100010 decodes to:
#   serial_port_rate=9600 (0b011), serial_parity_bit='8N1' (0b00), air_data_rate=2.4 (0b010)
REG_0 = 0x62
# REG1 (address 0x03) = 0xA1 = 0b10100001 decodes to:
#   sub_packet_length=64 (0b10), ambient_noise_enabled=True (1), transmitting_power=17 (0b01)
REG_1 = 0xA1

INIT_RESPONSES = [
    reg_response(0x00, [0x12, 0x34]),  # module_address
    reg_response(0x02, [REG_0]),       # serial_port_rate
    reg_response(0x02, [REG_0]),       # serial_parity_bit
    reg_response(0x02, [REG_0]),       # air_data_rate
    reg_response(0x03, [REG_1]),       # sub_packet_length
    reg_response(0x03, [REG_1]),       # ambient_noise_enabled
    reg_response(0x03, [REG_1]),       # transmitting_power
    reg_response(0x04, [0x0A]),        # channel
]


@pytest.fixture
def uart():
    return FakeUART()


@pytest.fixture
def pins():
    return FakePin(), FakePin()


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    """Every test gets a no-op, spyable sleep_ms."""
    import ebyte_e220_900t22d as module

    calls = []
    monkeypatch.setattr(module, "sleep_ms", lambda ms: calls.append(ms))
    return calls


@pytest.fixture
def device(pins):
    m0, m1 = pins
    uart = FakeUART(queue=list(INIT_RESPONSES))
    return EbyteE220900T22D(uart, m0, m1), uart, m0, m1


class TestRawReadRegister:
    def test_writes_read_command_and_returns_response(self, uart, pins):
        m0, m1 = pins
        uart.queue.append(reg_response(0x03, [0x01]))

        raw = RawEbyteE220900T22D(uart, m0, m1)
        response = raw.read_register(0x03, 0x01)

        assert uart.written == [bytes([0xC1, 0x03, 0x01])]
        assert response == reg_response(0x03, [0x01])

    def test_drains_stale_bytes_before_writing(self, uart, pins):
        m0, m1 = pins
        uart.pending = b"\x00\x00"  # garbage left over from a previous exchange
        uart.queue.append(reg_response(0x03, [0x01]))

        raw = RawEbyteE220900T22D(uart, m0, m1)
        response = raw.read_register(0x03, 0x01)

        assert response == reg_response(0x03, [0x01])
        assert uart.written == [bytes([0xC1, 0x03, 0x01])]

    def test_drain_raises_when_peer_keeps_streaming(self, uart, pins):
        m0, m1 = pins
        uart.incoming = [b"\xff"] * 100  # peer never stops talking
        raw = RawEbyteE220900T22D(uart, m0, m1)

        with pytest.raises(RuntimeError, match="not empty"):
            raw._clear_uart()

        # bounded: it gave up after MAX_CLEAR_READS instead of looping forever
        assert 100 - len(uart.incoming) == RawEbyteE220900T22D.MAX_CLEAR_READS

    def test_no_response_returns_none(self, uart, pins, no_delay):
        m0, m1 = pins
        raw = RawEbyteE220900T22D(uart, m0, m1)

        assert raw.read_register(0x03, 0x01) is None
        # one sleep per attempt, including the final one before giving up
        assert len(no_delay) == RawEbyteE220900T22D.MAX_READ_RETRIES + 1

    def test_all_ff_response_raises(self, uart, pins):
        m0, m1 = pins
        uart.queue.append(bytes([0xFF, 0xFF, 0xFF, 0xFF]))

        raw = RawEbyteE220900T22D(uart, m0, m1)

        with pytest.raises(ValueError, match="Wrong command format"):
            raw.read_register(0x03, 0x01)


class TestRawSetRegister:
    def test_writes_set_command_with_values(self, uart, pins):
        m0, m1 = pins
        raw = RawEbyteE220900T22D(uart, m0, m1)

        raw.set_register(0x03, 0x02, 0x01, 0x02)

        assert uart.written == [bytes([0xC0, 0x03, 0x02, 0x01, 0x02])]


class TestRawSetMode:
    def test_sets_pin_values_for_mode(self, uart, pins, no_delay):
        m0, m1 = pins
        raw = RawEbyteE220900T22D(uart, m0, m1)

        raw.set_mode((1, 0))

        assert m0.history == [1]
        assert m1.history == [0]
        assert no_delay == [20]

    def test_missing_pins_raises_attribute_error(self, uart):
        raw = RawEbyteE220900T22D(uart, None, None)

        with pytest.raises(AttributeError):
            raw.set_mode((0, 0))

    @pytest.mark.parametrize("bad", [None, (1,), (0, 1, 0), "ab", (2, 0), (0, -1)])
    def test_invalid_mode_raises_value_error(self, uart, pins, bad):
        m0, m1 = pins
        raw = RawEbyteE220900T22D(uart, m0, m1)

        with pytest.raises(ValueError):
            raw.set_mode(bad)

        assert m0.history == [] and m1.history == []  # nothing written on a bad mode


class TestConstructorDecodesRegisters:
    def test_decodes_saved_configuration(self, device):
        dev, uart, m0, m1 = device

        assert dev.module_address == 0x1234
        assert dev.serial_port_rate == 9600
        assert dev.serial_parity_bit == "8N1"
        assert dev.air_data_rate == 2.4
        assert dev.sub_packet_length == 64
        assert dev.ambient_noise_enabled is True
        assert dev.transmitting_power == 17
        assert dev.channel == 10
        assert dev.frequency == pytest.approx(860.125)

    def test_enters_configuration_then_normal_mode(self, device):
        dev, uart, m0, m1 = device

        # configuration / deep sleep (1, 1) first, normal (0, 0) last
        assert m0.history[0] == 1 and m1.history[0] == 1
        assert m0.history[-1] == 0 and m1.history[-1] == 0

    def test_no_response_raises_value_error(self, uart, pins, no_delay):
        m0, m1 = pins

        with pytest.raises(ValueError, match="No response from module"):
            EbyteE220900T22D(uart, m0, m1)


class TestModuleAddress:
    def test_valid_value_writes_two_bytes_big_endian(self, device):
        dev, uart, m0, m1 = device

        dev.module_address = 0xABCD

        assert uart.written[-1] == bytes([0xC0, 0x00, 0x02, 0xAB, 0xCD])
        assert dev.module_address == 0xABCD

    @pytest.mark.parametrize("bad", [-1, 65536, 1.5, "x"])
    def test_rejects_out_of_range_or_wrong_type(self, device, bad):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.module_address = bad


class TestChannelAndFrequency:
    def test_valid_channel_writes_one_byte(self, device):
        dev, uart, m0, m1 = device

        dev.channel = 20

        assert uart.written[-1] == bytes([0xC0, 0x04, 0x01, 20])
        assert dev.frequency == pytest.approx(870.125)

    @pytest.mark.parametrize("bad", [-1, 81, 1.5])
    def test_rejects_out_of_range_or_wrong_type(self, device, bad):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.channel = bad

    def test_frequency_setter_rounds_to_channel_and_writes_it(self, device):
        dev, uart, m0, m1 = device

        dev.frequency = 860.2

        assert dev.channel == 10  # round(860.2 - 850.125) == 10
        assert uart.written[-1] == bytes([0xC0, 0x04, 0x01, 10])

    @pytest.mark.parametrize("bad", [849, 931, "x"])
    def test_frequency_rejects_out_of_range_or_wrong_type(self, device, bad):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.frequency = bad


class TestAirDataRate:
    """The only bit-packed field whose setter math (add, no shift) is correct."""

    def test_setting_updates_only_its_bits(self, device):
        dev, uart, m0, m1 = device
        uart.queue.append(reg_response(0x02, [REG_0]))  # answers the internal re-read

        dev.air_data_rate = 62.5  # 0b111

        # low 3 bits replaced, high 5 bits (rate+parity) preserved: 0b01100 111 = 0x67
        assert uart.written[-1] == bytes([0xC0, 0x02, 0x01, 0b01100111])
        assert dev.air_data_rate == 62.5

    def test_rejects_unknown_value(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.air_data_rate = 999


class TestTransmittingPower:
    """The other bit-packed field whose setter math (add, no shift) is correct."""

    def test_setting_updates_only_its_bits(self, device):
        dev, uart, m0, m1 = device
        uart.queue.append(reg_response(0x03, [REG_1]))  # answers the internal re-read

        dev.transmitting_power = 10  # 0b11

        # high 6 bits (sub-packet+noise+reserved) preserved, low 2 bits replaced: 0b101000 11 = 0xA3
        assert uart.written[-1] == bytes([0xC0, 0x03, 0x01, 0b10100011])
        assert dev.transmitting_power == 10

    def test_rejects_unknown_value(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.transmitting_power = 999


class TestSerialPortRate:
    def test_setting_updates_only_its_bits(self, device):
        dev, uart, m0, m1 = device
        uart.queue.append(reg_response(0x02, [REG_0]))  # answers the internal re-read

        dev.serial_port_rate = 115200  # 0b111

        # high 3 bits replaced, low 5 bits (parity+air rate) preserved: 0b111 00010
        assert uart.written[-1] == bytes([0xC0, 0x02, 0x01, 0b11100010])
        assert dev.serial_port_rate == 115200

    def test_rejects_unknown_value(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.serial_port_rate = 12345


class TestSerialParityBit:
    def test_setting_updates_only_its_bits(self, device):
        dev, uart, m0, m1 = device
        uart.queue.append(reg_response(0x02, [REG_0]))  # answers the internal re-read

        dev.serial_parity_bit = "8E1"  # 0b10

        # bits 4-3 replaced, rate (7-5) and air rate (2-0) preserved: 0b011 10 010
        assert uart.written[-1] == bytes([0xC0, 0x02, 0x01, 0b01110010])
        assert dev.serial_parity_bit == "8E1"

    def test_rejects_unknown_value(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.serial_parity_bit = "9N2"


class TestSubPacketLength:
    def test_setting_updates_only_its_bits(self, device):
        dev, uart, m0, m1 = device
        uart.queue.append(reg_response(0x03, [REG_1]))  # answers the internal re-read

        dev.sub_packet_length = 128  # 0b01

        # bits 7-6 replaced, low 6 bits (noise+reserved+power) preserved: 0b01 100001
        assert uart.written[-1] == bytes([0xC0, 0x03, 0x01, 0b01100001])
        assert dev.sub_packet_length == 128

    def test_rejects_unknown_value(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.sub_packet_length = 99


class TestAmbientNoiseEnabled:
    def test_enabling_sets_only_bit_5(self, device):
        dev, uart, m0, m1 = device
        uart.queue.append(reg_response(0x03, [REG_1]))  # answers the internal re-read

        dev.ambient_noise_enabled = True

        # bit 5 set, every other bit of 0xA1 preserved
        assert uart.written[-1] == bytes([0xC0, 0x03, 0x01, 0xA1])
        assert dev.ambient_noise_enabled is True

    def test_disabling_clears_only_bit_5(self, device):
        dev, uart, m0, m1 = device
        uart.queue.append(reg_response(0x03, [REG_1]))  # answers the internal re-read

        dev.ambient_noise_enabled = False

        # bit 5 cleared, every other bit of 0xA1 preserved: 0xA1 & ~0x20 == 0x81
        assert uart.written[-1] == bytes([0xC0, 0x03, 0x01, 0x81])
        assert dev.ambient_noise_enabled is False

    def test_rejects_non_bool(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.ambient_noise_enabled = 1


class TestReceive:
    def test_parses_address_channel_and_data(self, device):
        dev, uart, m0, m1 = device
        uart.incoming.append(bytes([0x00, 0x2A, 0x05]) + b"hello")

        result = dev.receive()

        assert result == (0x2A, 5, b"hello")

    def test_no_response_returns_none(self, device, no_delay):
        dev, uart, m0, m1 = device

        assert dev.receive() is None


class TestTransmit:
    def test_sends_to_explicit_target(self, device):
        dev, uart, m0, m1 = device

        dev.transmit(b"hi", target_channel=5, target_address=0x0102)

        assert uart.written[-1] == bytes([0x01, 0x02, 0x05]) + b"hi"

    def test_broadcast_uses_ffff(self, device):
        dev, uart, m0, m1 = device

        dev.transmit("hi", target_channel=5, broadcast=True)

        assert uart.written[-1] == bytes([0xFF, 0xFF, 0x05]) + b"hi"

    def test_string_payload_is_utf8_encoded(self, device):
        dev, uart, m0, m1 = device

        dev.transmit("café", target_channel=0, target_address=1)

        assert uart.written[-1] == bytes([0x00, 0x01, 0x00]) + "café".encode("utf-8")

    def test_rejects_bad_target_channel(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.transmit(b"hi", target_channel=999, target_address=1)

    def test_rejects_bad_target_address(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.transmit(b"hi", target_channel=1, target_address=-1)

    def test_rejects_non_bytes_non_str_data(self, device):
        dev, uart, m0, m1 = device

        with pytest.raises(ValueError):
            dev.transmit(123, target_channel=1, target_address=1)
