"""Tests for the five workflow MCP tools, against a fake ComfyUI HTTP layer."""

import asyncio
import json

import pytest

import comfy_core
import workflow_tools
from workflow_tools import (
    CancelInput,
    GetOutputsInput,
    PollWorkflowInput,
    RunWorkflowInput,
    comfyui_cancel,
    comfyui_get_outputs,
    comfyui_list_queue,
    comfyui_poll_workflow,
    comfyui_run_workflow,
)

API_WORKFLOW = {
    "6": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20}},
    "92": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "clip"}},
}


def run(coro):
    return json.loads(asyncio.run(coro))


class FakeComfy:
    """Records what the server sent and replies with canned responses."""

    def __init__(self):
        self.posts = []
        self.history = {}
        self.queue = {"queue_running": [], "queue_pending": []}
        self.post_response = {"prompt_id": "abc-123", "number": 3, "node_errors": {}}
        self.error = None

    def get(self, path, timeout=10):
        if self.error:
            raise self.error
        if path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[1]
            entry = self.history.get(prompt_id)
            return {prompt_id: entry} if entry else {}
        if path == "/queue":
            return self.queue
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, payload, timeout=30):
        if self.error:
            raise self.error
        self.posts.append((path, payload))
        return self.post_response


@pytest.fixture
def comfy(monkeypatch, tmp_path):
    fake = FakeComfy()
    monkeypatch.setattr(comfy_core, "http_get_json", fake.get)
    monkeypatch.setattr(comfy_core, "http_post_json", fake.post)
    comfy_core.configure("http://127.0.0.1:8188", str(tmp_path / "output"))
    workflow_tools.WORKFLOW_JOBS.clear()
    return fake


@pytest.fixture
def workflow_file(tmp_path):
    path = tmp_path / "my_workflow.json"
    path.write_text(json.dumps(API_WORKFLOW))
    return str(path)


# ---------------------------------------------------------------------------
# comfyui_run_workflow
# ---------------------------------------------------------------------------

def test_submitting_a_valid_workflow_returns_a_prompt_id(comfy, workflow_file):
    result = run(comfyui_run_workflow(RunWorkflowInput(
        workflow_path=workflow_file, label="shot_01")))

    assert result["ok"] is True
    assert result["prompt_id"] == "abc-123"
    assert result["label"] == "shot_01"
    assert "comfyui_poll_workflow" in result["next"]


def test_submission_sends_the_graph_and_a_stable_client_id(comfy, workflow_file):
    run(comfyui_run_workflow(RunWorkflowInput(workflow_path=workflow_file)))
    run(comfyui_run_workflow(RunWorkflowInput(workflow_path=workflow_file)))

    paths = [p for p, _ in comfy.posts]
    payloads = [body for _, body in comfy.posts]
    assert paths == ["/prompt", "/prompt"]
    assert payloads[0]["prompt"]["6"]["class_type"] == "KSampler"
    assert payloads[0]["client_id"] == payloads[1]["client_id"]


def test_a_ui_format_workflow_is_rejected_and_nothing_is_queued(comfy, tmp_path):
    ui_file = tmp_path / "ui_workflow.json"
    ui_file.write_text(json.dumps({"nodes": [{"id": 6}], "links": []}))

    result = run(comfyui_run_workflow(RunWorkflowInput(workflow_path=str(ui_file))))

    assert result["ok"] is False
    assert "Export (API)" in result["error"]
    assert comfy.posts == [], "a UI-format workflow must never reach /prompt"


def test_node_errors_come_back_verbatim(comfy, workflow_file):
    comfy.post_response = {
        "prompt_id": "", "number": 0,
        "node_errors": {"6": {"errors": [
            {"type": "value_not_in_list", "message": "Value not in list",
             "details": "ckpt_name: 'missing.safetensors' not in [...]"}]}},
    }

    result = run(comfyui_run_workflow(RunWorkflowInput(workflow_path=workflow_file)))

    assert result["ok"] is False
    assert result["node_errors"]["6"]["errors"][0]["details"].startswith("ckpt_name")


def test_unparseable_json_names_the_file_and_queues_nothing(comfy, tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")

    result = run(comfyui_run_workflow(RunWorkflowInput(workflow_path=str(broken))))

    assert result["ok"] is False
    assert "broken.json" in result["error"]
    assert comfy.posts == []


def test_a_missing_workflow_file_is_reported_clearly(comfy, tmp_path):
    result = run(comfyui_run_workflow(RunWorkflowInput(
        workflow_path=str(tmp_path / "nope.json"))))

    assert result["ok"] is False
    assert "not found" in result["error"].lower()
    assert comfy.posts == []


def test_overrides_reach_the_submitted_graph(comfy, workflow_file):
    run(comfyui_run_workflow(RunWorkflowInput(
        workflow_path=workflow_file, overrides={"6.seed": 42})))

    assert comfy.posts[0][1]["prompt"]["6"]["inputs"]["seed"] == 42


def test_a_bad_override_is_rejected_before_submission(comfy, workflow_file):
    result = run(comfyui_run_workflow(RunWorkflowInput(
        workflow_path=workflow_file, overrides={"999.seed": 42})))

    assert result["ok"] is False
    assert comfy.posts == []


def test_comfyui_being_down_gives_an_actionable_message(comfy, workflow_file):
    comfy.error = ConnectionError(
        "ComfyUI is not reachable at http://127.0.0.1:8188. Is it running?")

    result = run(comfyui_run_workflow(RunWorkflowInput(workflow_path=workflow_file)))

    assert result["ok"] is False
    assert "not reachable" in result["error"]


# ---------------------------------------------------------------------------
# comfyui_poll_workflow
# ---------------------------------------------------------------------------

def test_polling_a_finished_job_reports_completed(comfy):
    comfy.history["abc-123"] = {
        "status": {"status_str": "success", "completed": True, "messages": []},
        "outputs": {"92": {"videos": [{"filename": "clip_00001.mp4",
                                       "subfolder": "", "type": "output"}]}},
    }

    result = run(comfyui_poll_workflow(PollWorkflowInput(prompt_id="abc-123")))

    assert result["status"] == "completed"
    assert "comfyui_get_outputs" in result["next"]


def test_polling_a_failed_job_returns_the_messages_that_explain_it(comfy):
    comfy.history["abc-123"] = {
        "status": {"status_str": "error", "completed": False, "messages": [
            ["execution_error", {"exception_message": "CUDA out of memory"}]]},
        "outputs": {},
    }

    result = run(comfyui_poll_workflow(PollWorkflowInput(prompt_id="abc-123")))

    assert result["status"] == "error"
    assert "CUDA out of memory" in json.dumps(result["messages"])


def test_an_out_of_memory_failure_suggests_the_actual_fix(comfy):
    comfy.history["abc-123"] = {
        "status": {"status_str": "error", "completed": False, "messages": [
            ["execution_error", {"exception_message": "Allocation on device: CUDA out of memory"}]]},
        "outputs": {},
    }

    result = run(comfyui_poll_workflow(PollWorkflowInput(prompt_id="abc-123")))

    assert "hint" in result
    assert "resolution" in result["hint"].lower() or "shorter" in result["hint"].lower()


def test_polling_a_running_job_reports_running_without_blocking(comfy):
    comfy.queue["queue_running"] = [[3, "abc-123", {}, {}, []]]

    result = run(comfyui_poll_workflow(PollWorkflowInput(prompt_id="abc-123")))

    assert result["status"] == "running"


def test_polling_a_queued_job_reports_its_position(comfy):
    comfy.queue["queue_running"] = [[3, "running-one", {}, {}, []]]
    comfy.queue["queue_pending"] = [
        [4, "first-pending", {}, {}, []],
        [5, "abc-123", {}, {}, []],
    ]

    result = run(comfyui_poll_workflow(PollWorkflowInput(prompt_id="abc-123")))

    assert result["status"] == "pending"
    assert result["queue_position"] == 2
    assert result["queue_remaining"] == 3


def test_polling_an_unknown_id_returns_unknown_rather_than_raising(comfy):
    result = run(comfyui_poll_workflow(PollWorkflowInput(prompt_id="never-existed")))

    assert result["ok"] is True
    assert result["status"] == "unknown"


def test_poll_reports_elapsed_time_for_a_job_this_server_submitted(comfy, workflow_file):
    run(comfyui_run_workflow(RunWorkflowInput(workflow_path=workflow_file, label="shot_01")))
    comfy.queue["queue_running"] = [[3, "abc-123", {}, {}, []]]

    result = run(comfyui_poll_workflow(PollWorkflowInput(prompt_id="abc-123")))

    assert result["elapsed_seconds"] >= 0
    assert result["label"] == "shot_01"


# ---------------------------------------------------------------------------
# comfyui_get_outputs
# ---------------------------------------------------------------------------

def test_get_outputs_returns_a_savevideo_mp4(comfy, tmp_path):
    video = tmp_path / "output" / "Scene_04" / "shot_01_00001.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"v" * 512)
    comfy.history["abc-123"] = {
        "status": {"status_str": "success", "completed": True, "messages": []},
        "outputs": {"92": {"videos": [{"filename": "shot_01_00001.mp4",
                                       "subfolder": "Scene_04", "type": "output"}]}},
    }

    result = run(comfyui_get_outputs(GetOutputsInput(prompt_id="abc-123")))

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["outputs"][0]["path"] == str(video)
    assert result["outputs"][0]["bytes"] == 512


def test_get_outputs_on_an_unfinished_job_says_so_instead_of_returning_empty(comfy):
    comfy.queue["queue_running"] = [[3, "abc-123", {}, {}, []]]

    result = run(comfyui_get_outputs(GetOutputsInput(prompt_id="abc-123")))

    assert result["ok"] is False
    assert result["status"] == "running"


def test_get_outputs_without_a_configured_output_dir_explains_how_to_set_it(comfy):
    comfy_core.configure("http://127.0.0.1:8188", None)
    comfy.history["abc-123"] = {
        "status": {"status_str": "success", "completed": True, "messages": []},
        "outputs": {"92": {"videos": [{"filename": "clip.mp4", "subfolder": "", "type": "output"}]}},
    }

    result = run(comfyui_get_outputs(GetOutputsInput(prompt_id="abc-123")))

    assert result["ok"] is False
    assert "--comfyui-output-dir" in result["error"]


# ---------------------------------------------------------------------------
# comfyui_list_queue
# ---------------------------------------------------------------------------

def test_list_queue_reports_running_and_pending_with_known_labels(comfy, workflow_file):
    run(comfyui_run_workflow(RunWorkflowInput(workflow_path=workflow_file, label="shot_01")))
    comfy.queue["queue_running"] = [[3, "abc-123", {}, {}, []]]
    comfy.queue["queue_pending"] = [[4, "other-job", {}, {}, []]]

    result = run(comfyui_list_queue())

    assert result["queue_remaining"] == 2
    assert result["running"][0]["prompt_id"] == "abc-123"
    assert result["running"][0]["label"] == "shot_01"
    assert result["pending"][0]["label"] is None


def test_list_queue_on_an_empty_queue_is_fine(comfy):
    result = run(comfyui_list_queue())

    assert result["ok"] is True
    assert result["queue_remaining"] == 0


# ---------------------------------------------------------------------------
# comfyui_cancel
# ---------------------------------------------------------------------------

def test_cancel_with_no_arguments_is_refused_and_cancels_nothing(comfy):
    result = run(comfyui_cancel(CancelInput()))

    assert result["ok"] is False
    assert comfy.posts == [], "a no-argument cancel must not touch the queue"


def test_cancel_deletes_a_pending_job_by_id(comfy):
    result = run(comfyui_cancel(CancelInput(prompt_id="abc-123")))

    assert result["ok"] is True
    assert comfy.posts == [("/queue", {"delete": ["abc-123"]})]


def test_interrupt_running_stops_the_current_job(comfy):
    run(comfyui_cancel(CancelInput(interrupt_running=True)))

    assert comfy.posts[0][0] == "/interrupt"


def test_clear_pending_empties_the_queue(comfy):
    run(comfyui_cancel(CancelInput(clear_pending=True)))

    assert ("/queue", {"clear": True}) in comfy.posts
