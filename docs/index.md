# Quick-Start — KE Black Pill (HC26060)

> 🏠 [HardCode — all products](https://github.com/hardcodebr) · 🛒 [Shop](https://lectronz.com/stores/hardcode-electronics) · 🌐 [hardcode.tools](https://hardcode.tools)

From the bag to a running program in four steps. You need a USB-C cable and an **SWD probe**
(the module has no built-in debugger).

## 1. Solder and power up
- Solder the two **1x20 headers** (and the **1x4 SWD header** if you will flash it). Put the
  module in a breadboard.
- Plug in **USB-C**. The **green power LED** turns on.
- From USB the MCU runs at about 3 V (on-board regulator). To run it at **5 V**, feed 2.7–5.5 V
  into a **3V3** pin instead — see [Datasheet → Power](datasheet.md#power).
  <!-- ⟨CONFIRM: measure VDD from USB on 2 boards (expected 3.0–3.1 V)⟩ -->

## 2. Open the serial console
- The USB-C port carries an **on-board USB-serial**, wired to the MCU's **UART0**
  (pins `B1` = TX, `B0` = RX).
- A new serial port appears: **COMx** on Windows, **/dev/ttyUSB\*** on Linux, **/dev/cu.\*** on macOS.
  Current Windows, macOS and Linux versions usually include the driver. If no port appears,
  install the USB-to-serial driver for your system.
  <!-- ⟨CONFIRM: test the driver on a clean Windows PC and on macOS⟩ -->
- Open a terminal at your firmware's baud rate. Our examples use **115200 8N1**.
- Use **one serial source at a time** on UART0: either the USB-serial, or your own adapter on the
  `B1`/`B0` header pins — not both.

## 3. Your first program — blink + serial echo
The example firmware ⟨TODO: link to the examples folder / release .bin⟩:
- **Blink** — toggles the red **user LED** on `A6` (PTA6, active high) and prints a counter on UART0.
- **Serial echo** — sends back every character you type in the console (UART0 ↔ USB-serial).
  ⟨TODO: example to be written⟩
- Press **USER** (`D4`, PTD4 to GND) and **RESET** to see the messages change.

Writing your own? Three things matter on Kinetis E:
- **Clock:** no crystal is fitted — use the internal clock. Set the core to full speed
  (40 MHz KE02 / 48 MHz KE04) so 115200 baud is accurate; at the reset-default clock the baud
  error is a few percent.
- **Button:** enable the internal **pull-up** on PTD4 for the USER button.
- **Security byte:** make sure your image holds **0xFE at address 0x40E** (see
  [step 5](#5-safety-flash-security-and-mass-erase)). NXP's startup code does this for you.

## 4. Flash over SWD
Wire the probe to the **SWD header J1** (see **[Pinout](pinout.md#swd-header-j1)**):

| J1 pin | Signal | Probe |
|---|---|---|
| 1 | 3V3 | VTref / target voltage |
| 2 | DIO | SWDIO |
| 3 | CLK | SWCLK |
| 4 | GND | GND |

<!-- CONFIRM on a physical board: J1 order 3V3 · DIO · CLK · GND (pin 1 = square pad), continuity J1.1 → 3V3 -->

- **RESET is not on J1.** If your probe uses a reset line, connect it to the **RST** pin
  (header J4, pin 3).
- Power the module from USB, or from the probe's target supply on J1 pin 1 (2.7–5.5 V).

Kinetis E has its **own flash controller** — tools set up for "Kinetis K / KL" will not work.
Always select the **exact device** (MKE02Z64 or MKE04Z64) in your tool.

| Probe / tool | How | Status |
|---|---|---|
| **HardCode Flash Station** | Kinetis KE job, J1 + RST wiring | **In development** ⟨CONFIRM: change after the station bench acceptance⟩ |
| **SEGGER J-Link** | Device `MKE02Z64xxx4` or `MKE04Z64xxx4` in J-Flash, J-Link Commander or your IDE ([SEGGER device list](https://www.segger.com/supported-devices/nxp/kinetis-ke/)) | Listed by SEGGER; not tested by HardCode yet ⟨CONFIRM⟩ |
| **CMSIS-DAP probe + OpenOCD** | `-f interface/cmsis-dap.cfg -f target/ke0x.cfg` (OpenOCD's Kinetis KE0x target + `kinetis_ke` flash driver) | Not tested by HardCode yet ⟨CONFIRM⟩ |
| **CMSIS-DAP probe + pyOCD** | No built-in KE02/KE04 target — install NXP's device pack first: `pyocd pack install mke04z64vld4` (or `mke02z64vld4`), then `pyocd flash -t mke04z64vld4 app.bin` ⟨CONFIRM: exact target name from `pyocd pack find`⟩ | Not tested by HardCode yet ⟨CONFIRM⟩ |

**Toolchains**
- **NXP MCUXpresso IDE + MCUXpresso SDK** — the SDK and device packs cover KE02 and KE04 (startup
  code, drivers, flash algorithms). Build the SDK for the exact part at
  [mcuxpresso.nxp.com](https://mcuxpresso.nxp.com).
- **Arm GNU Toolchain (arm-none-eabi-gcc)** — use the MCUXpresso SDK's GCC build files, then flash
  the `.bin`/`.elf` with one of the probes above.
- NXP device packs (CMSIS-Packs for Keil/pyOCD): `NXP.MKE02Z4_DFP` (KE02) and `NXP.MKE04Z1284_DFP`
  (KE04 Z64/Z128) from the [NXP CMSIS-Pack repository](https://mcuxpresso.nxp.com/cmsis_pack/repo/).

A **blank chip keeps resetting itself** (there is no valid program). Choose "connect under reset"
in your tool if it can't attach.

## 5. Safety: flash security and mass erase
Read this before you flash your own images.

- Kinetis E has a **security byte** at flash address **0x40E**. **0xFE = unsecured.** An **erased**
  value (0xFF) counts as **secured**. NXP's startup code writes the right value — if you build your
  own image or linker script, check it.
- If the chip becomes **secured**, a debugger can no longer read or write the flash. A **mass erase**
  over SWD (J-Link Commander `unlock Kinetis`, OpenOCD `kinetis_ke mdm mass_erase`, pyOCD `erase --chip`) unlocks it
  again. It **erases the whole chip**. ⟨CONFIRM: mass erase not bench-tested on this module yet⟩
- **Don't program the backdoor key or the flash protection bytes** unless you know you need them.
- Firmware can turn the SWD and RESET pins into GPIO. SWD comes back after any reset; RESET comes
  back only after a power cycle. To recover: hold **RESET** low, power-cycle, then connect the probe
  "under reset".

Trouble? See the **[FAQ](faq.md)**.

## 💬 Feedback & suggestions
Ideas, questions, or something you'd like to see? Open a discussion — we read every one:
**https://github.com/hardcodebr/ke-black-pill/discussions**

## 🛠️ Custom designs
Need a custom board or a tweak to this one? We do custom design work — **support@hardcode.tools**
