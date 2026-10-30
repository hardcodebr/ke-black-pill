/*
 * Bare-metal LED blink + UART0 115200 for NXP KE02 (MKE02Z16/Z32/Z64, 44-pin LQFP).
 *
 * Written for the HC26060 Kinetis target board (LQFP-44, takes KE02 or KE04) to be
 * loaded with any SWD probe that supports Kinetis KE. No SDK, no CMSIS: every
 * register below is hand-written from the KE02 reference manual and cited.
 *
 * SOURCES (both read for this file; section numbers are the M20 RM unless marked M40):
 *   [RM]  MKE02Z64M20SF0RM Rev. 3, July 2013 — KE02 20 MHz parts (MKE02Z16/32/64VLD2).
 *   [M40] MKE02P64M40SF0RM Rev. 3, Nov. 2014 — KE02 40 MHz parts (MKE02Z64VLD4, the part
 *         the HC26060 board was designed around). Every register used here has the same
 *         address, reset value and layout in both; differences are noted where they exist.
 *   [DS]  MKE02P64M20SF0 Rev. 7 — data sheet, IRC accuracy.
 *
 * ⚠ KE02 IS NOT KL25/K64. No PORTx_PCR mux registers (pin function is chosen by
 * enabling the peripheral, plus SIM_PINSEL), no SIM_SCGC5 port gates, a WDOG with an
 * unlock sequence instead of SIM_COPC, an ICS instead of an MCG, and a Flash
 * Configuration Field whose FSEC byte is at 0x40E, NOT 0x40C. Nothing from
 * ../kl25z_blink_uart_115200 transfers except the shape of the program.
 *
 * Memory (built for the SMALLEST part so one image fits Z16, Z32 and Z64):
 *   Flash 16 KB @ 0x00000000                       [RM 3.7.1.1]
 *   SRAM   2 KB = SRAM_L 0x1FFFFE00..0x1FFFFFFF + SRAM_U 0x20000000..0x200005FF
 *          (RM 3.7.3: SRAM_L = 1/4 below 0x2000_0000, SRAM_U = 3/4 above; Table 3-25:
 *          MKE02Z16VLD2 = 2 KB). Initial SP = 0x20000600.
 *   Core: Cortex-M0+ (no hardware divide — see div10()).
 */

#include <stdint.h>

#ifndef BUILD_ID
#define BUILD_ID "unknown"
#endif

/* ── LED: one #define, overridden by `LED=PTxN ./build.sh` ───────────────────────────
 * Default PTA6 = LQFP-44 pin 26 [RM 10.2.1 pinout table], HC26060 user LED D3:
 * pin -> R7 1k -> LED -> GND, i.e. ACTIVE HIGH (hardcode_hc26060_kinetis_target,
 * docs/HC26060_R7_swap_list_2026-10-09.md). LED_PORT: 0=PTA 1=PTB ... 7=PTH. */
#ifndef LED_PORT
#define LED_PORT 0      /* PTA */
#endif
#ifndef LED_PIN
#define LED_PIN 6       /* PTA6 */
#endif
#ifndef LED_ACTIVE_LOW
#define LED_ACTIVE_LOW 0
#endif
#ifndef LED_NAME
#define LED_NAME "PTA6"
#endif
#if LED_PORT < 0 || LED_PORT > 7 || LED_PIN < 0 || LED_PIN > 7
#error "LED must be PTA0..PTH7"
#endif

/* ── WDOG — RM 16.2 memory map, base 0x4005_2000. Enabled out of reset (CS1 reset 80h). */
#define WDOG_CS1    (*(volatile uint8_t  *)0x40052000u) /* RM 16.2.1: EN b7, INT b6, UPDATE b5, DBG b2 */
#define WDOG_CS2    (*(volatile uint8_t  *)0x40052001u) /* RM 16.2.2: reset 01h = CLK 01 (1 kHz LPO) */
#define WDOG_CNT16  (*(volatile uint16_t *)0x40052002u) /* RM 16.2.3/4: CNTH @+2, CNTL @+3 */
#define WDOG_TOVAL16 (*(volatile uint16_t *)0x40052004u) /* RM 16.2.5/6: TOVALH @+4, TOVALL @+5 */
/* Unlock keys as NXP's own code writes them: one 16-bit store of 0x20C5 then 0x28D9
 * (KE SDK WDOG_UPDATE_KEY1/2, same as tools/ke04_blink_uart). A little-endian halfword
 * store puts 0xC5 in CNTH (+2) and 0x20 in CNTL (+3), i.e. CNTH:CNTL = C5:20 as the RM's
 * transposed-byte NOTE requires.
 * ⚠ The first build wrote 0xC520 / 0xD928 here (bytes reversed). Bench note 2026-10-15:
 * flashed + verified, then SIM_SRSID read 0x...0020 = WDOG reset (it read 0x...0200 =
 * LOCKUP while blank) - the watchdog was never unlocked and kept resetting the part. */
#define WDOG_UNLOCK1_LE 0x20C5u
#define WDOG_UNLOCK2_LE 0x28D9u
#define WDOG_CS1_UPDATE (1u << 5)
#define WDOG_CS2_CLK_LPO 0x01u

/* ── SIM — RM 12.2, base 0x4004_8000 ───────────────────────────────────────────────── */
#define SIM_PINSEL  (*(volatile uint32_t *)0x40048008u) /* RM 12.2.3: reset 0; b7 UART0PS: 0 = RX PTB0 / TX PTB1 */
#define SIM_SCGC    (*(volatile uint32_t *)0x4004800Cu) /* RM 12.2.4: reset 0000_3000h; b20 UART0, b21 UART1 */
#define SIM_BUSDIV  (*(volatile uint32_t *)0x40048018u) /* RM 12.2.7: b0 BUSDIV; POR 0, UNAFFECTED by other resets */
#define SIM_PINSEL_UART0PS (1u << 7)
#define SIM_SCGC_UART0     (1u << 20)
#define SIM_SCGC_UART1     (1u << 21)

/* ── UART0 + UART1 — RM 31.2 memory map: identical layout, bases 0x4006_A000 / 0x4006_B000.
 * The SAME text goes out on both, so a serial monitor can listen on either:
 *    UART0 TX = PTB1 (LQFP-44 pin 23) -> CH340 (USB serial)        RX PTB0 pin 24
 *    UART1 TX = PTC7 (LQFP-44 pin 36) -> header J4.13              RX PTC6 pin 37, J4.12
 * ⭐ UART1 NEEDS NO PIN SELECT ON KE02. SIM_PINSEL (RM 12.2.3) has a UART0PS bit only — no
 *    UART1PS/UART2PS in either the M20 or the M40 RM — and UART1_TX/RX exist ONLY on
 *    PTC7/PTC6 (RM 10.2.1 pinout table, 44 LQFP column 36/37). Ungating it in SIM_SCGC and
 *    setting TE is all it takes. */
#define UART0_BASE  0x4006A000u
#define UART1_BASE  0x4006B000u
#define UART_BDH(b) (*(volatile uint8_t *)((b) + 0u))  /* RM 31.2.1: SBR[12:8] in b4:0, reset 00h */
#define UART_BDL(b) (*(volatile uint8_t *)((b) + 1u))  /* RM 31.2.2: SBR[7:0], reset 04h */
#define UART_C1(b)  (*(volatile uint8_t *)((b) + 2u))  /* RM 31.2.3: 0 = 8N1 */
#define UART_C2(b)  (*(volatile uint8_t *)((b) + 3u))  /* RM 31.2.4: TE b3, RE b2 */
#define UART_S1(b)  (*(volatile uint8_t *)((b) + 4u))  /* RM 31.2.5: TDRE b7, reset C0h */
#define UART_C3(b)  (*(volatile uint8_t *)((b) + 6u))  /* RM 31.2.7: TXINV etc., 0 = normal */
#define UART_D(b)   (*(volatile uint8_t *)((b) + 7u))  /* RM 31.2.8 */
#define C2_TE       (1u << 3)
#define S1_TDRE     (1u << 7)

/* ── GPIO — RM 32.2. GPIOA (0x400F_F000) carries PTA..PTD as bits 0-7/8-15/16-23/24-31;
 *    GPIOB (0x400F_F040) carries PTE..PTH the same way (RM 32.1 / 32.2 memory map). ── */
#define GPIO_BASE   (LED_PORT < 4 ? 0x400FF000u : 0x400FF040u)
#define GPIO_PSOR   (*(volatile uint32_t *)(GPIO_BASE + 0x04u)) /* RM 32.2.3 */
#define GPIO_PCOR   (*(volatile uint32_t *)(GPIO_BASE + 0x08u)) /* RM 32.2.4 */
#define GPIO_PDDR   (*(volatile uint32_t *)(GPIO_BASE + 0x14u)) /* RM 32.2.7: 1 = output */
#define LED_MASK    (1u << (((LED_PORT) % 4) * 8 + (LED_PIN)))

/* ── Buttons (HC26060 schematic, owner 2026-10-15: "2 buttons, put a message in the serial").
 *  SW2 USER  = PTD4 to GND, NO external pull-up -> internal pull-up PORT_PUEL bit 28.
 *  SW1 RESET = PTA5/RESET_b: it cannot be read as a GPIO (it IS the reset pin), so the
 *              boot banner prints SIM_SRSID's reset cause - a SW1 press shows "PIN (SW1)".
 *  Addresses from NXP's MKE02Z4.h: PORT 0x4004_9000 {IOFLT +0, PUEL +4, PUEH +8, HDRVE +C};
 *  GPIOA PDIR +0x10, PIDR +0x18 (reset all 1 = input buffers OFF - must be cleared). ── */
#define PORT_PUEL   (*(volatile uint32_t *)0x40049004u)
#define GPIOA_PDIR  (*(volatile uint32_t *)0x400FF010u)
#define GPIOA_PIDR  (*(volatile uint32_t *)0x400FF018u)
#define SW2_MASK    (1u << (3 * 8 + 4))   /* PTD4 = GPIOA bit 28 (PTD = bits 24..31) */
#define SIM_SRSID   (*(volatile uint32_t *)0x40048000u)

/* ── SysTick (ARMv6-M) — RM 3.3.1 Table 3-5: SysTick present; CLKSOURCE=1 = core clock ──────────── */
#define SYST_CSR    (*(volatile uint32_t *)0xE000E010u)
#define SYST_RVR    (*(volatile uint32_t *)0xE000E014u)
#define SYST_CVR    (*(volatile uint32_t *)0xE000E018u)
#define SYST_CSR_ENABLE    (1u << 0)
#define SYST_CSR_CLKSOURCE (1u << 2)
#define SYST_CSR_COUNTFLAG (1u << 16)

/*
 * ── CLOCK: RESET-DEFAULT FEI, NOT CHANGED. Deliberately. ─────────────────────────────
 *   ICS_C1 reset 04h: CLKS=00 FLL, IREFS=1 internal ref          [RM 20.3.1]
 *   ICS_C2 reset 20h: BDIV=001 = divide by 2                     [RM 20.3.2]
 *   FLL = 1024 x IRC; IRC factory-trimmed to 31.25 kHz            [RM 20.4.1.1, DS fint_ft]
 *     => ICSFLLCLK = 32 MHz, ICSOUTCLK = core = 16 MHz            [RM 5.4 Table 5-2, 5-4]
 *   SIM_BUSDIV = 0 => bus = core = 16 MHz                         [RM 12.2.7]
 * Same on the 40 MHz parts [M40 5.5 Table 5-4: BDIV=1 -> 16-20 MHz].
 *
 * WHY NOT FASTER / RE-TRIMMED: the station's KE02 driver (firmware/main/kinetis_ke.c
 * clock_check) only accepts ICS_C1=FEI, ICS_C2 BDIV/2, the CHARACTERIZED trim, and
 * SIM_BUSDIV == 0. ICS trim is NOT reloaded on a reset taken in debug mode [RM 20.3.3/4],
 * and SIM_BUSDIV is "unaffected by reset" except POR [RM 12.2.7]. So an image that
 * re-trims the IRC or sets BUSDIV would make the station REFUSE the next flash until the
 * board is power-cycled. The M20 parts also cap core at 20 MHz [RM 5.4 Table 5-3], so
 * 32 MHz is not available without re-trimming either.
 * We still WRITE SIM_BUSDIV = 0 below: it is the POR value, and it undoes a BUSDIV left
 * at 1 by some earlier firmware across a pin reset (which would halve the baud rate).
 */
#define BUS_HZ 16000000u

/*
 * ── BAUD ─────────────────────────────────────────────────────────────────────────────
 * Baud = bus / (16 x SBR), SBR integer 1..8191, NO fractional divider   [RM 31.3.1 Fig 31-35]
 *   115200: SBR = round(16e6 / 1843200) = 9  -> 111,111 Bd = -3.55 %   ⚠ MARGINAL
 *    57600: SBR 17 -> 58,824 Bd = +2.12 %
 *    38400: SBR 26 -> 38,462 Bd = +0.16 %
 * RM 31.3.1: allowed mismatch "about ±4.5 percent for 8-bit data format". The IRC adds
 * ±0.5 % at 25 °C, -1..+0.5 % over temperature [DS fint_ft/fint_t]. So 115200 has
 * ~1 % margin at the bench and ~0.5 % worst case. Rebuild with BAUD=38400 if lines garble.
 */
#ifndef BAUD
#define BAUD 115200
#endif
#define UART_SBR ((BUS_HZ + 8u * (BAUD)) / (16u * (BAUD)))   /* rounded */
#if UART_SBR < 1 || UART_SBR > 8191
#error "BAUD out of range for a 16 MHz bus"
#endif

#define STR_(x) #x
#define STR(x) STR_(x)

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;

void reset_handler(void);
void default_handler(void);

/* Cortex-M0+ vector table: SP + 15 system exceptions [RM 3.3.2.3 vector table, offsets 0x00-0x3C].
 * External IRQs are never enabled, so their slots are left out; the linker pads to 0x400. */
__attribute__((section(".isr_vector"), used))
void (*const vector_table[16])(void) = {
    (void (*)(void))(&_estack), /* 0x00 Initial SP (0x20000600)  */
    reset_handler,              /* 0x04 Reset                    */
    default_handler,            /* 0x08 NMI (PTB4, 10k pull-up)  */
    default_handler,            /* 0x0C HardFault                */
    0, 0, 0, 0, 0, 0, 0,        /* 0x10-0x28 reserved on ARMv6-M */
    default_handler,            /* 0x2C SVCall                   */
    0, 0,                       /* 0x30-0x34 reserved            */
    default_handler,            /* 0x38 PendSV                   */
    default_handler,            /* 0x3C SysTick (not enabled)    */
};

/*
 * ── FLASH CONFIGURATION FIELD @ 0x400-0x40F — RM 18.3.6 Table 18-6 ──────────────────
 * ⛔ A SECURED KE02 IS A ONE-WAY BENCH RISK. build.sh refuses any .bin whose 16 bytes here
 *    differ from exactly the values below.
 *   0x400-0x407 backdoor comparison key  = FF x 8  (unused; KEYEN below disables it)
 *   0x408-0x40B reserved                 = FF x 4  ("must be programmed to 0xFF")
 *   0x40C EEPROT                         = FF      (DPOPEN=1: no EEPROM protection)
 *   0x40D FPROT                          = FF      (FPOPEN=1, FPHDIS=1, FPLDIS=1: no flash protection, RM 18.3.6)
 *   0x40E FSEC                           = FE      KEYEN[7:6]=11 backdoor DISABLED,
 *                                                  reserved[5:2]=1111, SEC[1:0]=10 UNSECURED (RM 18.4.2)
 *   0x40F FOPT                           = FF      (erased; no option set)
 * KE has NO MEEN field — mass erase over MDM-AP is always possible. The station's
 * kinetis_ke_fcf_safe() accepts exactly this pattern and nothing else.
 */
__attribute__((section(".flash_config"), used))
const uint8_t flash_config[16] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,  /* backdoor key (disabled) */
    0xFF, 0xFF, 0xFF, 0xFF,                          /* reserved               */
    0xFF,                                            /* 0x40C EEPROT           */
    0xFF,                                            /* 0x40D FPROT            */
    0xFE,                                            /* 0x40E FSEC unsecured   */
    0xFF,                                            /* 0x40F FOPT             */
};

static void led_set(int on)
{
    if (on != LED_ACTIVE_LOW) {
        GPIO_PSOR = LED_MASK;
    } else {
        GPIO_PCOR = LED_MASK;
    }
}

/* Busy-wait in whole milliseconds on SysTick (core clock = 16 MHz, 24-bit reload). */
static void delay_ms(uint32_t ms)
{
    SYST_RVR = BUS_HZ / 1000u - 1u;   /* core == bus here (BUSDIV = 0) */
    SYST_CVR = 0;
    SYST_CSR = SYST_CSR_CLKSOURCE | SYST_CSR_ENABLE;
    while (ms--) {
        while (!(SYST_CSR & SYST_CSR_COUNTFLAG)) {
        }
    }
    SYST_CSR = 0;
}

static void uart_init_one(uint32_t b)
{
    UART_C2(b) = 0;                    /* TX/RX off while the divisor is written */
    UART_C1(b) = 0;                    /* 8N1 */
    UART_C3(b) = 0;
    UART_BDH(b) = (uint8_t)((UART_SBR >> 8) & 0x1Fu);
    UART_BDL(b) = (uint8_t)(UART_SBR & 0xFFu);
    /* TE last. Enabling the transmitter is what hands the TX pin to the UART — KE02 has no
     * PCR mux; an enabled peripheral takes priority over GPIO [RM 10.2.1 note + Table 10-1].
     * RE stays OFF: the RX pins (PTB0, PTC6) stay hi-Z inputs, so a host TX can idle on them. */
    UART_C2(b) = C2_TE;
}

static void uart_init(void)
{
    SIM_PINSEL &= ~SIM_PINSEL_UART0PS; /* UART0 on PTB0 (RX) / PTB1 (TX) — the reset default, written for clarity */
    SIM_SCGC |= SIM_SCGC_UART0 | SIM_SCGC_UART1; /* ungate both (reset: gated) */
    uart_init_one(UART0_BASE);
    uart_init_one(UART1_BASE);
}

/* One byte to BOTH UARTs. Same baud, so they drain in lock-step; TDRE polled on each. */
static void uart_putc(char c)
{
    while (!(UART_S1(UART0_BASE) & S1_TDRE)) {
    }
    UART_D(UART0_BASE) = (uint8_t)c;
    while (!(UART_S1(UART1_BASE) & S1_TDRE)) {
    }
    UART_D(UART1_BASE) = (uint8_t)c;
}

static void uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n') {
            uart_putc('\r');
        }
        uart_putc(*s++);
    }
}

/* Cortex-M0+ has no divide instruction and the build is -nostdlib (no __aeabi_uidiv):
 * divide by ten with shifts/adds, corrected once so it is exact over all of uint32_t. */
static uint32_t div10(uint32_t n, uint32_t *rem)
{
    uint32_t q = (n >> 1) + (n >> 2);
    q += q >> 4;
    q += q >> 8;
    q += q >> 16;
    q >>= 3;
    uint32_t r = n - (((q << 2) + q) << 1);
    if (r > 9u) {
        q += 1u;
        r -= 10u;
    }
    *rem = r;
    return q;
}

static void uart_putu32(uint32_t v)
{
    char buf[10];
    int n = 0;

    do {
        uint32_t r;
        v = div10(v, &r);
        buf[n++] = (char)('0' + r);
    } while (v && n < (int)sizeof(buf));
    while (n--) {
        uart_putc(buf[n]);
    }
}

int main(void)
{
    uint32_t count = 0;

    led_set(0);
    GPIO_PDDR |= LED_MASK;             /* output (PIDR left as reset: input buffer off) */

    uart_init();
    uart_puts("\nKE02 blink+uart " BUILD_ID "\n");
    uart_puts("UART0 TX=PTB1 + UART1 TX=PTC7, " STR(BAUD) " 8N1, bus 16 MHz FEI, LED=" LED_NAME "\n");

    /* SW2: input with pull-up (PDDR bit stays 0 = input). */
    PORT_PUEL |= SW2_MASK;
    GPIOA_PIDR &= ~SW2_MASK;

    /* SW1 test: why did we boot? SIM_SRSID bits [MKE02Z4.h SIM_SRSID_*_MASK]. */
    const uint32_t why = SIM_SRSID;
    uart_puts("reset:");
    if (why & 0x80u)   uart_puts(" POR");
    if (why & 0x40u)   uart_puts(" PIN (SW1)");
    if (why & 0x20u)   uart_puts(" WDOG");
    if (why & 0x200u)  uart_puts(" LOCKUP");
    if (why & 0x400u)  uart_puts(" SW");
    if (why & 0x800u)  uart_puts(" MDMAP (debugger/station)");
    if (why & 0x2u)    uart_puts(" LVD");
    if (why & 0x4u)    uart_puts(" LOC");
    uart_puts("\n");

    /* 10 ms tick: LED toggles every 50 ticks (~1 Hz, one "blink N" line per blink);
     * SW2 sampled every tick, a change must hold 3 ticks (30 ms debounce). */
    uint32_t presses = 0, tick = 0;
    int pressed = 0, stable = 0;
    for (;;) {
        if (tick == 0u) {
            led_set(1);
            uart_puts("blink ");
            uart_putu32(++count);
            uart_putc('\n');
        } else if (tick == 50u) {
            led_set(0);
        }
        const int now = (GPIOA_PDIR & SW2_MASK) == 0u;   /* low = pressed */
        if (now != pressed) {
            if (++stable >= 3) {
                pressed = now; stable = 0;
                if (pressed) {
                    uart_puts("button SW2 pressed ");
                    uart_putu32(++presses);
                    uart_putc('\n');
                } else {
                    uart_puts("button SW2 released\n");
                }
            }
        } else {
            stable = 0;
        }
        delay_ms(10);
        if (++tick == 100u) tick = 0;   /* no % : M0+ has no divider, no libgcc linked */
    }
}

void reset_handler(void)
{
    /* 1. WATCHDOG FIRST. It is enabled out of reset with a ~4 ms timeout [RM 16.3.3
     *    Table 16-10 note 1]. Unlock (RM 16.3.2.2), then reconfigure within 128 bus clocks:
     *    timeout first, then CS2, then CS1 last (RM 16.3.2: the new configuration takes
     *    effect once all registers except CNT are written). CS1 = UPDATE only: EN=0
     *    (disabled), DBG=0, and UPDATE=1 so later code could reconfigure it again. */
    __asm__ volatile("cpsid i");
    WDOG_CNT16 = WDOG_UNLOCK1_LE;
    WDOG_CNT16 = WDOG_UNLOCK2_LE;
    WDOG_TOVAL16 = 0xFFFFu;
    WDOG_CS2 = WDOG_CS2_CLK_LPO;
    WDOG_CS1 = WDOG_CS1_UPDATE;

    /* 2. Bus divider back to its POR value (see the CLOCK block). ICS is not touched. */
    SIM_BUSDIV = 0;

    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata;) {
        *dst++ = *src++;
    }
    for (uint32_t *dst = &_sbss; dst < &_ebss;) {
        *dst++ = 0;
    }
    main();
    for (;;) {
    }
}

void default_handler(void)
{
    for (;;) {
    }
}
