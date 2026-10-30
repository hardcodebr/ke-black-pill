/* Linker script for NXP MKE04Z64VLD4 (also runs unchanged on MKE04Z128VLD4).
 *
 * Built for the 64 KB layout so ONE image fits both parts:
 *   Flash  64 KB @ 0x00000000 (the Z128 has 128 KB; its upper half stays unused)
 *   SRAM    8 KB = 0x1FFFF800 .. 0x20001800 (Z64). The Z128's 16 KB SRAM is
 *                  0x1FFFF000 .. 0x20003000, which CONTAINS this window, so the
 *                  same stack top is valid on both (docs/191 geometry table).
 * Cortex-M0+.
 *
 * The Flash Configuration Field MUST sit at 0x400-0x40F and MUST be the safe
 * pattern (all 0xFF except FSEC = 0xFE at 0x40E). build.sh refuses the image
 * otherwise. Code is placed after it.
 */

ENTRY(reset_handler)

MEMORY
{
    VECTORS (rx)  : ORIGIN = 0x00000000, LENGTH = 0x400
    FCF     (rx)  : ORIGIN = 0x00000400, LENGTH = 0x10
    FLASH   (rx)  : ORIGIN = 0x00000410, LENGTH = 64K - 0x410
    RAM     (rwx) : ORIGIN = 0x1FFFF800, LENGTH = 8K
}

/* Top of stack = end of the Z64 SRAM = 0x20001800 */
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector :
    {
        KEEP(*(.isr_vector))
        . = ALIGN(4);
        FILL(0xFF);
        . = ORIGIN(VECTORS) + LENGTH(VECTORS); /* pad so the FCF lands at exactly 0x400 */
    } > VECTORS

    .flash_config :
    {
        KEEP(*(.flash_config))
    } > FCF

    .text :
    {
        *(.text)
        *(.text*)
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
        _etext = .;
    } > FLASH

    _sidata = LOADADDR(.data);

    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH

    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    /DISCARD/ : { *(.ARM.exidx*) }
}
