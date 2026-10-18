# FAQ / Troubleshooting — HC26060

> 🏠 [HardCode — all products](https://github.com/hardcodebr) · 🛒 [Shop](https://lectronz.com/stores/hardcode-electronics) · 🌐 [hardcode.com.br](https://hardcode.com.br)

**No serial port appears.**
Use a USB-C cable **with data lines** — charge-only cables light the power LED but give no port.
If the cable is fine, install the USB-to-serial driver for your OS, and try another USB port.
The green LED must be on.

**Garbage in the serial console.**
Check the baud rate (our examples use **115200 8N1**) and that only **one** serial source is
connected to UART0 (USB-serial *or* an adapter on `B1`/`B0`). In your own firmware, run the core at
full speed — at the reset-default clock the 115200 baud error is a few percent.

**Garbled serial on the first boot right after flashing with the Flash Station.**
Known issue, being fixed: on the first boot straight after a station flash the clock can run a few
percent slow, so the console shows garbage. Press **RESET** once (or power-cycle) — it then runs
normally. ⟨CONFIRM: keep, reword or drop once the station fix is out⟩

**My probe can't connect over SWD.**
- Check the wiring against the **J1 labels** (`3V3 DIO CLK GND`) — see [Pinout](pinout.md#swd-header-j1).
- The board must be powered (USB-C, or the probe's target supply on J1 pin 1).
- Select the **exact device** (MKE02Z64 / MKE04Z64). Kinetis E has its own flash controller;
  "Kinetis K / KL" settings won't work.
- A **blank chip** keeps resetting itself. Wire the probe's RESET to **RST** (J4 pin 3) and
  choose "connect under reset".
- Lower the SWD clock. If your probe needs a SWCLK pull-down, add one on your side.

**The debugger says the chip is secured / locked.**
The flash security byte (address **0x40E**) is not **0xFE** — often an image built without NXP's
startup code. Run a **mass erase** over SWD (J-Link Commander `unlock Kinetis`, OpenOCD
`kinetis_ke mdm mass_erase`, pyOCD `erase --chip`). It erases the whole chip and unlocks it, then
flash a correct image. If the firmware also disabled the SWD/RESET pins: hold **RESET** low,
power-cycle, then connect "under reset". ⟨CONFIRM: mass erase not bench-tested on this module yet⟩

**Is it 5 V or 3.3 V?**
Both — on **both SKUs**. The I/O always follow the MCU supply:
- From **USB-C**, the MCU runs at about 3 V. The I/O are **not 5 V tolerant** then.
- Feed **5 V into a 3V3 pin** and the MCU and its I/O run at 5 V.
- The on-board USB-serial is designed for ~3 V. At 5 V, use a 5 V serial adapter on a header UART.

**KE02 or KE04?**
Same board and pinout. The KE04 is faster (48 MHz) with more RAM (8 KB) and a second I2C; the KE02
has 256 B of on-chip EEPROM. See [Datasheet → KE02 vs KE04](datasheet.md#ke02-vs-ke04).

**Does it fit a breadboard?**
Yes. The two rows are 0.6 in apart, like a Black Pill: the module straddles the centre gap of a
standard breadboard. ⟨CONFIRM: free holes per side on a real breadboard⟩ The headers ship loose —
solder them with the pins pointing down, away from the components. ⟨CONFIRM: header side on the
real board⟩

**Does the board have a built-in debugger?**
No. You need an SWD probe (J-Link, a CMSIS-DAP probe, or the HardCode Flash Station once KE support
is released). USB-C is for power and the serial console only.

**Why is RESET not on the SWD header?**
The 4-pin SWD header follows the Black Pill layout (3V3, DIO, CLK, GND). RESET is on **RST**
(J4 pin 3).

**Is it certified?**
It is a development module for lab use. No CE/FCC certification.

More help: support@hardcode.tools
