# Datasheet — KE Black Pill (HC26060)

> 🏠 [HardCode — all products](https://github.com/hardcodebr) · 🛒 [Shop](https://lectronz.com/stores/hardcode-electronics) · 🌐 [hardcode.com.br](https://hardcode.com.br)

*Rev A (first batch). Items marked ⟨CONFIRM⟩ are not measured yet.*

| | Specification |
|---|---|
| **Type** | Breadboard development module for NXP Kinetis E |
| **SKUs** | HC26060-KE02 · HC26060-KE04 (same board, different MCU) |
| **MCU** | NXP Kinetis KE02 (MKE02Z64) or KE04 (MKE04Z64), 44-pin, Arm Cortex-M0+ |
| **Flash** | 64 KB |
| **Supply (MCU)** | 2.7–5.5 V |
| **Host interface** | USB-C: 5 V power + on-board USB-serial to UART0 (the MCU itself has no USB) |
| **Debug / programming** | SWD — 1x4 right-angle header J1 (3V3, DIO, CLK, GND); RESET on header pin RST |
| **I/O on headers** | 34 GPIO + RESET on 2 × 1x20, 2.54 mm pitch |
| **ADC** | 12-bit, 12 channels on the headers |
| **Timers** | FlexTimer PWM (one 6-ch + two 2-ch), periodic timer, RTC; KE04 adds a pulse width timer |
| **Serial** | 3 UART (UART0 = USB-serial), 2 SPI, I2C (1 on KE02, 2 on KE04) |
| **Analog** | 2 comparators with 6-bit DAC |
| **User I/O** | RESET + USER buttons, red user LED, green power LED |
| **Clock** | Internal, factory-trimmed (no crystal fitted) |
| **Dimensions** | 20.78 × 52.81 mm, 1.6 mm PCB (Black Pill size) |
| **Mounting** | None — breadboard / carrier module |
| **Toolchain** | MCUXpresso IDE + SDK, Arm GNU Toolchain; flash with J-Link, OpenOCD, pyOCD ([Quick-Start](index.md#4-flash-over-swd)) |
| **Compliance** | Development module for lab use — no CE/FCC certification |

## KE02 vs KE04

| | **HC26060-KE02** | **HC26060-KE04** |
|---|---|---|
| MCU | Kinetis KE02 (MKE02Z64) | Kinetis KE04 (MKE04Z64) |
| Core clock (max) | 40 MHz (bus 20 MHz) | 48 MHz (bus 24 MHz) |
| Flash / RAM | 64 KB / 4 KB | 64 KB / 8 KB |
| EEPROM | 256 B | — |
| I2C | 1 | 2 (I2C1 on `E0`/`E1`) |
| Pulse width timer | — | yes |
| Unique ID | 64-bit | 80-bit |
| Supply, I/O levels | 2.7–5.5 V, I/O follow the supply | same |
| Board, pinout, headers | same | same |

**Which one?** Pick the one your product uses. Starting fresh: the KE04 has more RAM and speed;
the KE02 has on-chip EEPROM.

## Power

The board has three power points, joined by diodes so they don't back-feed each other.

| Source | Where | What happens |
|---|---|---|
| **USB-C** 5 V | USB-C | Feeds the 3.3 V regulator and the USB-serial. MCU supply ≈ 3.0–3.1 V ⟨CONFIRM: measure⟩. The USB 5 V also appears on the **5V** pin. |
| **5 V in** | **5V** pin (J3.1) | Feeds the 3.3 V regulator; a diode stops it from reaching your USB port. |
| **2.7–5.5 V in** | any **3V3** pin (J3.3, J4.1, J1.1) | Powers the MCU **directly** — use this for **5 V operation**, or to power the board from your SWD probe. A diode stops it from back-feeding the regulator. |

- If USB and a 3V3-pin supply are both connected, the higher voltage supplies the MCU.
- The pins marked **3V3** carry the MCU supply. If you feed 5 V into one, they are all at 5 V.
- The **5V** pin is not regulated — it is the USB voltage minus a diode drop.

## Electrical

| Parameter | Value |
|---|---|
| MCU supply | 2.7–5.5 V (flash programming also works over the full range) |
| **I/O voltage** | **= MCU supply**, the same on both SKUs: ~3 V from USB, up to 5 V when fed on a 3V3 pin |
| Input limit | MCU supply + 0.3 V (per NXP) — at 3.3 V, the I/O are **not** 5 V tolerant |
| Open-drain pins | `A2`, `A3` (PTA2/PTA3, I2C0) — true open-drain outputs |
| High-drive pins | `D0`, `D1`, `E0`, `E1`, `B4`, `B5` |
| USB-serial | Designed for ~3 V operation; at 5 V use a 5 V serial adapter on a header UART |
| Current available to your circuit (from USB) | ⟨CONFIRM: measure under load⟩ |
| Board current, idle | ⟨CONFIRM: measure⟩ |
| MCU temperature rating | −40 to 105 °C (NXP); board not characterised |

## Mechanical

| Item | Value |
|---|---|
| Board outline | 20.78 × 52.81 mm, 1.6 mm FR4 |
| Long headers | 2 × 1x20, **2.54 mm** pitch, rows **0.6 in (15.24 mm)** apart |
| Pin 1 | at the **USB-C end** of both long headers |
| SWD header | 1x4 right-angle at the far short edge; the plastic body sits about 1 mm past the board edge |
| USB-C | centred on the near short edge |
| Height | ⟨CONFIRM: measure, with and without headers⟩ |
| Weight | ⟨CONFIRM: weigh⟩ |
| Mounting holes | none |
| Breadboard | Straddles the centre gap of a standard breadboard, like a Black Pill ⟨CONFIRM: count the free holes per side on a real breadboard⟩ |

The outline and power-pin positions follow the common Black Pill layout. The signal pins differ
(different MCU). ⟨CONFIRM: test one Black Pill carrier board before claiming carrier compatibility⟩

## Ordering information

| SKU | Description |
|---|---|
| **HC26060-KE02** | Kinetis KE02 module (MKE02Z64 — 40 MHz, 64 KB flash, 4 KB RAM, 256 B EEPROM) |
| **HC26060-KE04** | Kinetis KE04 module (MKE04Z64 — 48 MHz, 64 KB flash, 8 KB RAM) |

**In the box:** module (assembled, headers loose) · 2× 1x20 headers · 1× 1x4 right-angle SWD header · quick-start card · ESD bag.

**MCU references:** NXP [KE02 data sheet](https://www.nxp.com/docs/en/data-sheet/MKE02P64M40SF0.pdf) · NXP [KE04 data sheet](https://www.nxp.com/docs/en/data-sheet/MKE04P80M48SF0.pdf)

See also: [Quick-Start](index.md) · [Pinout](pinout.md) · [FAQ](faq.md)
