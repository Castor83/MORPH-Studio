"""
Arbitrary-workflow execution tools for the ComfyUI MCP server.

The MCP transport cancels any tool call after 60 seconds, while real renders
take minutes. So nothing here ever waits for a render: submission returns a
prompt_id immediately, a separate poll tool reports progress, and a third
collects the outputs once the job is done.
"""

import copy
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

import comfy_core
from comfy_core import mcp

# ============================================================================
# Job registry
# ============================================================================

# Jobs this server submitted, keyed by prompt_id. Lets poll and list_queue
# report a label and an elapsed time. ComfyUI itself does not remember either,
# so an id missing from here (server restarted) degrades to null rather than
# to an error.
WORKFLOW_JOBS: dict = {}

MAX_TRACKED_JOBS = 500


# ============================================================================
# Errors
# ============================================================================

class WorkflowError(Exception):
    """A user-fixable problem with a workflow file, its overrides, or the job.

    Carries an optional node_errors payload so ComfyUI's own per-node
    diagnostics can be returned verbatim rather than flattened into a string.
    """

    def __init__(self, message: str, node_errors: dict | None = None):
        super().__init__(message)
        self.message = message
        self.node_errors = node_errors or {}


# ============================================================================
# Workflow graph handling
# ============================================================================

def validate_api_workflow(graph, workflow_path: str) -> None:
    """Reject anything that is not an API-format workflow.

    A UI export is a dict with a "nodes" list; ComfyUI's /prompt endpoint only
    accepts the API format, which is a flat mapping of node id -> node. This is
    by far the most common mistake, so it gets an explicit message.
    """
    if not isinstance(graph, dict):
        raise WorkflowError(
            f"{workflow_path} does not contain a workflow object. Expected an "
            "API-format workflow: a JSON object keyed by node id."
        )

    if "nodes" in graph:
        raise WorkflowError(
            f"This is a UI-format workflow: {workflow_path}. Re-save with "
            "Workflow -> Export (API), or use an API-format file. ComfyUI's "
            "/prompt endpoint cannot run UI exports."
        )

    for node_id, node in graph.items():
        if not isinstance(node, dict) or "class_type" not in node:
            raise WorkflowError(
                f"Node '{node_id}' in {workflow_path} has no class_type. This "
                "does not look like an API-format workflow; re-save with "
                "Workflow -> Export (API)."
            )


def apply_overrides(graph: dict, overrides: dict | None) -> dict:
    """Return a copy of graph with per-run overrides applied.

    Keys are "<node_id>.<input_name>". Node ids can themselves contain dots or
    colons (subgraph-exported ids look like "105:111"), so the key is split on
    its LAST dot. Unknown ids and input names raise rather than being silently
    ignored - a typo that quietly does nothing costs a whole render to notice.
    """
    patched = copy.deepcopy(graph)
    if not overrides:
        return patched

    for key, value in overrides.items():
        node_id, sep, input_name = str(key).rpartition(".")
        if not sep or not node_id or not input_name:
            raise WorkflowError(
                f"Override key '{key}' is malformed. Use 'node_id.input_name', "
                "e.g. '119.seed' or '105:111.value'."
            )

        if node_id not in patched:
            known = ", ".join(sorted(patched.keys())[:40])
            raise WorkflowError(
                f"Override '{key}' names node '{node_id}', which is not in the "
                f"workflow. Node ids present: {known}"
            )

        inputs = patched[node_id].setdefault("inputs", {})
        if input_name not in inputs:
            known = ", ".join(sorted(inputs.keys()))
            raise WorkflowError(
                f"Override '{key}' names input '{input_name}', which node "
                f"'{node_id}' does not have. Inputs present: {known}"
            )

        inputs[input_name] = value

    return patched


# ============================================================================
# Output collection
# ============================================================================

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".exr"}
AUDIO_EXTENSIONS = {".flac", ".wav", ".mp3", ".ogg", ".m4a", ".aac"}


def classify_output(filename: str, key: str) -> str:
    """Name the kind of file this is, preferring the extension over the key.

    The key a node reports under is unreliable: VideoHelperSuite writes .mp4
    files under "gifs", and SaveVideo uses "videos" while SaveImage uses
    "images". The extension is what actually tells you what the file is.
    """
    suffix = Path(filename).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix == ".gif":
        return "animation"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    # Fall back to the reporting key, de-pluralised.
    return key[:-1] if key.endswith("s") else key


def _resolve_dir(entry_type: str, output_dir: Path) -> Path:
    """Map ComfyUI's output type to the directory it actually writes to.

    "temp" holds previews and "input" holds uploads; both sit beside output/
    in a standard install, so resolving them under output/ would be wrong.
    """
    if entry_type == "temp":
        return output_dir.parent / "temp"
    if entry_type == "input":
        return output_dir.parent / "input"
    return output_dir


def collect_outputs(history_entry: dict, output_dir: Path) -> list:
    """Walk every output key of every node and resolve each file on disk.

    Deliberately does not hardcode "images": a job whose only result is a
    SaveVideo .mp4 reports under a different key entirely, and that is exactly
    the case a naive implementation returns empty for.
    """
    output_dir = Path(output_dir)
    collected = []

    for node_id, node_outputs in (history_entry.get("outputs") or {}).items():
        if not isinstance(node_outputs, dict):
            continue

        for key, entries in node_outputs.items():
            if not isinstance(entries, list):
                continue

            for entry in entries:
                # Nodes also report non-file values (text, numbers) under
                # outputs; a file entry is a dict carrying a filename.
                if not isinstance(entry, dict) or not entry.get("filename"):
                    continue

                filename = entry["filename"]
                base = _resolve_dir(entry.get("type", "output"), output_dir)
                subfolder = entry.get("subfolder") or ""
                path = (base / subfolder / filename) if subfolder else (base / filename)

                record = {
                    "node_id": node_id,
                    "kind": classify_output(filename, key),
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": entry.get("type", "output"),
                    "path": str(path),
                    "exists": path.exists(),
                    "bytes": None,
                    "mtime": None,
                    "copied_to": None,
                }

                if record["exists"]:
                    stat = path.stat()
                    record["bytes"] = stat.st_size
                    record["mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    )

                collected.append(record)

    return collected


def copy_outputs(outputs: list, copy_to: str, filename: str | None) -> None:
    """Copy collected outputs into copy_to, recording the destination in place.

    Copies rather than moves: the ComfyUI output stays where ComfyUI put it.
    When several files would land on the same stem, later ones get a _2, _3
    suffix instead of silently overwriting their predecessors.
    """
    dest_dir = Path(copy_to)
    dest_dir.mkdir(parents=True, exist_ok=True)
    used = set()

    for record in outputs:
        source = Path(record["path"])
        if not record["exists"] or not source.exists():
            continue

        stem = filename if filename else source.stem
        target = dest_dir / f"{stem}{source.suffix}"

        # Disambiguate within this call only. Re-running the same job with the
        # same filename overwrites, which is what a caller who picked that name
        # expects; endless _2, _3 copies across runs would just be clutter.
        counter = 2
        while target.name in used:
            target = dest_dir / f"{stem}_{counter}{source.suffix}"
            counter += 1

        used.add(target.name)
        shutil.copy2(source, target)
        record["copied_to"] = str(target)


# ============================================================================
# Queue and history helpers
# ============================================================================

def _prompt_ids(entries) -> list:
    """Pull prompt ids out of a queue list.

    Queue entries are arrays with the prompt_id at index 1. Handled
    positionally but defensively, since a dict form would not be surprising.
    """
    ids = []
    for entry in entries or []:
        if isinstance(entry, (list, tuple)) and len(entry) > 1:
            ids.append(str(entry[1]))
        elif isinstance(entry, dict) and entry.get("prompt_id"):
            ids.append(str(entry["prompt_id"]))
    return ids


def _queue_snapshot() -> tuple:
    """Return (running_ids, pending_ids) from /queue."""
    data = comfy_core.http_get_json("/queue") or {}
    return _prompt_ids(data.get("queue_running")), _prompt_ids(data.get("queue_pending"))


def _history_entry(prompt_id: str) -> Optional[dict]:
    """Return the history record for a prompt_id, or None if it has not finished."""
    data = comfy_core.http_get_json(f"/history/{prompt_id}") or {}
    entry = data.get(prompt_id)
    return entry if isinstance(entry, dict) else None


def _message_timestamps(messages) -> tuple:
    """Extract (start_ms, end_ms) from a history status.messages array."""
    start = end = None
    for message in messages or []:
        if not (isinstance(message, (list, tuple)) and len(message) > 1):
            continue
        kind, payload = message[0], message[1]
        if not isinstance(payload, dict):
            continue
        timestamp = payload.get("timestamp")
        if not isinstance(timestamp, (int, float)):
            continue
        if kind == "execution_start":
            start = timestamp
        elif kind in ("execution_success", "execution_error", "execution_interrupted"):
            end = timestamp
    return start, end


def _elapsed_seconds(prompt_id: str, messages=None) -> Optional[float]:
    """How long the job has taken, preferring ComfyUI's own timestamps."""
    start, end = _message_timestamps(messages)
    if start and end:
        return round((end - start) / 1000.0, 1)

    job = WORKFLOW_JOBS.get(prompt_id)
    if job:
        return round(time.time() - job["submitted_at"], 1)
    return None


def _oom_hint(messages) -> Optional[str]:
    """Turn a CUDA OOM buried in the messages array into the actual fix."""
    blob = json.dumps(messages or []).lower()
    if "out of memory" in blob or "cuda oom" in blob:
        return (
            "The GPU ran out of memory. Render a shorter clip (fewer frames) or "
            "a lower resolution - that is the fix; retrying unchanged will fail "
            "the same way."
        )
    return None


def _remember(prompt_id: str, label: Optional[str], workflow_path: str) -> None:
    """Record a submitted job, trimming the oldest once the registry is full."""
    if len(WORKFLOW_JOBS) >= MAX_TRACKED_JOBS:
        oldest = min(WORKFLOW_JOBS, key=lambda k: WORKFLOW_JOBS[k]["submitted_at"])
        del WORKFLOW_JOBS[oldest]
    WORKFLOW_JOBS[prompt_id] = {
        "label": label,
        "workflow_path": workflow_path,
        "submitted_at": time.time(),
    }


def _label(prompt_id: str) -> Optional[str]:
    job = WORKFLOW_JOBS.get(prompt_id)
    return job["label"] if job else None


def _ok(**fields) -> str:
    return json.dumps({"ok": True, **fields}, indent=2)


def _fail(error: str, **fields) -> str:
    return json.dumps({"ok": False, "error": error, **fields}, indent=2)


# ============================================================================
# Input Models
# ============================================================================

class RunWorkflowInput(BaseModel):
    """Input parameters for submitting a saved workflow."""

    model_config = ConfigDict(extra="forbid")

    workflow_path: str = Field(
        ...,
        description=(
            "Absolute path to an API-format workflow JSON file (a flat object "
            "keyed by node id, each node having class_type and inputs). Save one "
            "from ComfyUI with Workflow -> Export (API). A normal UI export will "
            "be rejected."
        ),
        min_length=1,
    )
    overrides: Optional[dict] = Field(
        default=None,
        description=(
            "Per-run patches applied before submission, keyed "
            "'<node_id>.<input_name>', e.g. {\"119.seed\": 42, \"105:111.value\": 8.0}. "
            "Lets you change seed, duration or prompt without rewriting the file. "
            "Unknown node ids or input names are an error, never silently ignored."
        ),
    )
    label: Optional[str] = Field(
        default=None,
        description="Free-text tag stored with the job for later identification, e.g. 'shot_01'.",
    )


class PollWorkflowInput(BaseModel):
    """Input parameters for polling a submitted job."""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(..., description="The prompt_id returned by comfyui_run_workflow.", min_length=1)


class GetOutputsInput(BaseModel):
    """Input parameters for collecting a finished job's files."""

    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(..., description="The prompt_id returned by comfyui_run_workflow.", min_length=1)
    copy_to: Optional[str] = Field(
        default=None,
        description="Absolute directory to copy the outputs into. The ComfyUI originals are left in place.",
    )
    filename: Optional[str] = Field(
        default=None,
        description="Stem to rename to when copying, e.g. 'shot_01'. The extension is preserved.",
    )


class CancelInput(BaseModel):
    """Input parameters for cancelling jobs. At least one must be given."""

    model_config = ConfigDict(extra="forbid")

    prompt_id: Optional[str] = Field(default=None, description="Delete this job from the pending queue.")
    interrupt_running: bool = Field(default=False, description="Stop the job currently executing.")
    clear_pending: bool = Field(default=False, description="Clear every pending job from the queue.")


# ============================================================================
# Tools
# ============================================================================

@mcp.tool(
    name="comfyui_run_workflow",
    annotations={
        "title": "Run a ComfyUI Workflow",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def comfyui_run_workflow(params: RunWorkflowInput) -> str:
    """
    Submit any saved API-format workflow to ComfyUI and return immediately.

    This does NOT wait for the render. It returns a prompt_id in about a second,
    however long the job itself takes. Video renders run for 10-20 minutes, far
    past the 60 second tool timeout, so waiting here would fail every time after
    the GPU had already done the work.

    The pattern is: run -> poll -> get_outputs.
    1. comfyui_run_workflow(...) -> prompt_id
    2. comfyui_poll_workflow(prompt_id) until status is "completed"
    3. comfyui_get_outputs(prompt_id) to collect the files

    Args:
        params: RunWorkflowInput containing:
            - workflow_path (str): absolute path to an API-format workflow JSON
            - overrides (dict, optional): {"<node_id>.<input_name>": value} patches
            - label (str, optional): free-text tag stored with the job

    Returns:
        JSON with ok, prompt_id, number, label, queue_position and the next call
        to make. On a rejected graph: ok false plus ComfyUI's node_errors verbatim.
    """
    path = Path(params.workflow_path)

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail(f"Workflow file not found: {path}")
    except OSError as e:
        return _fail(f"Could not read workflow file {path}: {e}")

    try:
        graph = json.loads(raw)
    except json.JSONDecodeError as e:
        return _fail(f"Could not parse {path} as JSON: {e}")

    try:
        validate_api_workflow(graph, str(path))
        graph = apply_overrides(graph, params.overrides)
    except WorkflowError as e:
        return _fail(e.message)

    try:
        response = comfy_core.http_post_json(
            "/prompt", {"prompt": graph, "client_id": comfy_core.CLIENT_ID}
        )
    except ConnectionError as e:
        return _fail(str(e))

    node_errors = response.get("node_errors") or {}
    if node_errors:
        return _fail(
            "ComfyUI rejected the workflow. See node_errors for the offending "
            "nodes and fields.",
            node_errors=node_errors,
        )

    prompt_id = response.get("prompt_id")
    if not prompt_id:
        return _fail(
            f"ComfyUI did not return a prompt_id: {json.dumps(response)[:500]}"
        )

    _remember(prompt_id, params.label, str(path))

    # Best effort: a queue position is useful but never worth failing a
    # successful submission over.
    queue_position = None
    try:
        running, pending = _queue_snapshot()
        if prompt_id in running:
            queue_position = 0
        elif prompt_id in pending:
            queue_position = pending.index(prompt_id) + 1
    except ConnectionError:
        pass

    return _ok(
        prompt_id=prompt_id,
        number=response.get("number"),
        label=params.label,
        queue_position=queue_position,
        next=f"comfyui_poll_workflow(prompt_id='{prompt_id}')",
    )


@mcp.tool(
    name="comfyui_poll_workflow",
    annotations={
        "title": "Poll a ComfyUI Workflow Job",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def comfyui_poll_workflow(params: PollWorkflowInput) -> str:
    """
    Report the state of a submitted job. Fast, free and repeatable.

    Call this after comfyui_run_workflow to watch progress. It returns at once
    whatever the job is doing - it never blocks waiting for completion.

    TIMING: video renders take 10-20 minutes. Wait at least 60 seconds between
    calls; polling in a tight loop tells you nothing new.

    Args:
        params: PollWorkflowInput containing:
            - prompt_id (str): the prompt_id from comfyui_run_workflow

    Returns:
        JSON with status ("pending", "running", "completed", "error" or
        "unknown"), queue position, elapsed_seconds, and on failure the
        messages array explaining why.
    """
    prompt_id = params.prompt_id

    try:
        entry = _history_entry(prompt_id)
    except ConnectionError as e:
        return _fail(str(e))

    if entry is not None:
        status_block = entry.get("status") or {}
        messages = status_block.get("messages") or []
        failed = status_block.get("status_str") == "error"

        result = {
            "prompt_id": prompt_id,
            "label": _label(prompt_id),
            "status": "error" if failed else "completed",
            "elapsed_seconds": _elapsed_seconds(prompt_id, messages),
            "messages": messages if failed else [],
        }

        if failed:
            hint = _oom_hint(messages)
            if hint:
                result["hint"] = hint
        else:
            result["next"] = f"comfyui_get_outputs(prompt_id='{prompt_id}')"

        return _ok(**result)

    try:
        running, pending = _queue_snapshot()
    except ConnectionError as e:
        return _fail(str(e))

    queue_remaining = len(running) + len(pending)

    if prompt_id in running:
        return _ok(
            prompt_id=prompt_id,
            label=_label(prompt_id),
            status="running",
            queue_position=0,
            queue_remaining=queue_remaining,
            elapsed_seconds=_elapsed_seconds(prompt_id),
        )

    if prompt_id in pending:
        return _ok(
            prompt_id=prompt_id,
            label=_label(prompt_id),
            status="pending",
            queue_position=pending.index(prompt_id) + 1,
            queue_remaining=queue_remaining,
            elapsed_seconds=_elapsed_seconds(prompt_id),
        )

    return _ok(
        prompt_id=prompt_id,
        label=_label(prompt_id),
        status="unknown",
        queue_remaining=queue_remaining,
        note=(
            "This prompt_id is in neither the queue nor the history. It was "
            "cancelled, or ComfyUI restarted and forgot it."
        ),
    )


@mcp.tool(
    name="comfyui_get_outputs",
    annotations={
        "title": "Get ComfyUI Workflow Outputs",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def comfyui_get_outputs(params: GetOutputsInput) -> str:
    """
    Collect the files a completed job produced, as absolute local paths.

    Walks every output key of every node, so it finds SaveVideo .mp4 files and
    audio just as reliably as SaveImage .png files. The MCP server and ComfyUI
    are on the same machine, so this returns real paths rather than moving
    bytes over HTTP.

    Args:
        params: GetOutputsInput containing:
            - prompt_id (str): the prompt_id from comfyui_run_workflow
            - copy_to (str, optional): absolute directory to copy outputs into
            - filename (str, optional): stem to rename to when copying

    Returns:
        JSON with one entry per output file: node_id, kind, filename, absolute
        path, bytes, mtime and copied_to.
    """
    prompt_id = params.prompt_id

    try:
        entry = _history_entry(prompt_id)
    except ConnectionError as e:
        return _fail(str(e))

    if entry is None:
        try:
            running, pending = _queue_snapshot()
        except ConnectionError as e:
            return _fail(str(e))

        if prompt_id in running:
            return _fail(
                "This job is still running - no outputs yet. Poll it with "
                f"comfyui_poll_workflow(prompt_id='{prompt_id}').",
                prompt_id=prompt_id,
                status="running",
            )
        if prompt_id in pending:
            return _fail(
                "This job has not started yet - no outputs. Poll it with "
                f"comfyui_poll_workflow(prompt_id='{prompt_id}').",
                prompt_id=prompt_id,
                status="pending",
            )
        return _fail(
            "No history for this prompt_id. It was cancelled, or ComfyUI "
            "restarted and forgot it.",
            prompt_id=prompt_id,
            status="unknown",
        )

    status_block = entry.get("status") or {}
    if status_block.get("status_str") == "error":
        messages = status_block.get("messages") or []
        result = {
            "prompt_id": prompt_id,
            "status": "error",
            "messages": messages,
        }
        hint = _oom_hint(messages)
        if hint:
            result["hint"] = hint
        return _fail("This job failed, so it produced no outputs.", **result)

    output_dir = comfy_core.get_output_dir()
    if output_dir is None:
        return _fail(
            "The ComfyUI output directory is not configured, so output files "
            "cannot be resolved to absolute paths. Start the server with "
            "--comfyui-output-dir <path>, or set the COMFYUI_OUTPUT_DIR "
            "environment variable. It is the 'output' folder inside your "
            "ComfyUI installation.",
            prompt_id=prompt_id,
        )

    outputs = collect_outputs(entry, output_dir)

    if params.copy_to:
        try:
            copy_outputs(outputs, params.copy_to, params.filename)
        except OSError as e:
            return _fail(
                f"Collected the outputs but could not copy them to {params.copy_to}: {e}",
                prompt_id=prompt_id,
                outputs=outputs,
            )

    result = {
        "prompt_id": prompt_id,
        "label": _label(prompt_id),
        "status": "completed",
        "output_count": len(outputs),
        "outputs": outputs,
    }

    missing = [o["filename"] for o in outputs if not o["exists"]]
    if missing:
        result["warning"] = (
            f"ComfyUI reported these files but they are not on disk under "
            f"{output_dir}: {', '.join(missing)}. Check that --comfyui-output-dir "
            "points at the ComfyUI install actually serving this server."
        )
    elif not outputs:
        result["warning"] = (
            "The job completed but reported no output files. Its workflow may "
            "have no Save node, or it only produced previews."
        )

    return _ok(**result)


@mcp.tool(
    name="comfyui_list_queue",
    annotations={
        "title": "List the ComfyUI Queue",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def comfyui_list_queue() -> str:
    """
    List what ComfyUI is running and what is waiting.

    Use it to see what is already in flight before adding more work, or to
    recover a prompt_id you lost.

    Returns:
        JSON with the running and pending jobs, each with its prompt_id and the
        label it was submitted with (null for jobs this server did not submit),
        plus queue_remaining.
    """
    try:
        running, pending = _queue_snapshot()
    except ConnectionError as e:
        return _fail(str(e))

    return _ok(
        queue_remaining=len(running) + len(pending),
        running=[{"prompt_id": pid, "label": _label(pid)} for pid in running],
        pending=[
            {"prompt_id": pid, "label": _label(pid), "queue_position": i + 1}
            for i, pid in enumerate(pending)
        ],
    )


@mcp.tool(
    name="comfyui_cancel",
    annotations={
        "title": "Cancel ComfyUI Jobs",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def comfyui_cancel(params: CancelInput) -> str:
    """
    Cancel a pending job, interrupt the running one, or clear the queue.

    Requires at least one argument: a no-argument call is refused so that
    nothing is cancelled by accident.

    Args:
        params: CancelInput containing:
            - prompt_id (str, optional): delete this job from the pending queue
            - interrupt_running (bool): stop the job currently executing
            - clear_pending (bool): clear every pending job

    Returns:
        JSON listing the actions taken.
    """
    if not params.prompt_id and not params.interrupt_running and not params.clear_pending:
        return _fail(
            "Nothing was cancelled: comfyui_cancel needs at least one of "
            "prompt_id, interrupt_running or clear_pending. Refusing a "
            "no-argument call so nothing is cancelled by accident."
        )

    actions = []

    try:
        if params.prompt_id:
            comfy_core.http_post_json("/queue", {"delete": [params.prompt_id]})
            actions.append(f"Deleted pending job {params.prompt_id} from the queue.")

        if params.interrupt_running:
            comfy_core.http_post_json("/interrupt", {})
            actions.append("Interrupted the running job.")

        if params.clear_pending:
            comfy_core.http_post_json("/queue", {"clear": True})
            actions.append("Cleared all pending jobs.")
    except ConnectionError as e:
        return _fail(str(e), actions_taken=actions)

    return _ok(actions=actions)
