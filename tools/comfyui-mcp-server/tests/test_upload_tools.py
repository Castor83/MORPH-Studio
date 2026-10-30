"""Tests for comfyui_upload_image and comfyui_list_input_images."""

import asyncio
import json

import pytest
from pydantic import ValidationError

import comfy_core
from upload_tools import (
    ListInputImagesInput,
    UploadImageInput,
    build_load_image_name,
    comfyui_list_input_images,
    comfyui_upload_image,
    extract_input_image_names,
)


def run(coro):
    return json.loads(asyncio.run(coro))


class FakeComfy:
    """Records uploads and replies the way ComfyUI's /upload/image does."""

    def __init__(self):
        self.uploads = []
        self.rename_to = None          # simulate a collision rename
        self.object_info = {"LoadImage": {"input": {"required": {
            "image": [["existing.png", "shot_01.png", "keyframes/shot_02.png"],
                      {"image_upload": True}]}}}}
        self.error = None

    def post_multipart(self, path, fields, file_field, filename, content, timeout=60):
        if self.error:
            raise self.error
        self.uploads.append({"path": path, "fields": dict(fields),
                             "filename": filename, "content": content})
        return {"name": self.rename_to or filename,
                "subfolder": fields.get("subfolder") or "",
                "type": "input"}

    def get(self, path, timeout=10):
        if self.error:
            raise self.error
        if path.startswith("/object_info/LoadImage"):
            return self.object_info
        raise AssertionError(f"unexpected GET {path}")


@pytest.fixture
def comfy(monkeypatch, tmp_path):
    fake = FakeComfy()
    monkeypatch.setattr(comfy_core, "http_post_multipart", fake.post_multipart)
    monkeypatch.setattr(comfy_core, "http_get_json", fake.get)
    comfy_core.configure("http://127.0.0.1:8188", str(tmp_path / "output"))
    return fake


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "shot_01.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"pixels" * 20)
    return str(path)


# ---------------------------------------------------------------------------
# LoadImage reference building
# ---------------------------------------------------------------------------

def test_a_subfolder_reference_uses_a_forward_slash_even_on_windows():
    """This is a ComfyUI-internal key, not a filesystem path."""
    assert build_load_image_name("shot_01.png", "keyframes") == "keyframes/shot_01.png"


def test_a_reference_without_a_subfolder_is_just_the_name():
    assert build_load_image_name("shot_01.png", "") == "shot_01.png"
    assert build_load_image_name("shot_01.png", None) == "shot_01.png"


def test_a_nested_subfolder_keeps_forward_slashes():
    assert build_load_image_name("a.png", "keyframes\\scene_01") == "keyframes/scene_01/a.png"


# ---------------------------------------------------------------------------
# comfyui_upload_image
# ---------------------------------------------------------------------------

def test_uploading_returns_a_ready_to_use_load_image_name(comfy, png):
    result = run(comfyui_upload_image(UploadImageInput(paths=[png])))

    assert result["ok"] is True
    assert result["uploaded"][0]["load_image_name"] == "shot_01.png"
    assert result["uploaded"][0]["bytes"] > 0
    assert result["failed"] == []


def test_a_subfolder_is_sent_and_reflected_in_the_reference(comfy, png):
    result = run(comfyui_upload_image(UploadImageInput(paths=[png], subfolder="keyframes")))

    assert comfy.uploads[0]["fields"]["subfolder"] == "keyframes"
    assert result["uploaded"][0]["load_image_name"] == "keyframes/shot_01.png"


def test_overwrite_is_sent_as_the_string_true_not_a_bool(comfy, png):
    """ComfyUI parses form fields as text; a bool would arrive as 'True'."""
    run(comfyui_upload_image(UploadImageInput(paths=[png], overwrite=True)))

    assert comfy.uploads[0]["fields"]["overwrite"] == "true"
    assert not isinstance(comfy.uploads[0]["fields"]["overwrite"], bool)


def test_overwrite_false_is_sent_as_the_string_false(comfy, png):
    run(comfyui_upload_image(UploadImageInput(paths=[png], overwrite=False)))

    assert comfy.uploads[0]["fields"]["overwrite"] == "false"


def test_overwrite_defaults_to_true_so_stale_images_cannot_linger(comfy, png):
    run(comfyui_upload_image(UploadImageInput(paths=[png])))

    assert comfy.uploads[0]["fields"]["overwrite"] == "true"


def test_the_upload_targets_the_input_type(comfy, png):
    run(comfyui_upload_image(UploadImageInput(paths=[png])))

    assert comfy.uploads[0]["fields"]["type"] == "input"
    assert comfy.uploads[0]["path"] == "/upload/image"


def test_the_name_comfyui_returns_wins_over_the_one_we_sent(comfy, png):
    """ComfyUI renames on collision when overwrite is false."""
    comfy.rename_to = "shot_01 (1).png"

    result = run(comfyui_upload_image(UploadImageInput(paths=[png], overwrite=False)))

    assert result["uploaded"][0]["name"] == "shot_01 (1).png"
    assert result["uploaded"][0]["load_image_name"] == "shot_01 (1).png"


def test_a_missing_path_is_reported_while_the_others_still_upload(comfy, png, tmp_path):
    result = run(comfyui_upload_image(UploadImageInput(
        paths=[png, str(tmp_path / "gone.png")])))

    assert len(result["uploaded"]) == 1
    assert len(result["failed"]) == 1
    assert "gone.png" in result["failed"][0]["path"]
    assert result["ok"] is True, "a partial success is still a success"


def test_every_path_failing_is_not_reported_as_ok(comfy, tmp_path):
    result = run(comfyui_upload_image(UploadImageInput(
        paths=[str(tmp_path / "a.png"), str(tmp_path / "b.png")])))

    assert result["ok"] is False
    assert len(result["failed"]) == 2


def test_a_directory_passed_as_a_path_is_a_per_file_failure(comfy, tmp_path):
    result = run(comfyui_upload_image(UploadImageInput(paths=[str(tmp_path)])))

    assert result["ok"] is False
    assert "not a file" in result["failed"][0]["error"].lower()


def test_more_than_fifty_paths_is_rejected(png):
    with pytest.raises(ValidationError):
        UploadImageInput(paths=[png] * 51)


def test_an_empty_path_list_is_rejected(comfy):
    with pytest.raises(ValidationError):
        UploadImageInput(paths=[])


def test_comfyui_being_down_is_reported_per_file_not_as_a_crash(comfy, png):
    comfy.error = ConnectionError("ComfyUI is not reachable at http://127.0.0.1:8188. Is it running?")

    result = run(comfyui_upload_image(UploadImageInput(paths=[png])))

    assert result["ok"] is False
    assert "not reachable" in result["failed"][0]["error"]


# ---------------------------------------------------------------------------
# Reading the available names out of object_info
# ---------------------------------------------------------------------------

def test_names_are_read_from_the_load_image_enumeration():
    info = {"LoadImage": {"input": {"required": {
        "image": [["a.png", "b.png"], {"image_upload": True}]}}}}

    assert extract_input_image_names(info) == ["a.png", "b.png"]

def test_an_unexpected_shape_yields_no_names_rather_than_an_indexerror():
    """The nesting has changed between ComfyUI versions."""
    for broken in ({}, {"LoadImage": {}}, {"LoadImage": {"input": {"required": {}}}},
                   {"LoadImage": {"input": {"required": {"image": []}}}},
                   {"LoadImage": {"input": {"required": {"image": [{}]}}}}):
        assert extract_input_image_names(broken) == []


def test_names_are_found_under_optional_if_that_is_where_they_live():
    info = {"LoadImage": {"input": {"optional": {"image": [["a.png"], {}]}}}}

    assert extract_input_image_names(info) == ["a.png"]


# ---------------------------------------------------------------------------
# comfyui_list_input_images
# ---------------------------------------------------------------------------

def test_listing_returns_every_input_image_with_a_total(comfy):
    result = run(comfyui_list_input_images(ListInputImagesInput()))

    assert result["ok"] is True
    assert result["total"] == 3
    assert "existing.png" in result["images"]


def test_the_filter_is_a_case_insensitive_substring_match(comfy):
    result = run(comfyui_list_input_images(ListInputImagesInput(filter="SHOT")))

    # Sorted: the names come from two sources merged, so the order is made
    # deterministic rather than inherited from either one.
    assert result["images"] == ["keyframes/shot_02.png", "shot_01.png"]
    assert result["matched"] == 2
    assert result["total"] == 3, "total counts everything, not just matches"


def test_a_filter_matching_nothing_says_so_without_failing(comfy):
    result = run(comfyui_list_input_images(ListInputImagesInput(filter="nope")))

    assert result["ok"] is True
    assert result["images"] == []
    assert result["matched"] == 0


def test_comfyui_being_down_gives_an_actionable_message(comfy):
    comfy.error = ConnectionError("ComfyUI is not reachable at http://127.0.0.1:8188. Is it running?")

    result = run(comfyui_list_input_images(ListInputImagesInput()))

    assert result["ok"] is False
    assert "not reachable" in result["error"]
