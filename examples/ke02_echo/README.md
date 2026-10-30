# ke02_echo — KE02 blink + serial echo

`ke02_blink_uart` plus a **receiver on UART1**: every byte received on UART1 (PTC6 RX) is echoed
back on UART1 TX (PTC7) and reported on UART0 (the USB-C serial console). Bare metal, no SDK,
for the **KE Black Pill KE02**.

- Ready image: `ke02_echo.bin` — load at flash address **0x00000000** with any SWD probe that
  supports Kinetis KE. Build with `./build.sh` (`arm-none-eabi-gcc`).
- Same unsecured-FCF check as the blink example.
