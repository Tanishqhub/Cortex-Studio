/*
 * link.ld -- FIXED, checked into the repo. Never generated, never
 * user-supplied (see docs/SECURITY.md T7 and _plan/phase4.txt).
 *
 * Memory map is an arbitrary but fixed and documented generic Cortex-M4
 * profile (512K FLASH at 0x08000000, 128K RAM at 0x20000000 - the common
 * layout for this class of MCU). Nothing in this project flashes real
 * hardware (out of scope, see 00_agent_ground_rules.txt), so these
 * addresses only need to be internally consistent for the linker, not
 * matched to a specific physical chip.
 */
ENTRY(Reset_Handler)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector :
    {
        KEEP(*(.isr_vector))
    } > FLASH

    .text :
    {
        *(.text*)
        *(.rodata*)
    } > FLASH

    _sidata = LOADADDR(.data);

    .data :
    {
        _sdata = .;
        *(.data*)
        _edata = .;
    } > RAM AT> FLASH

    .bss :
    {
        _sbss = .;
        *(.bss*)
        *(COMMON)
        _ebss = .;
    } > RAM
}
