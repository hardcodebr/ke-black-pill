# Examples

Bare-metal (no SDK) firmware for the KE Black Pill, with ready-to-flash `.bin` files
(load at flash address 0x00000000) and build scripts for `arm-none-eabi-gcc`.

| Folder | Board | What it does |
|---|---|---|
| [`ke02_blink_uart`](ke02_blink_uart/) | KE02 | Blink the user LED, counter on UART0 (USB-C console) + UART1 |
| [`ke04_blink_uart`](ke04_blink_uart/) | KE04 | same, for the KE04 |
| [`ke02_echo`](ke02_echo/) | KE02 | blink + UART1 echo |
| [`ke04_echo`](ke04_echo/) | KE04 | blink + UART1 echo |

All images keep the chip **unsecured** (Flash Configuration Field FSEC = 0xFE); the build scripts refuse anything else.
