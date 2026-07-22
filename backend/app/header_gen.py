"""Generates signals.h from a workspace's parsed A2L MEASUREMENT signals.

See docs/DECISIONS.md ("brief 4.4 - how signals reach the code") for why a
generated header was chosen over accessor .c stubs or compile-time -D
injection: a header is the most transparent, ordinary way for C code to see
externally-defined symbols, and it's how embedded devs already work with
memory-mapped signals.

IMPORTANT - this is a COMPILE-TIME CONTRACT ONLY. This webapp does not
flash real ECU memory or perform real hardware linkage (out of scope, see
00_agent_ground_rules.txt). The `extern` declarations let C code compile
against signal names/types; Phase 4's sandbox build is responsible for
giving them SOME storage to link against (e.g. a generated stub .c), not a
real memory-mapped address.

Datatype mapping (A2L -> C, via <stdint.h>) is fixed and documented here;
an A2L datatype with no entry is NOT guessed at - the signal is skipped and
a comment is emitted instead (ground rule: fail loudly, don't fake data).
"""

import re

TYPE_MAP = {
    "UBYTE": "uint8_t",
    "SBYTE": "int8_t",
    "UWORD": "uint16_t",
    "SWORD": "int16_t",
    "ULONG": "uint32_t",
    "SLONG": "int32_t",
    "A_UINT64": "uint64_t",
    "A_INT64": "int64_t",
    "FLOAT32_IEEE": "float",
    "FLOAT64_IEEE": "double",
}

_INVALID_IDENT_CHARS = re.compile(r"[^A-Za-z0-9_]")
_LEADING_DIGIT = re.compile(r"^[0-9]")

_BANNER = """/*
 * signals.h -- AUTO-GENERATED. DO NOT EDIT BY HAND.
 *
 * Generated from this workspace's uploaded A2L file. Declares one `extern`
 * per MEASUREMENT signal so C code can reference ECU signals by name at
 * compile time. Names that aren't legal C identifiers (e.g. containing
 * '.' or '[]') are sanitised; the original A2L name is kept in a comment.
 *
 * THIS IS A COMPILE-TIME CONTRACT ONLY, NOT REAL LINKAGE. This webapp does
 * not flash real ECU memory or communicate with hardware (out of scope -
 * see 00_agent_ground_rules.txt / docs/DECISIONS.md). These externs let
 * code compile against signal names and types, nothing more.
 */
#ifndef SIGNALS_H
#define SIGNALS_H

#include <stdint.h>
"""

_FOOTER = "\n#endif /* SIGNALS_H */\n"


def sanitise_identifier(name):
    """Map an arbitrary A2L signal name to a legal C identifier."""
    ident = _INVALID_IDENT_CHARS.sub("_", name)
    if _LEADING_DIGIT.match(ident):
        ident = "_" + ident
    if not ident:
        ident = "_"
    return ident


def _resolve_signals(measurements):
    """Shared name-resolution pass: sanitises + de-duplicates identifiers in
    signal order, same logic generate_header has always used. Returns a list
    of dicts, either {"skipped": True, "name", "datatype"} for datatypes not
    in TYPE_MAP, or {"skipped": False, "name", "ident", "c_type",
    "matrix_dim"}. Used by both generate_header (declarations) and
    generate_definitions (Phase 4: storage for the linker to resolve those
    externs against, see docs/DECISIONS.md)."""
    resolved = []
    used_idents = set()

    for signal in measurements:
        name = signal.get("name")
        datatype = signal.get("datatype")
        c_type = TYPE_MAP.get(datatype)

        if c_type is None:
            resolved.append({"skipped": True, "name": name, "datatype": datatype})
            continue

        ident = sanitise_identifier(name)
        base_ident = ident
        suffix = 2
        while ident in used_idents:
            ident = f"{base_ident}_{suffix}"
            suffix += 1
        used_idents.add(ident)

        resolved.append(
            {
                "skipped": False,
                "name": name,
                "ident": ident,
                "c_type": c_type,
                "matrix_dim": signal.get("matrix_dim"),
            }
        )

    return resolved


def generate_header(measurements):
    """measurements: list of signal dicts as returned by a2l_parser.parse_a2l
    (name, datatype, matrix_dim, ...). Returns the full signals.h text.

    Deterministic and ordered: signals are emitted in the order given, one
    line per signal (or one comment line if the datatype is unsupported).
    """
    lines = [_BANNER]

    for signal in _resolve_signals(measurements):
        if signal["skipped"]:
            lines.append(f"/* unsupported type {signal['datatype']!r} for signal '{signal['name']}': skipped */")
            continue

        ident = signal["ident"]
        comment = f"  /* original A2L name: {signal['name']} */" if ident != signal["name"] else ""

        if signal["matrix_dim"]:
            lines.append(f"extern {signal['c_type']} {ident}[{signal['matrix_dim']}];{comment}")
        else:
            lines.append(f"extern {signal['c_type']} {ident};{comment}")

    lines.append(_FOOTER)
    return "\n".join(lines)


_DEFINITIONS_BANNER = """/*
 * signals_def.c -- AUTO-GENERATED. DO NOT EDIT BY HAND.
 *
 * Phase 4 concern (see signals.h's banner and docs/DECISIONS.md): signals.h
 * declares these as `extern`, which satisfies the compiler but not the
 * linker -- an extern with no definition anywhere is an undefined reference
 * at link time. This file gives each declared signal exactly one
 * zero-initialised definition so `-T link.ld startup.c signals_def.c
 * user.c` links. Zero-initialised, not garbage: this is a compile-time
 * contract only, not real ECU memory (see signals.h), so there is no
 * meaningful initial value to give it.
 */
#include "signals.h"
"""


def generate_definitions(measurements):
    """Companion to generate_header: one zero-initialised tentative
    definition per signal generate_header declared `extern`, in the same
    order, using the exact same resolved identifiers (calls
    _resolve_signals independently, but it's a pure deterministic function
    of `measurements`, so the identifiers always match signals.h for the
    same input)."""
    lines = [_DEFINITIONS_BANNER]

    for signal in _resolve_signals(measurements):
        if signal["skipped"]:
            continue

        ident = signal["ident"]
        if signal["matrix_dim"]:
            lines.append(f"{signal['c_type']} {ident}[{signal['matrix_dim']}];")
        else:
            lines.append(f"{signal['c_type']} {ident};")

    return "\n".join(lines) + "\n"
