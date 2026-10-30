"""Listing input images must cover subfolders, which object_info cannot see.

LoadImage.INPUT_TYPES enumerates os.listdir(input_dir), which is not recursive.
A file uploaded into a subfolder is perfectly usable by LoadImage but never
appears there, so listing from object_info alone reports a working file as
missing - the opposite of what this tool is for.
"""

import asyncio
import json

import pytest

import comfy_core
from upload_tools import (
    ListInputImagesInput,
    comfyui_list_input_images,
    scan_input_subfolders,
)


def run(coro):
    return json.loads(asyncio.run(coro))


@pytest.fixture
def input_dir(tmp_path):
    d = tmp_path / "input"
    d.mkdir()
    return d


def make_image(directory, relative_name):
    path = directory / relative_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n data")
    return path


# ---------------------------------------------------------------------------
# Scanning subfolders
# ---------------------------------------------------------------------------

def test_a_file_in_a_subfolder_is_found(input_dir):
    make_image(input_dir, "keyframes/shot_01.png")

    assert scan_input_subfolders(input_dir) == ["keyframes/shot_01.png"]


def test_scanned_names_use_forward_slashes_on_every_platform(input_dir):
    make_image(input_dir, "keyframes/scene_01/shot_01.png")

    assert scan_input_subfolders(input_dir) == ["keyframes/scene_01/shot_01.png"]


def test_root_level_files_are_left_to_object_info(input_dir):
    """object_info is authoritative for the root; scanning it too would duplicate."""
    make_image(input_dir, "root_level.png")
    make_image(input_dir, "keyframes/nested.png")

    assert scan_input_subfolders(input_dir) == ["keyframes/nested.png"]


def test_non_image_files_are_ignored(input_dir):
    make_image(input_dir, "keyframes/keyframe.png")
    (input_dir / "keyframes" / "notes.txt").write_text("not an image")

    assert scan_input_subfolders(input_dir) == ["keyframes/keyframe.png"]


def test_a_missing_input_directory_yields_nothing_rather_than_raising(tmp_path):
    assert scan_input_subfolders(tmp_path / "nope") == []
    assert scan_input_subfolders(None) == []


# ---------------------------------------------------------------------------
# The tool merges both sources
# ---------------------------------------------------------------------------

class FakeComfy:
    def __init__(self, names):
        self.names = names

    def get(self, path, timeout=10):
        return {"LoadImage": {"input": {"required": {
            "image": [list(self.names), {"image_upload": True}]}}}}


@pytest.fixture
def comfy(monkeypatch, tmp_path):
    fake = FakeComfy(["root_level.png"])
    monkeypatch.setattr(comfy_core, "http_get_json", fake.get)
    # The input dir is derived from the configured output dir.
    comfy_core.configure("http://127.0.0.1:8188", str(tmp_path / "output"))
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "input").mkdir(exist_ok=True)
    return fake


def test_listing_includes_both_root_files_and_subfolder_files(comfy, tmp_path):
    make_image(tmp_path / "input", "keyframes/shot_01.png")

    result = run(comfyui_list_input_images(ListInputImagesInput()))

    assert result["images"] == ["keyframes/shot_01.png", "root_level.png"]
    assert result["total"] == 2


def test_a_subfolder_upload_is_findable_by_filter(comfy, tmp_path):
    """The spec's checklist: list_input_images(filter='shot') finds the keyframe."""
    make_image(tmp_path / "input", "mcp/shot_01_keyframe.png")

    result = run(comfyui_list_input_images(ListInputImagesInput(filter="shot")))

    assert result["images"] == ["mcp/shot_01_keyframe.png"]
    assert result["matched"] == 1


def test_a_name_is_not_listed_twice_if_both_sources_report_it(comfy, tmp_path):
    comfy.names = ["root_level.png", "keyframes/shot_01.png"]
    make_image(tmp_path / "input", "keyframes/shot_01.png")

    result = run(comfyui_list_input_images(ListInputImagesInput()))

    assert result["images"].count("keyframes/shot_01.png") == 1


def test_listing_says_so_when_subfolders_could_not_be_scanned(comfy):
    """Without an output dir the input dir cannot be derived; say so rather than
    implying the root-level list is the whole story."""
    comfy_core.configure("http://127.0.0.1:8188", None)

    result = run(comfyui_list_input_images(ListInputImagesInput()))

    assert result["ok"] is True
    assert result["images"] == ["root_level.png"]
    assert "subfolder" in result.get("note", "").lower()
