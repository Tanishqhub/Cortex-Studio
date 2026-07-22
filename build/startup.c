/*
 * startup.c -- FIXED, checked into the repo. Never generated, never
 * user-supplied (see docs/SECURITY.md T7 and _plan/phase4.txt). Every
 * sandboxed build compiles this exact file alongside the user's C.
 *
 * Minimal Cortex-M4 reset path: a vector table with just the entries the
 * ARMv7-M architecture requires a linker/debugger to find (initial SP,
 * Reset_Handler, and the fault/exception handlers up to SysTick — every
 * unused IRQ slot beyond that is intentionally omitted since this profile
 * is freestanding/never-flashed, see header_gen.py's compile-time-contract
 * note), plus a Reset_Handler that does the usual startup sequence: copy
 * .data from its load address in FLASH to RAM, zero .bss, call main().
 */
#include <stdint.h>

extern uint32_t _sidata;
extern uint32_t _sdata;
extern uint32_t _edata;
extern uint32_t _sbss;
extern uint32_t _ebss;
extern uint32_t _estack;

int main(void);

void Reset_Handler(void);
void Default_Handler(void);

void NMI_Handler(void) __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void MemManage_Handler(void) __attribute__((weak, alias("Default_Handler")));
void BusFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void UsageFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SVC_Handler(void) __attribute__((weak, alias("Default_Handler")));
void DebugMon_Handler(void) __attribute__((weak, alias("Default_Handler")));
void PendSV_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void) __attribute__((weak, alias("Default_Handler")));

__attribute__((section(".isr_vector")))
void (* const vector_table[])(void) = {
    (void (*)(void))&_estack,
    Reset_Handler,
    NMI_Handler,
    HardFault_Handler,
    MemManage_Handler,
    BusFault_Handler,
    UsageFault_Handler,
    0,
    0,
    0,
    0,
    SVC_Handler,
    DebugMon_Handler,
    0,
    PendSV_Handler,
    SysTick_Handler,
};

void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    uint32_t *dst = &_sdata;
    while (dst < &_edata) {
        *dst++ = *src++;
    }

    dst = &_sbss;
    while (dst < &_ebss) {
        *dst++ = 0;
    }

    main();

    while (1) {
    }
}

void Default_Handler(void)
{
    while (1) {
    }
}
