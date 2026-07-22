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


def generate_header(measurements):
    """measurements: list of signal dicts as returned by a2l_parser.parse_a2l
    (name, datatype, matrix_dim, ...). Returns the full signals.h text.

    Deterministic and ordered: signals are emitted in the order given, one
    line per signal (or one comment line if the datatype is unsupported).
    """
    lines = [_BANNER]
    used_idents = set()

    for signal in measurements:
        name = signal.get("name")
        datatype = signal.get("datatype")
        c_type = TYPE_MAP.get(datatype)

        if c_type is None:
            lines.append(f"/* unsupported type {datatype!r} for signal '{name}': skipped */")
            continue

        ident = sanitise_identifier(name)
        base_ident = ident
        suffix = 2
        while ident in used_idents:
            ident = f"{base_ident}_{suffix}"
            suffix += 1
        used_idents.add(ident)

        comment = f"  /* original A2L name: {name} */" if ident != name else ""

        matrix_dim = signal.get("matrix_dim")
        if matrix_dim:
            lines.append(f"extern {c_type} {ident}[{matrix_dim}];{comment}")
        else:
            lines.append(f"extern {c_type} {ident};{comment}")

    lines.append(_FOOTER)
    return "\n".join(lines)
