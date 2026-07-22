#!/bin/sh
# Fixed build sequence baked into the sandbox image. Not parameterised by
# argv on purpose: even if the caller (backend/app/compiler.py) had a bug
# and passed through attacker-controlled arguments, this script ignores
# them and always runs the exact same two commands against files that must
# already exist at fixed names in the (per-build, tmpfs-mounted) workdir.
#
# Compiler flags mirror the reference build command in _plan/phase4.txt,
# verified against `arm-none-eabi-gcc --version` / `--help` in this image
# (see docs/SECURITY.md for the verification output).
set -eu

cd /build

arm-none-eabi-gcc \
    -mcpu=cortex-m4 -mthumb -Wall -Wextra \
    -ffreestanding -nostdlib -O0 -g \
    -T link.ld startup.c signals_def.c user.c -o out.elf

arm-none-eabi-objcopy -O binary out.elf out.bin
