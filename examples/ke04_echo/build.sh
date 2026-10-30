#!/usr/bin/env bash
# Build bare-metal NXP KE04 (MKE04Z64VLD4 / MKE04Z128VLD4, LQFP-44) blink + UART0+UART1 115200
# + UART1 RX line echo ("ECHO <line>") -> ke04_echo.bin, loaded at flash offset 0x00000000.
# Same as ../ke04_blink_uart/build.sh, plus: the FCF must also be byte-identical to the golden
# ../ke04_blink_uart/ke04_blink_uart.bin.
#
# Usage:
#   ./build.sh               default LED = PTA6 (HC26060 user LED D3, pin 26, active high)
#   ./build.sh LED=PTD0      another LED pin -> ke04_echo_led_ptd0.bin
#
# The build FAILS (and deletes the .bin) unless the Flash Configuration Field at
# 0x400..0x40F is exactly the unsecured, unprotected, no-backdoor pattern.
set -euo pipefail

cd "$(dirname "$0")"

LED=PTA6
for arg in "$@"; do
    case "$arg" in
        LED=*) LED="${arg#LED=}" ;;
        *) echo "error: unknown argument '$arg' (only LED=PTxN)" >&2; exit 2 ;;
    esac
done
LED=$(echo "$LED" | tr '[:lower:]' '[:upper:]')

# GPIO pins that exist on the 44-pin LQFP (KE04 DS MKE04P80M48SF0 §8.1, 44-pin column).
PINS44="PTA0 PTA1 PTA2 PTA3 PTA4 PTA5 PTA6 PTA7 PTB0 PTB1 PTB2 PTB3 PTB4 PTB5 PTB6 PTB7
PTC0 PTC1 PTC2 PTC3 PTC4 PTC5 PTC6 PTC7 PTD0 PTD1 PTD2 PTD3 PTD4 PTD5 PTD6 PTD7
PTE0 PTE1 PTE2 PTE7 PTH2 PTI4"
if ! echo $PINS44 | tr ' ' '\n' | grep -qx "$LED"; then
    echo "error: LED=$LED is not a GPIO on the KE04 44-pin LQFP" >&2
    exit 2
fi
case "$LED" in
    PTA4|PTC4) echo "error: $LED is SWD (station needs it)" >&2; exit 2 ;;
    PTA5)      echo "error: PTA5 is RESET_b" >&2; exit 2 ;;
    PTB4)      echo "error: PTB4 is NMI_b at reset (driving it low traps the core in NMI)" >&2; exit 2 ;;
    PTB0|PTB1) echo "error: $LED is UART0 (RX/TX) in this image" >&2; exit 2 ;;
    PTC6|PTC7) echo "error: $LED is UART1 (RX/TX) in this image" >&2; exit 2 ;;
    PTD4)      echo "error: PTD4 is the SW2 user button in this image" >&2; exit 2 ;;
    PTA2|PTA3) echo "warning: $LED is TRUE OPEN-DRAIN: it can only sink, wire the LED to VDD" >&2 ;;
esac
PORT_LETTER=${LED:2:1}
PIN=${LED:3:1}
PORT_IDX=$(( $(printf '%d' "'$PORT_LETTER") - 65 ))

if [ "$LED" = "PTA6" ]; then
    OUT=ke04_echo
else
    OUT=ke04_echo_led_$(echo "$LED" | tr '[:upper:]' '[:lower:]')
fi

# Locate the ARM toolchain: prefer PATH, fall back to the prebuilt ARM release under ~.
if command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    CROSS=arm-none-eabi-
else
    ARM_DIR=$(ls -d "$HOME"/arm-gnu-toolchain-*-x86_64-arm-none-eabi 2>/dev/null | head -1 || true)
    if [ -z "${ARM_DIR:-}" ]; then
        echo "error: arm-none-eabi-gcc not found. Install gcc-arm-none-eabi or the ARM release under ~." >&2
        exit 1
    fi
    CROSS="$ARM_DIR/bin/arm-none-eabi-"
fi

# Build id = hash of the sources (reproducible: same source -> same banner -> same .bin).
SRC_ID=$(cat echo.c mke04z64.ld | sha256sum | cut -c1-8)
BUILD_ID="src-$SRC_ID LED=$LED"

CFLAGS="-mcpu=cortex-m0plus -mthumb -mfloat-abi=soft -Wall -Wextra -Os -ffreestanding -nostdlib"

"${CROSS}gcc" $CFLAGS -T mke04z64.ld \
    -DLED_PORT_IDX="$PORT_IDX" -DLED_PIN="$PIN" -DLED_NAME="\"$LED\"" -DBUILD_ID="\"$BUILD_ID\"" ${UART_SBR:+-DUART_SBR=${UART_SBR}u} \
    -o "$OUT.elf" echo.c
"${CROSS}objcopy" -O binary "$OUT.elf" "$OUT.bin"

fail() {
    echo "error: $*" >&2
    rm -f "$OUT.bin"
    echo "       $OUT.bin DELETED so it cannot be loaded by mistake." >&2
    exit 1
}

SIZE=$(stat -c%s "$OUT.bin")
[ "$SIZE" -gt $((0x410)) ] || fail "image is $SIZE bytes, shorter than the FCF"
[ "$SIZE" -le $((64 * 1024)) ] || fail "image is $SIZE bytes, does not fit the 64 KB part"

# ── SAFETY: Flash Configuration Field, KE04 FTMRE layout (docs/191) ──────────
#   0x400-0x407 backdoor key FF..  0x408-0x40B reserved FF  0x40C EEPROT FF
#   0x40D FPROT FF (no protection)  0x40E FSEC FE (SEC=10 unsecure, KEYEN=11 off)  0x40F FOPT FF
# Exact match of all 16 bytes — the same rule as the station's kinetis_ke_fcf_safe().
FCF_WANT="fffffffffffffffffffffffffffffeff"
FCF_GOT=$(od -An -tx1 -v -j $((0x400)) -N16 "$OUT.bin" | tr -d ' \n')
[ "$FCF_GOT" = "$FCF_WANT" ] || fail "FCF @0x400 is $FCF_GOT, expected $FCF_WANT — a secured/protected image is a one-way risk, refusing"
# Second, independent check: the same 16 bytes must equal the golden blink image's FCF.
GOLDEN=../ke04_blink_uart/ke04_blink_uart.bin
[ -f "$GOLDEN" ] || fail "golden $GOLDEN missing, cannot cross-check the FCF"
cmp -s <(dd if="$OUT.bin" bs=1 skip=$((0x400)) count=16 2>/dev/null) \
       <(dd if="$GOLDEN"  bs=1 skip=$((0x400)) count=16 2>/dev/null) \
    || fail "FCF @0x400 differs from the golden $GOLDEN, refusing"

# Vector table sanity: initial SP inside the Z64 SRAM, reset vector a Thumb address inside the image.
word() { od -An -tu4 -v -j "$1" -N4 "$OUT.bin" | tr -d ' \n'; }
SP=$(word 0); RV=$(word 4)
[ "$SP" -gt $((0x1FFFF800)) ] && [ "$SP" -le $((0x20001800)) ] || fail "initial SP 0x$(printf %08x "$SP") outside SRAM"
[ $((RV & 1)) -eq 1 ] && [ "$RV" -gt $((0x410)) ] && [ "$RV" -lt "$SIZE" ] || fail "reset vector 0x$(printf %08x "$RV") invalid"

echo "Built $OUT.bin ($SIZE bytes) — $BUILD_ID"
echo "FCF check OK (pattern + identical to golden ke04_blink_uart.bin): 0x400..0x40F = $(od -An -tx1 -v -j $((0x400)) -N16 "$OUT.bin" | tr -s ' ' | sed 's/^ //')"
echo "Vectors OK: SP=0x$(printf %08x "$SP") reset=0x$(printf %08x "$RV")"
echo "sha256 $(sha256sum "$OUT.bin" | cut -d' ' -f1)"
