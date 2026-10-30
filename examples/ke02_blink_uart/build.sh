#!/usr/bin/env bash
# Build bare-metal NXP KE02 (MKE02Z16/Z32/Z64, LQFP-44) blink + UART0 -> ke02_blink_uart.bin
# (load at flash offset 0x00000000).
#
#   ./build.sh                     default: LED=PTA6 active-high, BAUD=115200
#   LED=PTD0 ./build.sh            another LED pin (PTA0..PTH7) -> ke02_blink_uart_PTD0.bin
#   LED_ACTIVE_LOW=1 ./build.sh    LED wired pin -> LED -> VDD
#   BAUD=38400 ./build.sh          safer baud on the 16 MHz bus (see blink.c BAUD block)
#
# The build FAILS unless the image's Flash Configuration Field (0x400-0x40F) is exactly
# FF*8 | FF*4 | EEPROT FF | FPROT FF | FSEC FE | FOPT FF  — unsecured, no backdoor, no protection.
set -euo pipefail

cd "$(dirname "$0")"

LED="${LED:-PTA6}"
BAUD="${BAUD:-115200}"
LED_ACTIVE_LOW="${LED_ACTIVE_LOW:-0}"

if [[ ! "$LED" =~ ^PT([A-H])([0-7])$ ]]; then
    echo "error: LED='$LED' — expected PTA0..PTH7" >&2
    exit 1
fi
PORT_IDX=$(( $(printf '%d' "'${BASH_REMATCH[1]}") - 65 ))
PIN="${BASH_REMATCH[2]}"

# Pins this image must never drive: SWD (PTA4 SWD_DIO, PTC4 SWD_CLK), RESET (PTA5),
# NMI (PTB4), UART0 (PTB0 RX, PTB1 TX), UART1 (PTC6 RX, PTC7 TX), SW2 button (PTD4). Driving SWD/RESET could lock your probe out.
case "$LED" in
    PTA4|PTC4|PTA5|PTB4|PTB0|PTB1|PTC6|PTC7|PTD4)
        echo "error: LED=$LED is a SWD/RESET/NMI/UART/button pin on KE02 — refusing" >&2
        exit 1 ;;
esac
if [[ ! "$LED_ACTIVE_LOW" =~ ^[01]$ ]]; then
    echo "error: LED_ACTIVE_LOW='$LED_ACTIVE_LOW' — 0 or 1" >&2
    exit 1
fi
if [[ ! "$BAUD" =~ ^[0-9]+$ ]] || [ "$BAUD" -lt 2400 ] || [ "$BAUD" -gt 1000000 ]; then
    echo "error: BAUD='$BAUD'" >&2
    exit 1
fi

# Toolchain: the pinned ARM 13.2 release first, then PATH, then any ARM release under ~.
TC13="$HOME/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin/arm-none-eabi-"
if [ -x "${TC13}gcc" ]; then
    CROSS="$TC13"
elif command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    CROSS=arm-none-eabi-
else
    ARM_DIR=$(ls -d "$HOME"/arm-gnu-toolchain-*-x86_64-arm-none-eabi 2>/dev/null | head -1 || true)
    if [ -z "${ARM_DIR:-}" ]; then
        echo "error: arm-none-eabi-gcc not found" >&2
        exit 1
    fi
    CROSS="$ARM_DIR/bin/arm-none-eabi-"
fi

OUT=ke02_blink_uart
if [ "$LED" != "PTA6" ]; then OUT="${OUT}_${LED}"; fi
if [ "$LED_ACTIVE_LOW" != "0" ]; then OUT="${OUT}_low"; fi
if [ "$BAUD" != "115200" ]; then OUT="${OUT}_${BAUD}"; fi

# Build id = hash of the sources, so the banner names the exact source a binary came from
# and a rebuild of unchanged source is byte-identical (no dates, no git state).
SRC_ID=$(cat blink.c mke02z16.ld | sha256sum | cut -c1-8)
BUILD_ID="src-${SRC_ID}"

CFLAGS=(-mcpu=cortex-m0plus -mthumb -mfloat-abi=soft -Wall -Wextra -Werror -Os -ffreestanding -nostdlib)
DEFS=(-DLED_PORT="$PORT_IDX" -DLED_PIN="$PIN" -DLED_NAME="\"$LED\"" -DLED_ACTIVE_LOW="$LED_ACTIVE_LOW"
      -DBAUD="${BAUD}" -DBUILD_ID="\"$BUILD_ID\"")

"${CROSS}gcc" "${CFLAGS[@]}" "${DEFS[@]}" -T mke02z16.ld -o "$OUT.elf" blink.c
"${CROSS}objcopy" -O binary "$OUT.elf" "$OUT.bin"

SIZE=$(stat -c%s "$OUT.bin")
POL=high
if [ "$LED_ACTIVE_LOW" = "1" ]; then POL=low; fi
echo "Built $OUT.bin ($SIZE bytes, $BUILD_ID, LED=$LED active-$POL, $BAUD 8N1)"
"${CROSS}size" "$OUT.elf"

fail() {
    echo "error: $*" >&2
    echo "       REFUSING: $OUT.bin and $OUT.elf deleted." >&2
    rm -f "$OUT.bin" "$OUT.elf"
    exit 1
}

# ── Safety gate 1: FCF must be EXACTLY the unsecured, unprotected, no-backdoor pattern ──
# KE02 RM 18.3.6 Table 18-6: 0x400-7 backdoor key, 0x408-B reserved, 0x40C EEPROT,
# 0x40D FPROT, 0x40E FSEC, 0x40F FOPT. FSEC 0xFE = KEYEN 11 (backdoor off), SEC 10 (unsecure).
# ⚠ KE's FSEC is at 0x40E — NOT 0x40C as on KL25/K64. Checking 0x40C alone would pass a
# secured KE image (0x40C is EEPROT here).
WANT="ffffffffffffffffffffffffffff""feff"   # 14 x FF, then FSEC FE, FOPT FF
FCF=$(od -An -tx1 -v -j $((0x400)) -N16 "$OUT.bin" | tr -d ' \n')
if [ "$FCF" != "$WANT" ]; then
    fail "FCF 0x400-0x40F = '$FCF', expected '$WANT' (FSEC 0xFE @ 0x40E) — this image could secure the KE02"
fi
echo "FCF check OK: 0x400-0x40F = $FCF"
echo "              backdoor key FF*8, reserved FF*4, EEPROT FF, FPROT FF, FSEC FE @0x40E (SEC=10 unsecured, KEYEN=11 off), FOPT FF"

# ── Safety gate 2: sane vector table, and it fits the 16 KB part ──
SP=$(od -An -tx4 -v -j 0 -N4 "$OUT.bin" | tr -d ' \n')
RV=$(od -An -tx4 -v -j 4 -N4 "$OUT.bin" | tr -d ' \n')
if [ "$SP" != "20000600" ]; then fail "initial SP 0x$SP, expected 0x20000600 (top of 2 KB SRAM)"; fi
if [ $((0x$RV & 1)) -ne 1 ] || [ $((0x$RV)) -lt $((0x410)) ] || [ $((0x$RV)) -ge 16384 ]; then
    fail "reset vector 0x$RV not a Thumb address in 0x410..0x3FFF"
fi
if [ "$SIZE" -gt 16384 ]; then fail "$SIZE bytes does not fit the 16 KB MKE02Z16"; fi
echo "Vector OK: SP=0x$SP reset=0x$RV; $SIZE bytes fits 16 KB"
echo "sha256 $(sha256sum "$OUT.bin" | cut -d' ' -f1)  $OUT.bin"
