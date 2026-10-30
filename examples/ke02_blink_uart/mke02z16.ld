/* Linker script for NXP MKE02Z16 (smallest KE02) — the image therefore also fits
 * MKE02Z32 / MKE02Z64 unchanged.
 *   Flash 16 KB @ 0x00000000 (MKE02Z16VLD2: 0x0000_0000-0x0000_3FFF, RM 3.7.1.1)
 *   SRAM   2 KB @ 0x1FFFFE00 (SRAM_L 512 B 0x1FFFFE00-0x1FFFFFFF + SRAM_U 1.5 KB
 *          0x20000000-0x200005FF; RM 3.7.3, Table 3-25). Z32/Z64 have 4 KB — unused here.
 * The Flash Configuration Field MUST sit at 0x400-0x40F (RM 18.3.6 Table 18-6);
 * code is placed after it. Cortex-M0+.
 */

ENTRY(reset_handler)

MEMORY
{
    VECTORS (rx)  : ORIGIN = 0x00000000, LENGTH = 0x400
    FCF     (rx)  : ORIGIN = 0x00000400, LENGTH = 0x10
    FLASH   (rx)  : ORIGIN = 0x00000410, LENGTH = 16K - 0x410
    RAM     (rwx) : ORIGIN = 0x1FFFFE00, LENGTH = 2K
}

/* Top of stack = end of SRAM_U on the 2 KB part = 0x20000600 */
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
}

/* A .flash_config section that is missing or the wrong size would leave 0x40E erased
 * (0xFF = SEC 11 = SECURED). Fail the link instead. */
ASSERT(SIZEOF(.flash_config) == 16, "FCF must be exactly 16 bytes at 0x400")
ASSERT(ADDR(.flash_config) == 0x400, "FCF must start at 0x400")
