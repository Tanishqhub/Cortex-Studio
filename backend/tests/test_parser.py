import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest

from app.a2l_parser import ParseError, parse_a2l

SIMPLE = """
/begin PROJECT p ""
/begin MODULE m ""

/begin MEASUREMENT current_gear "measurement for symbol current_gear"
  UBYTE gear_state_t 0 0 0 2
  ECU_ADDRESS 0x280058C0
  SYMBOL_LINK "current_gear" 0
/end MEASUREMENT

/end MODULE
/end PROJECT
"""

DOTTED = """
/begin MEASUREMENT ctx[0].state "state for ctx 0"
  UBYTE NO_COMPU_METHOD 0 0 0 255
  ECU_ADDRESS 0x1000
  MATRIX_DIM 2
/end MEASUREMENT
"""

MISSING_ADDRESS = """
/begin MEASUREMENT no_addr "no ecu address"
  UWORD NO_COMPU_METHOD 0 0 0 65535
/end MEASUREMENT
"""

TRUNCATED = """
/begin MEASUREMENT broken "never closed"
  UBYTE NO_COMPU_METHOD 0 0 0 255
"""

NOT_A2L = "this is just some random text\nwith no a2l blocks in it at all\n"


def test_simple_measurement_fields():
    result = parse_a2l(SIMPLE)
    assert result["summary"]["measurement_count"] == 1
    assert result["summary"]["characteristic_count"] == 0
    signal = result["measurements"][0]
    assert signal["name"] == "current_gear"
    assert signal["kind"] == "MEASUREMENT"
    assert signal["direction"] == "input"
    assert signal["datatype"] == "UBYTE"
    assert signal["compu_method"] == "gear_state_t"
    assert signal["address"] == "0x280058C0"
    assert signal["limits"] == {"lower": 0, "upper": 2}
    assert signal["matrix_dim"] is None


def test_dotted_bracketed_name_and_matrix_dim():
    result = parse_a2l(DOTTED)
    signal = result["measurements"][0]
    assert signal["name"] == "ctx[0].state"
    assert signal["matrix_dim"] == 2
    assert signal["compu_method"] is None  # NO_COMPU_METHOD -> null


def test_missing_ecu_address_is_null_not_a_crash():
    result = parse_a2l(MISSING_ADDRESS)
    signal = result["measurements"][0]
    assert signal["address"] is None
    assert signal["datatype"] == "UWORD"


def test_truncated_block_raises_parse_error():
    with pytest.raises(ParseError):
        parse_a2l(TRUNCATED)


def test_non_a2l_input_raises_parse_error():
    with pytest.raises(ParseError):
        parse_a2l(NOT_A2L)


def test_real_sample_ground_truth():
    sample_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "_resources", "Reference_a2l.a2l"
    )
    with open(sample_path, encoding="utf-8") as f:
        text = f.read()
    result = parse_a2l(text)
    assert result["summary"]["measurement_count"] == 173
    assert result["summary"]["characteristic_count"] == 0
    gear = next(m for m in result["measurements"] if m["name"] == "current_gear")
    assert gear["datatype"] == "UBYTE"
    assert gear["address"] == "0x280058C0"
    assert gear["limits"] == {"lower": 0, "upper": 2}
    assert gear["compu_method"] == "gear_state_t"
