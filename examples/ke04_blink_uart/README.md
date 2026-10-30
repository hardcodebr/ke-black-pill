# ke04_blink_uart — KE04 blink + serial banner

Bare-metal (no SDK) example for the **KE Black Pill KE04** (MKE04Z64). Blinks the red user LED
(**PTA6**) and prints a counter on **UART0** (115200 8N1, the USB-C serial console) and on **UART1**
(PTC7 TX, header). Press **USER** (PTD4) and **RESET** to see the messages change.

- Ready image: `ke04_blink_uart.bin` — load at flash address **0x00000000** with any SWD probe
  that supports Kinetis KE (J-Link, CMSIS-DAP + OpenOCD `target/ke0x.cfg`, pyOCD with the NXP pack).
- Build: `./build.sh` (needs `arm-none-eabi-gcc`); `LED=PTD0 ./build.sh` for another LED pin.
- The build checks that the Flash Configuration Field (0x400–0x40F) leaves the chip **unsecured**
  (FSEC = 0xFE). Never change that unless you know how to mass-erase the part.
- Note: right after an SWD flash the internal clock can run a few percent slow until the first
  RESET; press RESET once if the first serial lines look garbled.

See the [quick-start](../../docs/index.md) and the [safety notes](../../docs/datasheet.md).
