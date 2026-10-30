"""
Image upload tools for the ComfyUI MCP server.

LoadImage resolves its `image` value against ComfyUI's own input/ directory,
not against the filesystem: handing it an absolute path fails with
"Invalid image file". These tools get local files into input/ over HTTP and
hand back the exact string a LoadImage node expects.

Uploading over /upload/image rather than writing into input/ directly means the
server never needs to know where ComfyUI is installed, and keeps working if
ComfyUI moves to another host.
"""

import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

import comfy_core
from comfy_core import mcp

MAX_UPLOAD_FILES = 50


# ============================================================================
# Helpers
# ============================================================================

def build_load_image_name(name: str, subfolder: Optional[str]) -> str:
    """Build the string a LoadImage node's `image` field expects.

    Forward slashes regardless of OS: this is a ComfyUI-internal key, not a
    filesystem path, and a backslash will simply not match.
    """
    if not subfolder:
        return name
    normalised = str(subfolder).replace("\\", "/").strip("/")
    return f"{normalised}/{name}" if normalised else name


def extract_input_image_names(object_info: dict) -> list:
    """Pull the available input filenames out of /object_info/LoadImage.

    The names are the enumeration in the image input spec, roughly
    ["input"]["required"]["image"][0]. The exact nesting has moved between
    ComfyUI versions, so every step is checked rather than indexed blindly.
    """
    node = (object_info or {}).get("LoadImage")
    if not isinstance(node, dict):
        return []

    inputs = node.get("input")
    if not isinstance(inputs, dict):
        return []

    for section in ("required", "optional"):
        spec = (inputs.get(section) or {}).get("image")
        if not isinstance(spec, (list, tuple)) or not spec:
            continue
        candidates = spec[0]
        if isinstance(candidates, (list, tuple)):
            return [str(name) for name in candidates]

    return []


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}


def scan_input_subfolders(input_dir) -> list:
    """List image files sitting in subfolders of ComfyUI's input directory.

    LoadImage's enumeration comes from a non-recursive os.listdir, so files in
    subfolders never appear in object_info even though LoadImage loads them
    happily. Without this, a working upload would be reported as missing.

    Root-level files are skipped: object_info already covers those, and it is
    the authoritative answer for what the node's dropdown offers.
    """
    if not input_dir:
        return []

    root = Path(input_dir)
    if not root.is_dir():
        return []

    names = []
    try:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if len(relative.parts) == 1:
                continue  # root level, already covered by object_info
            names.append(relative.as_posix())
    except OSError:
        return []

    return sorted(names)


def _ok(**fields) -> str:
    return json.dumps({"ok": True, **fields}, indent=2)


def _fail(error: str, **fields) -> str:
    return json.dumps({"ok": False, "error": error, **fields}, indent=2)


# ============================================================================
# Input Models
# ============================================================================

class UploadImageInput(BaseModel):
    """Input parameters for uploading images into ComfyUI's input directory."""

    model_config = ConfigDict(extra="forbid")

    paths: List[str] = Field(
        ...,
        description="Absolute paths to local image files to upload (1-50).",
        min_length=1,
        max_length=MAX_UPLOAD_FILES,
    )
    subfolder: Optional[str] = Field(
        default=None,
        description=(
            "Subfolder under ComfyUI's input directory, e.g. 'keyframes'. Created "
            "automatically. Use it to keep projects separate."
        ),
    )
    overwrite: bool = Field(
        default=True,
        description=(
            "Replace an existing file of the same name. Defaults to true: "
            "regenerated keyframes are re-uploaded constantly, and silently "
            "keeping a stale image is a nasty bug to chase. With false, ComfyUI "
            "renames on collision and the returned name reflects that."
        ),
    )


class ListInputImagesInput(BaseModel):
    """Input parameters for listing ComfyUI's input directory."""

    model_config = ConfigDict(extra="forbid")

    filter: Optional[str] = Field(
        default=None,
        description="Case-insensitive substring to match against the filenames.",
    )


# ============================================================================
# Tools
# ============================================================================

@mcp.tool(
    name="comfyui_upload_image",
    annotations={
        "title": "Upload Images to ComfyUI",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def comfyui_upload_image(params: UploadImageInput) -> str:
    """
    Upload local image files into ComfyUI's input directory.

    Use this before running any workflow with a LoadImage node. LoadImage
    resolves its `image` value against ComfyUI's input directory, not against
    the filesystem, so an absolute path fails with "Invalid image file". This
    returns a `load_image_name` per file, which goes straight into a workflow's
    LoadImage.inputs.image - for example via comfyui_run_workflow's overrides:

        overrides={"12.image": "keyframes/shot_01.png"}

    A file that cannot be read is reported in `failed` while the rest still
    upload; one bad path never aborts the batch.

    Args:
        params: UploadImageInput containing:
            - paths (list[str]): 1-50 absolute paths to local image files
            - subfolder (str, optional): subfolder under input/, e.g. 'keyframes'
            - overwrite (bool): replace a file of the same name (default true)

    Returns:
        JSON with an `uploaded` list (path, load_image_name, name, subfolder,
        bytes) and a `failed` list (path, error).
    """
    uploaded = []
    failed = []

    for raw_path in params.paths:
        path = Path(raw_path)

        try:
            if not path.exists():
                failed.append({"path": str(path), "error": "File not found."})
                continue
            if not path.is_file():
                failed.append({"path": str(path), "error": "Path is not a file."})
                continue
            content = path.read_bytes()
        except OSError as e:
            failed.append({"path": str(path), "error": f"Could not read the file: {e}"})
            continue

        if not content:
            failed.append({"path": str(path), "error": "File is empty."})
            continue

        try:
            response = comfy_core.http_post_multipart(
                "/upload/image",
                {
                    "subfolder": params.subfolder,
                    "type": "input",
                    # A string, deliberately: ComfyUI parses form fields as
                    # text, so a bool would arrive as "True" and not match.
                    "overwrite": "true" if params.overwrite else "false",
                },
                file_field="image",
                filename=path.name,
                content=content,
            )
        except ConnectionError as e:
            failed.append({"path": str(path), "error": str(e)})
            continue

        # Trust the name ComfyUI reports, never the one we sent: it renames on
        # collision when overwrite is false.
        name = response.get("name") or path.name
        subfolder = response.get("subfolder") or ""

        uploaded.append({
            "path": str(path),
            "load_image_name": build_load_image_name(name, subfolder),
            "name": name,
            "subfolder": subfolder,
            "bytes": len(content),
        })

    result = {
        "uploaded": uploaded,
        "failed": failed,
        "uploaded_count": len(uploaded),
        "failed_count": len(failed),
    }

    if not uploaded:
        return _fail(
            "No files were uploaded. See failed for the reason on each path.",
            **result,
        )

    example = uploaded[0]["load_image_name"]
    result["next"] = (
        "Put load_image_name into your workflow's LoadImage.inputs.image, e.g. "
        "comfyui_run_workflow(..., overrides={'<node_id>.image': "
        + repr(example) + "})"
    )

    return _ok(**result)


@mcp.tool(
    name="comfyui_list_input_images",
    annotations={
        "title": "List ComfyUI Input Images",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def comfyui_list_input_images(params: ListInputImagesInput) -> str:
    """
    List the images already in ComfyUI's input directory.

    Names are read from ComfyUI itself, so they are exactly the values a
    LoadImage node will accept. Use this when a workflow reports "Invalid image
    file": it shows whether the name is absent, sitting under a different
    subfolder, or simply spelled differently.

    Args:
        params: ListInputImagesInput containing:
            - filter (str, optional): case-insensitive substring to match

    Returns:
        JSON with the matching names, how many matched, and the total available.
    """
    try:
        info = comfy_core.http_get_json("/object_info/LoadImage")
    except ConnectionError as e:
        return _fail(str(e))

    # object_info is authoritative for root-level files, but its enumeration
    # comes from a non-recursive listing, so subfolder uploads are added from a
    # local scan of input/ - read-only, and skipped if it cannot be located.
    input_dir = comfy_core.get_input_dir()
    names = sorted(
        set(extract_input_image_names(info)) | set(scan_input_subfolders(input_dir))
    )

    notes = []
    if input_dir is None:
        notes.append(
            "Images inside subfolders of input/ are not covered: ComfyUI's node "
            "definition only enumerates the top level, and the input directory "
            "could not be located locally to scan it. Set --comfyui-output-dir "
            "so its sibling input/ can be read."
        )

    if not names:
        notes.append(
            "ComfyUI reported no images in its input directory. If you expected "
            "some, upload them with comfyui_upload_image."
        )

    matches = names
    if params.filter:
        needle = params.filter.lower()
        matches = [name for name in names if needle in name.lower()]
        if not matches:
            notes.append(
                f"No input image matches '{params.filter}'. {len(names)} images "
                "are available; call again without a filter to see them."
            )

    result = {
        "images": matches,
        "matched": len(matches),
        "total": len(names),
    }
    if notes:
        result["note"] = " ".join(notes)

    return _ok(**result)
