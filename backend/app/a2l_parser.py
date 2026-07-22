"""Line-scanner for the A2L subset this project cares about: MEASUREMENT and
CHARACTERISTIC blocks. This is NOT a general ASAM A2L grammar/parser — see
docs/DECISIONS.md for why a full grammar was rejected as out of scope.

MEASUREMENT block shape (verified against _resources/Reference_a2l.a2l):

    /begin MEASUREMENT <name> "<description>"
      <DATATYPE> <COMPU_METHOD|NO_COMPU_METHOD> <res> <res> <lower> <upper>
      ECU_ADDRESS <hex>          (optional)
      MATRIX_DIM <n>             (optional)
      SYMBOL_LINK "<str>" <n>    (optional, ignored)
    /end MEASUREMENT

CHARACTERISTIC blocks use a different field layout (TYPE, inline address,
record layout, conversion, limits) that the sample file has zero instances
of, so it has never been exercised against ground truth here. Rather than
guess at field positions, CHARACTERISTIC blocks are only parsed for
name/kind; every field is left null and the block is reported in the
`skipped` list. This is a deliberate scope cut (see 00_agent_ground_rules.txt
rule 3: fail loudly instead of faking data).
"""

import re

MEASUREMENT = "MEASUREMENT"
CHARACTERISTIC = "CHARACTERISTIC"
_KNOWN_KINDS = (MEASUREMENT, CHARACTERISTIC)

_BEGIN_RE = re.compile(r"^/begin\s+(\S+)\s*(.*)$")
_HEADER_RE = re.compile(r'^(\S+)\s*(?:"([^"]*)")?')
_NO_COMPU_METHOD = "NO_COMPU_METHOD"


class ParseError(Exception):
    """Raised for input that can't be scanned at all (truncated file, not
    A2L-shaped input, etc). The Flask route turns this into a 422."""


def _to_number(token):
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return None


def _parse_header(rest):
    """rest = everything on the /begin <KIND> line after the kind keyword,
    e.g.  current_gear "measurement for symbol current_gear" """
    m = _HEADER_RE.match(rest)
    if not m:
        return None, None
    return m.group(1), m.group(2) or ""


def _parse_measurement_body(block_lines):
    """Returns (fields_dict, skip_reason_or_None)."""
    fields = {
        "datatype": None,
        "address": None,
        "compu_method": None,
        "matrix_dim": None,
        "limits": {"lower": None, "upper": None},
    }
    skip_reason = None

    definition_line = None
    for line in block_lines:
        if line and not line.startswith(("ECU_ADDRESS", "MATRIX_DIM", "SYMBOL_LINK")):
            definition_line = line
            break

    if definition_line is None:
        skip_reason = "missing datatype/conversion/limits definition line"
    else:
        tokens = definition_line.split()
        if tokens:
            fields["datatype"] = tokens[0]
        if len(tokens) > 1 and tokens[1] != _NO_COMPU_METHOD:
            fields["compu_method"] = tokens[1]
        if len(tokens) >= 2:
            lower = _to_number(tokens[-2])
            upper = _to_number(tokens[-1])
            fields["limits"] = {"lower": lower, "upper": upper}
            if lower is None or upper is None:
                skip_reason = "could not parse numeric limits from definition line"

    for line in block_lines:
        if line.startswith("ECU_ADDRESS"):
            tokens = line.split()
            if len(tokens) > 1:
                fields["address"] = tokens[1]
        elif line.startswith("MATRIX_DIM"):
            tokens = line.split()
            if len(tokens) > 1:
                dim = _to_number(tokens[1])
                fields["matrix_dim"] = int(dim) if dim is not None else None

    return fields, skip_reason


def _direction_for(kind):
    # MEASUREMENT = readable ECU value = "input" to the C program.
    # CHARACTERISTIC = writable calibration param = "output"/tunable.
    # See docs/DECISIONS.md for the reasoning.
    return "input" if kind == MEASUREMENT else "output"


def parse_a2l(text):
    lines = [line.strip() for line in text.splitlines()]
    n = len(lines)

    measurements = []
    characteristics = []
    skipped = []
    datatypes_seen = set()
    saw_any_begin = False

    i = 0
    while i < n:
        line = lines[i]
        m = _BEGIN_RE.match(line)
        if not m:
            i += 1
            continue

        saw_any_begin = True
        kind = m.group(1)
        if kind not in _KNOWN_KINDS:
            i += 1
            continue

        header_rest = m.group(2)
        end_marker = f"/end {kind}"
        block_lines = []
        j = i + 1
        closed = False
        while j < n:
            if lines[j] == end_marker:
                closed = True
                break
            block_lines.append(lines[j])
            j += 1

        if not closed:
            raise ParseError(
                f"unterminated /begin {kind} block starting at line {i + 1} "
                f"(no matching {end_marker} found before end of file)"
            )

        name, description = _parse_header(header_rest)
        if name is None:
            skipped.append(
                {"kind": kind, "line": i + 1, "name": None, "reason": "could not parse block header"}
            )
            i = j + 1
            continue

        signal = {
            "name": name,
            "kind": kind,
            "direction": _direction_for(kind),
            "datatype": None,
            "address": None,
            "limits": {"lower": None, "upper": None},
            "compu_method": None,
            "matrix_dim": None,
        }

        if kind == MEASUREMENT:
            fields, skip_reason = _parse_measurement_body(block_lines)
            signal.update(fields)
            if fields["datatype"]:
                datatypes_seen.add(fields["datatype"])
            if skip_reason:
                skipped.append({"kind": kind, "line": i + 1, "name": name, "reason": skip_reason})
            measurements.append(signal)
        else:
            skipped.append(
                {
                    "kind": kind,
                    "line": i + 1,
                    "name": name,
                    "reason": (
                        "CHARACTERISTIC field extraction not implemented (no CHARACTERISTIC "
                        "blocks in the reference sample to validate field layout against); "
                        "only name/kind captured"
                    ),
                }
            )
            characteristics.append(signal)

        i = j + 1

    if not saw_any_begin:
        raise ParseError("no /begin blocks found; this does not look like a valid A2L file")

    return {
        "measurements": measurements,
        "characteristics": characteristics,
        "summary": {
            "measurement_count": len(measurements),
            "characteristic_count": len(characteristics),
            "datatypes_seen": sorted(datatypes_seen),
            "skipped": skipped,
        },
    }
