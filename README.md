# ebyte-e220-900t22d

MicroPython driver for the [EBYTE E220-900T22D](https://www.cdebyte.com/products/E220-900T22D) LoRa module (SX1262), talking to it over UART with the M0/M1 mode pins.

Two classes are provided in `src/ebyte_e220_900t22d.py`:

- `RawEbyteE220900T22D` — low level interface over the module's register read/write protocol and mode pins.
- `EbyteE220900T22D` — extends `RawEbyteE220900T22D`, adding a high-level interface for interacting with the module. On boot, reads and exposes typed properties (`module_address`, `network_id`, `serial_port_rate`, `serial_parity_bit`, `air_data_rate`, `sub_packet_length`, `ambient_noise_enabled`, `transmitting_power`, `channel`, `frequency`), plus `transmit()` / `receive()` for normal-mode operation.

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
lora.transmit(b"hello", target_channel=10, broadcast=True)
```

## Testing

Tests run on plain CPython with `pytest` — no MicroPython build or hardware required. `machine.UART`/`machine.Pin` are stood in for with small fakes in `tests/fakes.py`, and `tests/conftest.py` shims `time.sleep_ms` (a MicroPython builtin that CPython's `time` module lacks) so the module imports cleanly.

```sh
uv sync
uv run pytest
```
