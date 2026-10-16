# Pinout — Kinetis KE02 / KE04 Module (HC26060)

> 🏠 [HardCode — all products](https://github.com/hardcodebr) · 🛒 [Shop](https://lectronz.com/stores/hardcode-electronics) · 🌐 [hardcode.com.br](https://hardcode.com.br)

<!-- ⟨TODO: pinout graphic docs/img/pinout.png (Waveshare style, separate KE02 / KE04 versions)⟩ -->
![pinout](img/pinout.png)

- **Pin 1** of both long headers is at the **USB-C end**. Pin names are printed on the board
  next to each pin (`B1`, `A6`, `5V`, `G`, `3V3`, `RST` …). `B1` = port **PTB1**, and so on.
- Seen from the top with USB-C on the left: **J4** is the upper row, **J3** the lower row.
  <!-- CONFIRM on a physical board: J4 (3V3·G·RST…) = upper row, J3 (5V·G·3V3…) = lower row, USB-C left, top view -->
- Every pin also works as a **GPIO**, and most as a keyboard-interrupt (KBI) input.
- The pins marked **3V3** carry the MCU supply. If you feed 5 V into one, they are all at 5 V.
- **I/O voltage = MCU supply.** At 3.3 V, don't apply 5 V to any I/O pin.

## Header J4 (1x20)

In pin order as on the board (pin 1 → 20):

| Pin | Name | Main functions | Notes |
|---|---|---|---|
| 1 | **3V3** | MCU supply | in or out — see [Datasheet → Power](datasheet.md#power) |
| 2 | **G** | GND | |
| 3 | **RST** | RESET (PTA5) | RESET button; connect your probe's RESET here |
| 4 | H2 | PTH2 · FTM1_CH0 · BUSOUT | |
| 5 | E7 | PTE7 · FTM1_CH1 | |
| 6 | D0 | PTD0 · FTM2_CH2 · SPI1_SCK | high-drive |
| 7 | D1 | PTD1 · FTM2_CH3 · SPI1_MOSI | high-drive |
| 8 | C5 | PTC5 · FTM1_CH1 · RTC clock out | |
| 9 | E0 | PTE0 · SPI0_SCK · *KE04: I2C1_SDA* | high-drive |
| 10 | E1 | PTE1 · SPI0_MOSI · *KE04: I2C1_SCL* | high-drive |
| 11 | E2 | PTE2 · SPI0_MISO · *KE04: PWT_IN0* | |
| 12 | C6 | PTC6 · UART1_RX | |
| 13 | C7 | PTC7 · UART1_TX | |
| 14 | A0 | PTA0 · FTM0_CH0 · ACMP0_IN0 · ADC0_SE0 | |
| 15 | A1 | PTA1 · FTM0_CH1 · ACMP0_IN1 · ADC0_SE1 | |
| 16 | A2 | PTA2 · I2C0_SDA · UART0_RX (alt) | true open-drain output |
| 17 | A3 | PTA3 · I2C0_SCL · UART0_TX (alt) | true open-drain output |
| 18 | D2 | PTD2 · SPI1_MISO | |
| 19 | D3 | PTD3 · SPI1_PCS0 | |
| 20 | D4 | PTD4 | **USER button** (to GND) — enable the internal pull-up |

## Header J3 (1x20)

In pin order as on the board (pin 1 → 20):

| Pin | Name | Main functions | Notes |
|---|---|---|---|
| 1 | **5V** | USB 5 V out / 5 V in to the regulator | not regulated |
| 2 | **G** | GND | |
| 3 | **3V3** | MCU supply | same rail as J4.1 |
| 4 | B7 | PTB7 · I2C0_SCL · EXTAL | crystal pin — free (no crystal fitted) |
| 5 | B6 | PTB6 · I2C0_SDA · XTAL | crystal pin — free |
| 6 | B5 | PTB5 · FTM2_CH5 · SPI0_PCS0 · ACMP1_OUT | high-drive |
| 7 | B4 | PTB4 · **NMI** · FTM2_CH4 · SPI0_MISO · ACMP1_IN2 | high-drive; pulled up on board — **don't hold low at power-up** |
| 8 | C3 | PTC3 · FTM2_CH3 · ADC0_SE11 | |
| 9 | C2 | PTC2 · FTM2_CH2 · ADC0_SE10 | |
| 10 | D7 | PTD7 · UART2_TX | |
| 11 | D6 | PTD6 · UART2_RX | |
| 12 | D5 | PTD5 · *KE04: PWT_IN0* | |
| 13 | C1 | PTC1 · FTM2_CH1 · ADC0_SE9 | |
| 14 | C0 | PTC0 · FTM2_CH0 · ADC0_SE8 | |
| 15 | B3 | PTB3 · SPI0_MOSI · FTM0_CH1 · ADC0_SE7 | |
| 16 | B2 | PTB2 · SPI0_SCK · FTM0_CH0 · ADC0_SE6 | |
| 17 | B1 | PTB1 · **UART0_TX** · ADC0_SE5 | also to the on-board USB-serial |
| 18 | B0 | PTB0 · **UART0_RX** · ADC0_SE4 · *KE04: PWT_IN1* | also from the on-board USB-serial |
| 19 | A7 | PTA7 · FTM2_FLT2 · ACMP1_IN1 · ADC0_SE3 | |
| 20 | A6 | PTA6 · FTM2_FLT1 · ACMP1_IN0 · ADC0_SE2 | **user LED** (red, active high) |

*KE04-only functions in italics.* The KBI numbering differs between KE02 and KE04. Full
alternate-function list: NXP data sheet, "Signal multiplexing and pin assignments"
([KE02](https://www.nxp.com/docs/en/data-sheet/MKE02P64M40SF0.pdf) ·
[KE04](https://www.nxp.com/docs/en/data-sheet/MKE04P80M48SF0.pdf)).

**UART0 / USB-serial.** `B1`/`B0` go to the header **and** to the on-board USB-serial. Use one
serial source at a time. An adapter on the header pins overrides the USB-serial.

## SWD header (J1)

1x4 right-angle header at the far end of the board. Pin 1 = square pad. Label on the board:
`3V3 DIO CLK GND`.

<!-- CONFIRM on a physical board: J1 order 3V3 · DIO · CLK · GND, pin 1 square pad, continuity J1.1 → 3V3 -->

| Pin | Label | Signal |
|---|---|---|
| 1 | **3V3** | MCU supply — probe target-voltage reference, or 2.7–5.5 V in |
| 2 | **DIO** | SWDIO (PTA4) — pulled up on board |
| 3 | **CLK** | SWCLK (PTC4) |
| 4 | **GND** | GND |

- **RESET is not on J1** — it is on **J4 pin 3 (RST)**.
- **Check the labels before you connect a probe.** Use this table, not a cable made for another board.
  ⟨CONFIRM: if the rev A order turns out to differ from the usual Black Pill SWD order, add: "The
  SWD order on rev A differs from Black Pill boards."⟩
- There is no SWCLK pull-down on the board. Most probes drive SWCLK actively, so this is fine.
  If your probe needs one (NXP recommends it), add a pull-down from SWCLK to GND on your side.

## USB-C

| Function | Detail |
|---|---|
| Power | 5 V in from a USB host or charger |
| Data | to the on-board USB-serial only (UART0) — the KE02/KE04 has no USB |
| Cable | any USB-C cable **with data lines** (charge-only cables give power but no serial port) |

## LEDs and buttons

| Item | Pin | Behaviour |
|---|---|---|
| Power LED (green) | — | On when the MCU supply is present. Dim at 3 V, brighter at 5 V. |
| User LED (red) | `A6` (PTA6) | Active **high** — drive PTA6 high to turn it on |
| RESET button | `RST` (PTA5) | Resets the MCU; pull-up on board |
| USER button | `D4` (PTD4) | Connects PTD4 to GND when pressed — enable the internal pull-up |
