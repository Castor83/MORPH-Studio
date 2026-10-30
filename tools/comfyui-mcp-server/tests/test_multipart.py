"""Tests for the multipart/form-data encoder used by the upload endpoint."""

from comfy_core import encode_multipart


def encode(fields=None, **kwargs):
    defaults = dict(
        fields=fields if fields is not None else {},
        file_field="image",
        filename="frame.png",
        content=b"\x89PNG\r\n\x1a\n fake",
    )
    defaults.update(kwargs)
    return encode_multipart(**defaults)


def test_form_values_are_encoded_as_text_not_json():
    """ComfyUI parses form fields as text: a JSON bool would arrive as 'True'."""
    content_type, body = encode({"overwrite": "true", "type": "input"})

    assert b'name="overwrite"\r\n\r\ntrue\r\n' in body
    assert b"True" not in body, "Python's bool repr must never reach the wire"


def test_the_boundary_in_the_header_matches_the_one_in_the_body():
    content_type, body = encode({"type": "input"})

    assert content_type.startswith("multipart/form-data; boundary=")
    boundary = content_type.split("boundary=")[1]
    assert body.startswith(f"--{boundary}\r\n".encode())
    assert body.endswith(f"--{boundary}--\r\n".encode())


def test_the_file_part_carries_its_filename_and_content():
    content_type, body = encode(filename="shot_01.png", content=b"BYTES-HERE")

    assert b'name="image"; filename="shot_01.png"' in body
    assert b"BYTES-HERE" in body


def test_the_mime_type_is_derived_from_the_filename():
    _, png = encode(filename="frame.png")
    _, jpg = encode(filename="frame.jpg")

    assert b"Content-Type: image/png" in png
    assert b"Content-Type: image/jpeg" in jpg


def test_an_unknown_extension_falls_back_to_octet_stream():
    _, body = encode(filename="frame.unknownext")

    assert b"Content-Type: application/octet-stream" in body


def test_the_body_is_bytes_so_binary_content_survives():
    """Encoding to str would corrupt any byte the codec cannot round-trip."""
    raw = bytes(range(256))
    _, body = encode(content=raw)

    assert isinstance(body, bytes)
    assert raw in body


def test_fields_with_no_value_are_omitted_entirely():
    _, body = encode({"subfolder": None, "type": "input"})

    assert b'name="subfolder"' not in body
    assert b'name="type"' in body


def test_a_filename_with_quotes_does_not_break_the_header():
    """An embedded quote would terminate the header value early."""
    _, body = encode(filename='we"ird.png')

    assert b'filename="weird.png"' in body
