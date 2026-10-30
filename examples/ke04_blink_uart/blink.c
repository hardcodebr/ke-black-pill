/*
 * Bare-metal LED blink + UART0 AND UART1 115200 for NXP KE04, 44-pin LQFP
 * (MKE04Z64VLD4 or MKE04Z128VLD4 — one image, built for the 64 KB layout).
 * Load with any SWD probe that supports Kinetis KE (J-Link, CMSIS-DAP + OpenOCD/pyOCD).
 *
 * No SDK / no CMSIS — self-contained, direct register access. Same shape as
 * ../kl25z_blink_uart_115200/, but ⚠ KE IS NOT KL: different watchdog, no PORT
 * PCR mux registers, different FCF layout (FSEC at 0x40E, not 0x40C), one GPIO
 * register block per FOUR ports. Nothing below was copied from the KL25 file
 * without re-checking it against the KE04 sources.
 *
 * Sources (the RM itself is not in the tree; see docs/191 "Vendor evidence"):
 *   [DS]  KE04 Sub-Family Data Sheet MKE04P80M48SF0 Rev. 6 — §8.1 pin table,
 *         ICS spec table (fint_ft 37.5 kHz, fdco 40-50 MHz).
 *   [SVD] NXP MKE04Z1284_DFP 14.0.0 MKE04Z1284.xml/.h — register addresses,
 *         reset values, field positions (the RM register chapters in machine form).
 *   [SDK] NXP system_MKE04Z4.c SystemInit() — the watchdog disable sequence.
 *   [191] docs/191_ke02_ke04_driver.md — FCF layout and what the station accepts.
 *
 * ── CLOCK: RESET DEFAULT, NOTHING IS WRITTEN ────────────────────────────────
 * Out of reset the ICS is in FEI [SVD: ICS_C1 reset 0x04, IREFS=1, CLKS=00]:
 *   IRC 37.5 kHz (factory pre-trimmed) [DS fint_ft] x 1280 (FLL) = 48 MHz
 *   ICS_C2 reset 0x20 = BDIV 001 = divide by 2      -> ICSOUTCLK = 24 MHz
 *   SIM_CLKDIV reset 0 = OUTDIV1 /1, OUTDIV2 /1     -> core 24 MHz, bus 24 MHz
 * (The NXP SDK's own SystemCoreClock default for KE04 is 24 000 000.)
 * ⭐ Deliberately untouched: the station's KE driver refuses to program a part
 *   whose SIM dividers or ICS trim differ from reset, and SIM_CLKDIV survives a
 *   non-POR reset [191 "Clock contract"]. An image that raised the clock could
 *   make the NEXT flash of the same board refuse until a power cycle.
 * ⚠ The IRC is trimmed, not crystal-accurate. fdco is spec'd 40-50 MHz [DS] and
 *   drifts ~1.5 % over temperature. The baud error below inherits that.
 *
 * ── BAUD ────────────────────────────────────────────────────────────────────
 *   UART module clock = bus clock = 24 MHz. Baud = bus / (16 x SBR), no
 *   fractional divider on KE UARTs (BDH/BDL only).
 *   SBR = 13 -> 24 000 000 / 208 = 115 384.6 baud = +0.16 %.
 *   If anyone adds clock setup, RECOMPUTE THIS.
 */

#include <stdint.h>

#ifndef BUILD_ID
#define BUILD_ID "dev"
#endif

/* ── LED pin: ONE place. build.sh LED=PTxN sets these three. ───────────────
 * Default PTA6 = the HC26060 user LED (pin -> R7 1k -> D3 -> GND, active HIGH,
 * LQFP-44 pin 26) per hardcode_hc26060_kinetis_target
 * docs/HC26060_R7_swap_list_2026-10-09.md (moved there from PTD0 in that swap).
 * PTA6's reset default is ADC0_SE2, but the ADC is clock-gated and its pin
 * control is not enabled, so PDDR alone makes it a GPIO output.
 * On KE the GPIO blocks are grouped FOUR ports per block
 * [SVD: GPIOA @0x400FF000 = PTA..PTD, GPIOB @0x400FF040 = PTE..PTH,
 * GPIOC @0x400FF080 = PTI], 8 bits per port. */
#ifndef LED_PORT_IDX
#define LED_PORT_IDX 0          /* 0=A 1=B 2=C 3=D 4=E 5=F 6=G 7=H 8=I */
#endif
#ifndef LED_PIN
#define LED_PIN      6          /* 0..7 */
#endif
#ifndef LED_NAME
#define LED_NAME     "PTA6"
#endif

#define GPIO_BASE(port) (0x400FF000u + 0x40u * ((uint32_t)(port) / 4u))
#define LED_MASK        (1u << (((uint32_t)LED_PORT_IDX % 4u) * 8u + (uint32_t)LED_PIN))
#define LED_PSOR (*(volatile uint32_t *)(GPIO_BASE(LED_PORT_IDX) + 0x04u)) /* [SVD] PSOR +0x04 */
#define LED_PCOR (*(volatile uint32_t *)(GPIO_BASE(LED_PORT_IDX) + 0x08u)) /* [SVD] PCOR +0x08 */
#define LED_PTOR (*(volatile uint32_t *)(GPIO_BASE(LED_PORT_IDX) + 0x0Cu)) /* [SVD] PTOR +0x0C */
#define LED_PDOR (*(volatile uint32_t *)(GPIO_BASE(LED_PORT_IDX) + 0x00u)) /* [SVD] PDOR +0x00 */
#define LED_PDDR (*(volatile uint32_t *)(GPIO_BASE(LED_PORT_IDX) + 0x14u)) /* [SVD] PDDR +0x14 */

#if LED_PORT_IDX > 8 || LED_PIN > 7
#error "LED_PORT_IDX must be 0..8 (A..I) and LED_PIN 0..7"
#endif

/* ── Watchdog — WDOG @ 0x40052000 [SVD]. ENABLED OUT OF RESET (CS1 reset 0x80 = EN). */
#define WDOG_CS1    (*(volatile uint8_t  *)0x40052000u) /* EN bit7, INT 6, UPDATE 5, DBG 2 */
#define WDOG_CS2    (*(volatile uint8_t  *)0x40052001u) /* reset 0x01: CLK = 01 (1 kHz LPO) */
#define WDOG_CNT    (*(volatile uint16_t *)0x40052002u) /* unlock / refresh keys */
#define WDOG_TOVAL  (*(volatile uint16_t *)0x40052004u)
#define WDOG_WIN    (*(volatile uint16_t *)0x40052006u)
#define WDOG_UNLOCK_KEY1 0x20C5u   /* [SDK MKE04Z4.h WDOG_UPDATE_KEY1] */
#define WDOG_UNLOCK_KEY2 0x28D9u   /* [SDK MKE04Z4.h WDOG_UPDATE_KEY2] */
#define WDOG_CS1_UPDATE  (1u << 5)

/* ── SIM @ 0x40048000 [SVD] ─────────────────────────────────────────────────── */
#define SIM_SCGC    (*(volatile uint32_t *)0x40048014u) /* reset 0x3000; UART0 gate bit 20, UART1 bit 21 */
#define SCGC_UART0  (1u << 20)
#define SCGC_UART1  (1u << 21)
#define SIM_PINSEL0 (*(volatile uint32_t *)0x4004800Cu) /* [SVD] offset 0x0C, reset 0 */
#define SIM_PINSEL1 (*(volatile uint32_t *)0x40048010u) /* [SVD] offset 0x10, reset 0 */
#define PINSEL0_UART0PS (1u << 7)  /* [SVD] 0 = UART0 RX/TX on PTB0/PTB1, 1 = PTA2/PTA3 */
#define PINSEL1_UART1PS (1u << 12) /* [SVD] 0 = UART1 TX on PTC7, RX on PTC6; 1 = PTF3/PTF2 */

/* ── UART0 @ 0x4006A000, UART1 @ 0x4006B000 [SVD] — same register layout ────── */
#define UART0_BASE  0x4006A000u
#define UART1_BASE  0x4006B000u
#define UART_BDH(b) (*(volatile uint8_t *)((b) + 0x0u)) /* SBR[12:8] bits 4:0, SBNS bit5 */
#define UART_BDL(b) (*(volatile uint8_t *)((b) + 0x1u)) /* SBR[7:0], reset 0x04 */
#define UART_C1(b)  (*(volatile uint8_t *)((b) + 0x2u)) /* M=0 8-bit, PE=0 */
#define UART_C2(b)  (*(volatile uint8_t *)((b) + 0x3u)) /* TE bit3, RE bit2 */
#define UART_S1(b)  (*(volatile uint8_t *)((b) + 0x4u)) /* TDRE bit7 */
#define UART_C3(b)  (*(volatile uint8_t *)((b) + 0x6u))
#define UART_D(b)   (*(volatile uint8_t *)((b) + 0x7u))
#define C2_TE       (1u << 3)
#define S1_TDRE     (1u << 7)
/* Baud divider: 24 MHz / (16 x 13) = 115 384.6 baud (+0.16 %), both UARTs.
 * Bench note 2026-10-15: right after an SWD flash (MDM-AP reset, ICS_C3 = 0x80) the
 * core ran ~22.4 MHz and this read ~107.5 kBd; after a SW1 (pin) reset it ran at nominal
 * (SBR 12 then gave ~125 kBd). So only the first boot after flashing is slow - a pin/power
 * reset fixes it. SBR 12 was tried and reverted. Station-side trim: bead 3slx. */
#ifndef UART_SBR
#define UART_SBR    13u
#endif

/* ── Buttons (HC26060 schematic, owner 2026-10-15: "2 buttons, put a message in the serial").
 *  SW2 USER  = PTD4 to GND, NO external pull-up -> internal pull-up PORT_PUE0 bit 28.
 *  SW1 RESET = PTA5/RESET_b: not readable as GPIO (it IS the reset pin), so the boot
 *              line prints SIM_SRSID's reset cause - a SW1 press shows "PIN (SW1)".
 *  Addresses from NXP MKE04Z1284.h (DFP 14.0.0): PORT 0x4004_9000 {IOFLT0 +0, IOFLT1 +4,
 *  PUE0 +8, PUE1 +C, PUE2 +10, HDRVE +14} - NOT the KE02 layout (PUEL +4);
 *  GPIOA PDIR +0x10, PIDR +0x18 (reset all 1 = input buffers OFF - must be cleared). ── */
#define PORT_PUE0   (*(volatile uint32_t *)0x40049008u)
#define GPIOA_PDIR  (*(volatile uint32_t *)0x400FF010u)
#define GPIOA_PIDR  (*(volatile uint32_t *)0x400FF018u)
#define SW2_MASK    (1u << 28)            /* PTD4 = GPIOA bit 28 = PORT_PUE0_PTDPE4 */
#define SIM_SRSID   (*(volatile uint32_t *)0x40048000u)

/* ── SysTick (ARMv6-M, core clock) — used polled, no interrupt ─────────────── */
#define SYST_CSR    (*(volatile uint32_t *)0xE000E010u) /* ENABLE 0, TICKINT 1, CLKSOURCE 2, COUNTFLAG 16 */
#define SYST_RVR    (*(volatile uint32_t *)0xE000E014u)
#define SYST_CVR    (*(volatile uint32_t *)0xE000E018u)
#define CORE_HZ     24000000u
#define TICK_RELOAD (CORE_HZ / 100u)       /* 10 ms SysTick period; 240000 < 2^24 */

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;

void reset_handler(void);
void default_handler(void);
int main(void);

/* Cortex-M0+ core exceptions (16 words). Device IRQ slots are left 0xFF-filled
 * by the linker: no peripheral interrupt is ever enabled in this image. */
__attribute__((section(".isr_vector"), used))
void (*const vector_table[16])(void) = {
    (void (*)(void))(&_estack), /* 0x00 Initial SP (0x20001800) */
    reset_handler,              /* 0x04 Reset      */
    default_handler,            /* 0x08 NMI        (PTB4 is NMI_b at reset — keep it pulled up) */
    default_handler,            /* 0x0C HardFault  */
    0, 0, 0, 0, 0, 0, 0,        /* 0x10-0x28 reserved on ARMv6-M */
    default_handler,            /* 0x2C SVCall     */
    0, 0,                       /* reserved        */
    default_handler,            /* 0x38 PendSV     */
    default_handler,            /* 0x3C SysTick    */
};

/* ── Flash Configuration Field @ 0x400 (16 bytes) — KE04 FTMRE layout [191] ──
 * ⛔ DO NOT EDIT. A secured KE04 can only be recovered by a mass erase through
 *    MDM-AP; a wrong FSEC here is a one-way risk on the bench. build.sh compares
 *    these 16 bytes of the .bin against the exact pattern below and refuses.
 *   0x400-0x407 backdoor comparison key      = 0xFF (no backdoor)
 *   0x408-0x40B reserved                     = 0xFF
 *   0x40C       EEPROT / reserved            = 0xFF
 *   0x40D       FPROT                        = 0xFF (no flash protection)
 *   0x40E       FSEC                         = 0xFE (SEC = 10 UNSECURED, KEYEN = 11 backdoor off)
 *   0x40F       FOPT                         = 0xFF (erased)
 * ⚠ KL25's FSEC is at 0x40C; on KE it is 0x40E. The station accepts ONLY this
 *   exact pattern (kinetis_ke_fcf_safe()). There is no MEEN field on KE. */
__attribute__((section(".flash_config"), used))
const uint8_t flash_config[16] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFE, 0xFF,
};

static void uart_init_one(uint32_t base)
{
    UART_C2(base) = 0;         /* TX/RX off while the divisor is set */
    UART_BDH(base) = (uint8_t)((UART_SBR >> 8) & 0x1Fu); /* SBNS = 0: one stop bit */
    UART_BDL(base) = (uint8_t)(UART_SBR & 0xFFu);
    UART_C1(base) = 0;         /* 8 data bits, no parity */
    UART_C3(base) = 0;
    UART_C2(base) = C2_TE;     /* TX only */
}

/* The same text goes out on BOTH UARTs:
 *   UART0 TX = PTB1 (pin 23) -> CH340 on HC26060
 *   UART1 TX = PTC7 (pin 36, J4.13) -> header, for an external serial monitor
 * KE has no PCR mux: enabling TE hands the pin to the UART (peripheral beats
 * GPIO in the pin-priority scheme). RX (PTB0, PTC6) is NOT enabled — those pins
 * stay at reset default, so a peer may drive its TX into them harmlessly. */
static void uart_init(void)
{
    SIM_SCGC |= SCGC_UART0 | SCGC_UART1;   /* ungate both (reset: gated) */
    SIM_PINSEL0 &= ~PINSEL0_UART0PS;       /* UART0 on PTB0/PTB1 (= reset value, written to be explicit) */
    SIM_PINSEL1 &= ~PINSEL1_UART1PS;       /* UART1 on PTC6/PTC7 (= reset value, written to be explicit) */
    uart_init_one(UART0_BASE);
    uart_init_one(UART1_BASE);
}

/* Poll TDRE before EVERY byte, on each UART. Same baud on both, so neither
 * waits on the other for more than one character time. */
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

/* Cortex-M0+ has no divide instruction and we link with -nostdlib, so divide
 * by ten with shifts/adds (exact over the whole uint32_t range). */
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

    if (v == 0) {
        uart_putc('0');
        return;
    }
    while (v && n < (int)sizeof(buf)) {
        uint32_t r;
        v = div10(v, &r);
        buf[n++] = (char)('0' + r);
    }
    while (n--) {
        uart_putc(buf[n]);
    }
}

static void wait_tick(void)
{
    while (!(SYST_CSR & (1u << 16))) { /* COUNTFLAG: set on wrap, cleared by the read */
    }
}

int main(void)
{
    uint32_t seq = 0;

    LED_PCOR = LED_MASK;       /* drive low first ... */
    LED_PDDR |= LED_MASK;      /* ... then make it an output (no glitch high) */

    uart_init();
    uart_puts("\nKE04 blink+uart " BUILD_ID "\n");
    uart_puts("UART0 TX=PTB1 (pin 23) + UART1 TX=PTC7 (pin 36) 115200 8N1, LED=" LED_NAME ", core/bus 24 MHz FEI reset default\n");

    /* SW2: input with pull-up (PDDR bit stays 0 = input). */
    PORT_PUE0 |= SW2_MASK;
    GPIOA_PIDR &= ~SW2_MASK;

    /* SW1 test: why did we boot? SIM_SRSID bits [MKE04Z1284.h SIM_SRSID_*_MASK]. */
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

    SYST_RVR = TICK_RELOAD - 1u;
    SYST_CVR = 0;
    SYST_CSR = (1u << 2) | (1u << 0); /* CLKSOURCE = core, ENABLE, no TICKINT */

    /* 10 ms tick: LED toggles every 50 ticks (1 Hz blink, one line per toggle);
     * SW2 sampled every tick, a change must hold 3 ticks (30 ms debounce). */
    uint32_t presses = 0, tick = 0;
    int pressed = 0, stable = 0;
    for (;;) {
        if (tick == 0u) {
            LED_PTOR = LED_MASK;
            uart_putu32(++seq);
            uart_puts((LED_PDOR & LED_MASK) ? " LED=1\n" : " LED=0\n");
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
        wait_tick();
        if (++tick == 50u) tick = 0;   /* no % : M0+ has no divider, -nostdlib */
    }
}

void reset_handler(void)
{
    /* WATCHDOG OFF, FIRST. [SDK SystemInit, SVD WDOG]. The two unlock writes must
     * land back to back (the RM's window is a few bus clocks), so interrupts are
     * masked; then every config register is written once so the new settings
     * take effect, CS1 last with EN = 0 and UPDATE = 1 (re-configurable later). */
    __asm__ volatile("cpsid i");
    WDOG_CNT = WDOG_UNLOCK_KEY1;
    WDOG_CNT = WDOG_UNLOCK_KEY2;
    WDOG_TOVAL = 0xFFFFu;
    WDOG_WIN = 0u;
    WDOG_CS2 = 0x01u;          /* reset value: 1 kHz LPO, no window, no prescaler */
    WDOG_CS1 = WDOG_CS1_UPDATE; /* EN = 0 */
    __asm__ volatile("cpsie i");

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
