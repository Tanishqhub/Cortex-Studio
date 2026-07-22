from app.header_gen import generate_header, sanitise_identifier


def _measurement(name, datatype, matrix_dim=None):
    return {
        "name": name,
        "kind": "MEASUREMENT",
        "direction": "input",
        "datatype": datatype,
        "address": "0x0",
        "limits": {"lower": 0, "upper": 1},
        "compu_method": None,
        "matrix_dim": matrix_dim,
    }


def test_datatype_mapping():
    measurements = [
        _measurement("a", "UBYTE"),
        _measurement("b", "SBYTE"),
        _measurement("c", "UWORD"),
        _measurement("d", "SWORD"),
        _measurement("e", "ULONG"),
        _measurement("f", "SLONG"),
        _measurement("g", "A_UINT64"),
        _measurement("h", "A_INT64"),
        _measurement("i", "FLOAT32_IEEE"),
        _measurement("j", "FLOAT64_IEEE"),
    ]
    header = generate_header(measurements)

    assert "extern uint8_t a;" in header
    assert "extern int8_t b;" in header
    assert "extern uint16_t c;" in header
    assert "extern int16_t d;" in header
    assert "extern uint32_t e;" in header
    assert "extern int32_t f;" in header
    assert "extern uint64_t g;" in header
    assert "extern int64_t h;" in header
    assert "extern float i;" in header
    assert "extern double j;" in header


def test_current_gear_maps_to_uint8_t():
    header = generate_header([_measurement("current_gear", "UBYTE")])
    assert "extern uint8_t current_gear;" in header


def test_unknown_datatype_is_skipped_with_comment_not_guessed():
    header = generate_header([_measurement("mystery", "SOME_FUTURE_TYPE")])
    assert "extern" not in header.split("#include <stdint.h>")[1].replace("SOME_FUTURE_TYPE", "")
    assert "/* unsupported type 'SOME_FUTURE_TYPE' for signal 'mystery': skipped */" in header
    assert "mystery" not in header.replace(
        "/* unsupported type 'SOME_FUTURE_TYPE' for signal 'mystery': skipped */", ""
    )


def test_dotted_bracketed_name_is_sanitised_with_original_name_comment():
    header = generate_header([_measurement("ctx[0].state", "UBYTE")])
    assert "extern uint8_t ctx_0__state;" in header
    assert "/* original A2L name: ctx[0].state */" in header
    # the raw dotted/bracketed name must never appear as a bare (unquoted) identifier
    assert "ctx[0].state;" not in header


def test_name_sanitisation_helper():
    assert sanitise_identifier("ctx[0].state") == "ctx_0__state"
    assert sanitise_identifier("AppStatusListFrame620.app_uid") == "AppStatusListFrame620_app_uid"
    assert sanitise_identifier("already_legal") == "already_legal"
    assert sanitise_identifier("9lives") == "_9lives"


def test_uniqueness_after_sanitising_collision():
    # 'a.b' and 'a_b' both sanitise to 'a_b' -- the second must be renamed, not
    # silently dropped or overwrite the first.
    header = generate_header(
        [
            _measurement("a.b", "UBYTE"),
            _measurement("a_b", "UBYTE"),
        ]
    )
    assert "extern uint8_t a_b;" in header
    assert "extern uint8_t a_b_2;" in header


def test_matrix_dim_produces_array_declaration():
    header = generate_header([_measurement("AppStatusListFrame620.app_uid", "UBYTE", matrix_dim=2)])
    assert "extern uint8_t AppStatusListFrame620_app_uid[2];" in header
    assert "/* original A2L name: AppStatusListFrame620.app_uid */" in header


def test_header_has_include_guard_and_stdint_include():
    header = generate_header([_measurement("a", "UBYTE")])
    assert "#ifndef SIGNALS_H" in header
    assert "#define SIGNALS_H" in header
    assert "#endif" in header
    assert "#include <stdint.h>" in header


def test_empty_measurement_list_still_produces_valid_header():
    header = generate_header([])
    assert "#ifndef SIGNALS_H" in header
    assert "#endif" in header
