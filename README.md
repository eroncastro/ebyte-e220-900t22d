# ebyte-e220-900t22d

MicroPython driver for the [EBYTE E220-900T22D](https://www.cdebyte.com/products/E220-900T22D) LoRa module (LLCC68), talking to it over UART with the M0/M1 mode pins.

Two classes are provided in `src/ebyte_e220_900t22d.py`:

- `RawEbyteE220900T22D` — low level interface over the module's register read/write protocol and mode pins.
- `EbyteE220900T22D` — extends `RawEbyteE220900T22D`, adding a high-level interface for interacting with the module. On boot, reads and exposes typed properties (`module_address`, `serial_port_rate`, `serial_parity_bit`, `air_data_rate`, `sub_packet_length`, `ambient_noise_enabled`, `transmitting_power`, `channel`, `frequency`, `rssi_byte_enabled`, `fixed_transmission`, `lbt_enabled`, `wor_cycle`), plus `transmit()` / `receive()` as a raw byte pipe for normal-mode operation (framing and addressing are left to the caller).

## Deploying to a device

```sh
uvx mpremote cp src/ebyte_e220_900t22d.py :lib/ebyte_e220_900t22d.py
```

## Usage

```python
from machine import UART, Pin
from ebyte_e220_900t22d import EbyteE220900T22D

uart = UART(2, baudrate=9600)
m0 = Pin(19, Pin.OUT)
m1 = Pin(18, Pin.OUT)

lora = EbyteE220900T22D(uart, m0, m1)
print(lora)
lora.channel = 10
print(lora)

lora.transmit(b"hello")        # raw bytes over the air
print(lora.receive())          # raw bytes waiting on the module, or None
```

## `transmit()` / `receive()`

In normal mode the module's UART is transparent: bytes written to it go out over
the air as-is, and bytes received over the air come back on TXD as-is. `transmit()`
and `receive()` are a thin wrapper over that — they switch the module to normal
mode (mode 0) and then write or read. They add no protocol of their own.

`transmit(data)`
- `data` is `bytes`, `bytearray`, or `str` (encoded as UTF-8); anything else raises `ValueError`.
- The bytes are written verbatim. No address, channel, or length is prepended.

`receive(size=None)`
- Returns whatever bytes are currently buffered on the module's TXD, or `None` if
  there are none. With `size`, reads at most that many bytes.
- It does not block for a message, delimit messages, or check integrity. A call
  can return a partial message, one message, or several concatenated.

Message boundaries, integrity (e.g. a CRC), retransmission, and addressing are the
caller's responsibility — they depend entirely on what runs on the other end. If
you need the module's hardware address filtering, set `lora.fixed_transmission = True`
and prepend the `addrH addrL channel` bytes to `data` yourself before calling
`transmit()`; the receiver gets only the payload either way.

## Restoring defaults

```python
lora.restore_defaults()          # every field back to its documented default
lora.restore_defaults(channel=17)  # ...and set the channel too
```

Applies the factory default listed for each field in the module's register table.
`channel` has no single documented default across variants, so it's left alone
unless you pass one.

## Testing

Tests run on plain CPython with `pytest` — no MicroPython build or hardware required. `machine.UART`/`machine.Pin` are stood in for with small fakes in `tests/fakes.py`, and `tests/conftest.py` shims `time.sleep_ms` (a MicroPython builtin that CPython's `time` module lacks) so the module imports cleanly.

```sh
uv sync
uv run pytest
```
