"""Tests for collecting the files a finished job produced."""

import pytest

from workflow_tools import collect_outputs, copy_outputs


@pytest.fixture
def output_dir(tmp_path):
    """A stand-in for the ComfyUI output directory."""
    return tmp_path / "output"


def write_output(output_dir, subfolder, filename, content=b"x" * 100):
    target = output_dir / subfolder / filename if subfolder else output_dir / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


# ---------------------------------------------------------------------------
# Walking the outputs dict
# ---------------------------------------------------------------------------

def test_savevideo_output_is_found_although_it_is_not_under_images(output_dir):
    """SaveVideo reports under 'videos'; hardcoding 'images' misses it."""
    write_output(output_dir, "Scene_04", "shot_01_00001.mp4")
    history = {
        "outputs": {
            "92": {"videos": [{"filename": "shot_01_00001.mp4",
                               "subfolder": "Scene_04", "type": "output"}]}
        }
    }

    outputs = collect_outputs(history, output_dir)

    assert len(outputs) == 1
    assert outputs[0]["filename"] == "shot_01_00001.mp4"
    assert outputs[0]["kind"] == "video"
    assert outputs[0]["node_id"] == "92"


def test_mp4_under_the_gifs_key_is_still_classified_as_video(output_dir):
    """VideoHelperSuite reports .mp4 files under 'gifs' - trust the extension."""
    write_output(output_dir, "", "clip_00001.mp4")
    history = {
        "outputs": {
            "60": {"gifs": [{"filename": "clip_00001.mp4",
                             "subfolder": "", "type": "output"}]}
        }
    }

    assert collect_outputs(history, output_dir)[0]["kind"] == "video"


def test_outputs_from_several_nodes_and_keys_are_all_collected(output_dir):
    write_output(output_dir, "", "frame_00001.png")
    write_output(output_dir, "", "clip_00001.webm")
    write_output(output_dir, "", "voice_00001.flac")
    history = {
        "outputs": {
            "9": {"images": [{"filename": "frame_00001.png", "subfolder": "", "type": "output"}]},
            "92": {"videos": [{"filename": "clip_00001.webm", "subfolder": "", "type": "output"}]},
            "70": {"audio": [{"filename": "voice_00001.flac", "subfolder": "", "type": "output"}]},
        }
    }

    kinds = {o["filename"]: o["kind"] for o in collect_outputs(history, output_dir)}

    assert kinds == {
        "frame_00001.png": "image",
        "clip_00001.webm": "video",
        "voice_00001.flac": "audio",
    }


def test_entry_resolves_to_an_absolute_path_under_the_subfolder(output_dir):
    expected = write_output(output_dir, "Scene_04", "shot_01_00001.mp4")
    history = {"outputs": {"92": {"videos": [
        {"filename": "shot_01_00001.mp4", "subfolder": "Scene_04", "type": "output"}]}}}

    assert collect_outputs(history, output_dir)[0]["path"] == str(expected)


def test_size_and_mtime_are_reported_so_a_caller_can_confirm_the_write(output_dir):
    write_output(output_dir, "", "clip_00001.mp4", content=b"y" * 2048)
    history = {"outputs": {"92": {"videos": [
        {"filename": "clip_00001.mp4", "subfolder": "", "type": "output"}]}}}

    entry = collect_outputs(history, output_dir)[0]

    assert entry["exists"] is True
    assert entry["bytes"] == 2048
    assert entry["mtime"].startswith("20")  # ISO-8601 timestamp


def test_a_file_not_on_disk_is_reported_rather_than_dropped(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    history = {"outputs": {"92": {"videos": [
        {"filename": "missing_00001.mp4", "subfolder": "", "type": "output"}]}}}

    entry = collect_outputs(history, output_dir)[0]

    assert entry["exists"] is False
    assert entry["bytes"] is None


def test_temp_previews_resolve_under_the_temp_dir_not_output(output_dir):
    history = {"outputs": {"12": {"images": [
        {"filename": "preview_00001.png", "subfolder": "", "type": "temp"}]}}}

    entry = collect_outputs(history, output_dir)[0]

    assert entry["path"] == str(output_dir.parent / "temp" / "preview_00001.png")


def test_non_file_output_keys_are_ignored(output_dir):
    """Nodes report things like text under outputs too; they are not files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    history = {"outputs": {"15": {"text": ["a caption string"], "value": [4]}}}

    assert collect_outputs(history, output_dir) == []


# ---------------------------------------------------------------------------
# copy_to
# ---------------------------------------------------------------------------

def test_copy_to_copies_and_leaves_the_comfyui_copy_in_place(output_dir, tmp_path):
    source = write_output(output_dir, "", "clip_00001.mp4")
    history = {"outputs": {"92": {"videos": [
        {"filename": "clip_00001.mp4", "subfolder": "", "type": "output"}]}}}
    outputs = collect_outputs(history, output_dir)
    dest_dir = tmp_path / "renders"

    copy_outputs(outputs, str(dest_dir), filename=None)

    assert source.exists(), "the original must survive - copy, never move"
    assert (dest_dir / "clip_00001.mp4").exists()
    assert outputs[0]["copied_to"] == str(dest_dir / "clip_00001.mp4")


def test_filename_renames_the_copy_and_keeps_the_extension(output_dir, tmp_path):
    write_output(output_dir, "", "clip_00001.mp4")
    history = {"outputs": {"92": {"videos": [
        {"filename": "clip_00001.mp4", "subfolder": "", "type": "output"}]}}}
    outputs = collect_outputs(history, output_dir)
    dest_dir = tmp_path / "renders"

    copy_outputs(outputs, str(dest_dir), filename="shot_01")

    assert (dest_dir / "shot_01.mp4").exists()


def test_several_outputs_sharing_one_stem_do_not_overwrite_each_other(output_dir, tmp_path):
    write_output(output_dir, "", "clip_00001.mp4")
    write_output(output_dir, "", "clip_00002.mp4")
    history = {"outputs": {"92": {"videos": [
        {"filename": "clip_00001.mp4", "subfolder": "", "type": "output"},
        {"filename": "clip_00002.mp4", "subfolder": "", "type": "output"}]}}}
    outputs = collect_outputs(history, output_dir)
    dest_dir = tmp_path / "renders"

    copy_outputs(outputs, str(dest_dir), filename="shot_01")

    assert (dest_dir / "shot_01.mp4").exists()
    assert (dest_dir / "shot_01_2.mp4").exists()


def test_a_missing_source_file_is_not_copied_and_is_flagged(output_dir, tmp_path):
    output_dir.mkdir(parents=True, exist_ok=True)
    history = {"outputs": {"92": {"videos": [
        {"filename": "missing_00001.mp4", "subfolder": "", "type": "output"}]}}}
    outputs = collect_outputs(history, output_dir)

    copy_outputs(outputs, str(tmp_path / "renders"), filename=None)

    assert outputs[0]["copied_to"] is None
