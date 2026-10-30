# ComfyUI MCP Server

An MCP (Model Context Protocol) server that enables AI assistants like Claude to generate images using ComfyUI.

By [Sumit Chatterjee](https://github.com/sumitchatterjee13)

## Features

- **Generate Images**: Create images from text prompts using your ComfyUI workflow
- **Run Any Workflow**: Queue any saved API-format workflow — video, audio, upscaling, anything — and collect its outputs
- **Upload Images**: Push local images into ComfyUI's input directory for LoadImage nodes to use
- **Automatic File Handling**: Optionally copy generated images directly to your project
- **Status Checking**: Verify ComfyUI is running before generating
- **List Images**: Browse previously generated images

## Prerequisites

1. **ComfyUI** running locally on `http://127.0.0.1:8188`
2. **Z-Image Turbo model** (or modify `workflow.json` for your model)
3. **Python 3.10+**
4. **Claude Code** or another MCP-compatible client

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/sumitchatterjee13/comfyui-mcp-server.git
```

### 2. Install dependencies

```bash
cd path/to/comfyui-mcp
pip install -r requirements.txt
```

Or with uv (recommended):
```bash
uv pip install -r requirements.txt
```

### 3. Configure your MCP client

Add this server to your MCP client configuration. Examples for popular clients below.

**Claude Code** — global config (`~/.claude.json`):

```json
{
  "mcpServers": {
    "comfyui": {
      "command": "python",
      "args": [
        "C:/Users/YourName/mcp-servers/comfyui-mcp/server.py",
        "--comfyui-url", "http://127.0.0.1:8188",
        "--comfyui-output-dir", "C:/path/to/ComfyUI/output"
      ]
    }
  }
}
```

**Claude Code** — project-level config (`.mcp.json` in your project root):

```json
{
  "mcpServers": {
    "comfyui": {
      "command": "python",
      "args": [
        "C:/Users/YourName/mcp-servers/comfyui-mcp/server.py",
        "--comfyui-url", "http://127.0.0.1:8188",
        "--comfyui-output-dir", "C:/path/to/ComfyUI/output"
      ]
    }
  }
}
```

**Cursor / Kilo Code / Cline / Roo Code** — MCP settings JSON:

```json
{
  "mcpServers": {
    "comfyui": {
      "command": "python",
      "args": [
        "server.py",
        "--comfyui-url", "http://127.0.0.1:8188",
        "--comfyui-output-dir", "C:/path/to/ComfyUI/output"
      ],
      "cwd": "C:/Users/YourName/mcp-servers/comfyui-mcp",
      "alwaysAllow": [
        "generate_image",
        "batch_generate_images",
        "check_batch_status",
        "list_generated_images",
        "check_comfyui_status",
        "convert_to_webp",
        "batch_convert_to_webp",
        "comfyui_run_workflow",
        "comfyui_poll_workflow",
        "comfyui_get_outputs",
        "comfyui_list_queue",
        "comfyui_upload_image",
        "comfyui_list_input_images"
      ]
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "comfyui": {
      "command": "python",
      "args": [
        "C:/Users/YourName/mcp-servers/comfyui-mcp/server.py",
        "--comfyui-url", "http://127.0.0.1:8188",
        "--comfyui-output-dir", "C:/path/to/ComfyUI/output"
      ]
    }
  }
}
```

> **Notes:**
>
> - Replace the paths with the actual location of your `comfyui-mcp` folder.
> - `--comfyui-url` is optional (defaults to `http://127.0.0.1:8188`). Use it to point to ComfyUI on a different port, a LAN machine (`http://192.168.1.50:8188`), or a cloud instance.
> - `--comfyui-output-dir` is the `output` folder inside your ComfyUI installation (e.g. `.../ComfyUI_windows_portable/ComfyUI/output`). It is only needed for `comfyui_get_outputs`, which uses it to turn ComfyUI's relative filenames into absolute paths. Leave it out if you only use the image generation tools.
> - Both can also be set via the `COMFYUI_URL` and `COMFYUI_OUTPUT_DIR` environment variables.
> - `alwaysAllow` is supported by Cursor/Kilo Code/Cline/Roo Code to auto-approve tool calls without prompting each time.
> - `cwd` lets you use a relative path for `server.py` instead of an absolute one.

## Usage

Once configured, you can ask Claude to generate images naturally:

### Basic generation
> "Generate an image of a sunset over mountains"

### With specific dimensions
> "Create a 1920x1080 hero banner image of a modern tech office"

### Save to project
> "Generate a product mockup image and save it to ./public/images/product.png"

### Check status
> "Is ComfyUI running?"

### List previous images
> "Show me the last 5 images I generated"

## Available Tools

### `generate_image`
Generate an image from a text prompt.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | required | Description of the image to generate |
| `save_path` | string | required | Full output path (no extension, forward slashes) |
| `width` | int | 1024 | Image width in pixels (256-4096) |
| `height` | int | 1024 | Image height in pixels (256-4096) |
| `seed` | int | random | Seed for reproducible generation |
| `file_format` | string | "jpg" | Output format: jpg, webp, or png |

### `batch_generate_images`
Queue multiple images (up to 100) for generation. This tool is **non-blocking** — it queues all images to ComfyUI and returns a `batch_id` immediately. Use `check_batch_status` to monitor progress.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `images` | list | required | Array of 1-100 image requests (see below) |

**Each image request:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | required | Description of the image |
| `save_path` | string | required | Unique output path (no extension) |
| `width` | int | 1024 | Image width in pixels (256-4096) |
| `height` | int | 1024 | Image height in pixels (256-4096) |
| `seed` | int | random | Seed for reproducible generation |
| `file_format` | string | "jpg" | Output format: jpg, webp, or png |

**Two-step workflow:**
1. Call `batch_generate_images` → returns `batch_id` immediately
2. Call `check_batch_status` with the `batch_id` → returns progress
3. Repeat step 2 until status is `"completed"`

**Example usage:**
> "Generate 5 product images for the e-commerce site: a leather bag, sneakers, a watch, sunglasses, and a jacket"

### `check_batch_status`
Check the progress of a batch image generation job. Returns current status, completed count, pending count, and results of finished images.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch_id` | string | required | The batch_id from batch_generate_images |

### `list_generated_images`
List recently generated images.

**Parameters:**

| Parameter   | Type   | Default  | Description                        |
|-------------|--------|----------|------------------------------------|
| `directory` | string | required | Directory path to list images from |
| `limit`     | int    | 10       | Maximum images to return           |

### `check_comfyui_status`
Check if ComfyUI is running and accessible. No parameters needed.

## Running Arbitrary Workflows

The tools above drive one built-in image workflow. The tools below run **any** workflow you have saved — video, audio, upscaling, ControlNet, whatever you have built in ComfyUI.

They never block. A video render can take 10–20 minutes, far longer than the 60-second MCP tool timeout, so submission returns a `prompt_id` immediately and progress is polled separately:

```text
comfyui_run_workflow(...)   → prompt_id      (returns in well under a second)
comfyui_poll_workflow(id)   → status         (repeat until "completed")
comfyui_get_outputs(id)     → absolute paths to the rendered files
```

> **Your workflow must be in API format.** In ComfyUI, use **Workflow → Export (API)**, not the normal save. A UI export has a top-level `"nodes"` array and ComfyUI's `/prompt` endpoint cannot run it; `comfyui_run_workflow` detects this and tells you, rather than failing obscurely.

### `comfyui_run_workflow`
Submit a saved workflow and return immediately.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workflow_path` | string | required | Absolute path to an API-format workflow JSON |
| `overrides` | dict | none | Per-run patches keyed `"<node_id>.<input_name>"` |
| `label` | string | none | Free-text tag stored with the job, e.g. `"shot_01"` |

`overrides` lets you change a seed, duration, or prompt without rewriting the file:

```json
{"119.seed": 42, "105:111.value": 8.0, "6.text": "a red bicycle"}
```

Node ids containing colons (from exported subgraphs) work fine — the key is split on its last dot. An unknown node id or input name is an error listing the valid ones, never a silent no-op.

Returns `prompt_id`, `number`, `queue_position`, and the next call to make. If ComfyUI rejects the graph, its `node_errors` come back verbatim, naming the offending node and field.

### `comfyui_poll_workflow`
Report the state of a submitted job. Fast, free, and repeatable — it never waits for the render.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt_id` | string | required | The `prompt_id` from `comfyui_run_workflow` |

Returns `status` (`pending`, `running`, `completed`, `error`, or `unknown`), queue position, and `elapsed_seconds`. On failure it returns ComfyUI's `messages` array, which is what actually explains the failure; a CUDA out-of-memory error also gets a hint pointing at the real fix.

`unknown` means the id is in neither the queue nor the history — the job was cancelled, or ComfyUI restarted and forgot it.

### `comfyui_get_outputs`
Collect the files a completed job produced, as absolute local paths.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt_id` | string | required | The `prompt_id` from `comfyui_run_workflow` |
| `copy_to` | string | none | Absolute directory to copy the outputs into |
| `filename` | string | none | Stem to rename to when copying (extension preserved) |

Walks every output key of every node, so it finds `SaveVideo` `.mp4` files and audio just as reliably as `SaveImage` `.png` files. Each entry carries the node id, kind, absolute path, size and mtime, so you can confirm the write finished. `copy_to` copies — the ComfyUI original stays where ComfyUI put it.

Requires `--comfyui-output-dir` to be configured.

### `comfyui_list_queue`
List what ComfyUI is running and what is waiting, with the label each job was submitted with. No parameters. Useful for seeing what is in flight before adding more, or recovering a `prompt_id` you lost.

### `comfyui_cancel`
Cancel a pending job, interrupt the running one, or clear the queue.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt_id` | string | none | Delete this job from the pending queue |
| `interrupt_running` | bool | false | Stop the job currently executing |
| `clear_pending` | bool | false | Clear every pending job |

At least one argument is required — a no-argument call is refused so nothing is cancelled by accident.

## Using Your Own Images (LoadImage)

`LoadImage` resolves its `image` value against ComfyUI's own `input/` directory, **not** against the filesystem. Passing an absolute path fails with `Invalid image file: <name>`. So an image generated elsewhere on disk has to be uploaded into `input/` before a workflow can load it.

```text
comfyui_upload_image(paths=[...])  → load_image_name
comfyui_run_workflow(..., overrides={"<node_id>.image": load_image_name})
```

### `comfyui_upload_image`
Upload local image files into ComfyUI's `input/` directory.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `paths` | list | required | 1–50 absolute paths to local image files |
| `subfolder` | string | none | Subfolder under `input/`, e.g. `keyframes`. Created automatically |
| `overwrite` | bool | `true` | Replace an existing file of the same name |

Returns a `load_image_name` per file — the exact string to drop into a `LoadImage` node's `image` field. It uses forward slashes on every platform (`"keyframes/shot_01.png"`), because this is a ComfyUI-internal key rather than a filesystem path, and it reports the name **ComfyUI returned**, which can differ from the one you sent.

A file that cannot be read is reported in `failed` while the rest still upload; one bad path never aborts the batch.

`overwrite` defaults to `true` on purpose: regenerated keyframes get re-uploaded constantly, and silently keeping a stale image is a miserable bug to track down. With `overwrite=false`, ComfyUI renames on collision (`shot_01 (1).png`) — except when the bytes are identical, in which case it keeps the existing file and returns the original name.

Uploads go over ComfyUI's HTTP endpoint, so the server never needs to know where ComfyUI is installed and keeps working if ComfyUI moves to another machine.

### `comfyui_list_input_images`
List the images already in ComfyUI's `input/` directory.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filter` | string | none | Case-insensitive substring match |

Use it when a workflow reports `Invalid image file` — it shows whether the name is absent, sitting under a different subfolder, or simply spelled differently.

> **Note on subfolders.** ComfyUI's `LoadImage` node definition enumerates the input directory non-recursively, so images inside subfolders never appear there even though `LoadImage` loads them fine. This tool merges that list with a read-only scan of `input/` (located as the sibling of `--comfyui-output-dir`) so subfolder uploads are actually findable. Without `--comfyui-output-dir` configured, only top-level images are listed and the response says so.

### Example

> "Render `my_workflow.json` with seed 42, then copy the result to `./renders` as `shot_01`"

```text
comfyui_run_workflow(workflow_path="C:/wf/my_workflow.json",
                     overrides={"119.seed": 42}, label="shot_01")
  → {"ok": true, "prompt_id": "abc-123", "queue_position": 1}

comfyui_poll_workflow(prompt_id="abc-123")
  → {"status": "running", "elapsed_seconds": 240}

… wait, then poll again …

comfyui_poll_workflow(prompt_id="abc-123")
  → {"status": "completed"}

comfyui_get_outputs(prompt_id="abc-123", copy_to="./renders", filename="shot_01")
  → {"outputs": [{"kind": "video", "path": ".../shot_01_00001.mp4",
                  "bytes": 18234112, "copied_to": "./renders/shot_01.mp4"}]}
```

## Workflow Customization

The included `workflow.json` is configured for the Z-Image Turbo model. To use a different workflow:

1. Export your workflow from ComfyUI (Save → API Format)
2. Replace `workflow.json`
3. Update the node mappings in `server.py` if needed:
   - Node 7: Positive prompt (`text` field)
   - Node 11: Dimensions (`width`, `height` fields)
   - Node 6: Seed (`seed` field)
   - Node 12: Output (`filename_prefix` field)

## Troubleshooting

### "Cannot connect to ComfyUI"
- Ensure ComfyUI is running
- Check it's accessible at http://127.0.0.1:8188
- Verify no firewall is blocking the connection

### "Image file not found"

- Check that the save_path directory exists or is writable
- Verify ComfyUI has write permissions to the output folder

### Generation seems stuck
- Check ComfyUI's web interface for errors
- Verify your model and VAE are loaded correctly
- The default timeout is 300 seconds (5 minutes)

### "This is a UI-format workflow"
Your JSON is a normal ComfyUI save, not an API export. In ComfyUI use **Workflow → Export (API)**. An API-format file is a flat object keyed by node id, where each node has `class_type` and `inputs`; a UI export has a top-level `"nodes"` array instead.

### "Invalid image file: <name>"
A `LoadImage` node was given a name that is not in ComfyUI's `input/` directory. Upload the file with `comfyui_upload_image` and use the `load_image_name` it returns, or run `comfyui_list_input_images` to see what is actually there. An absolute filesystem path will never work here.

### "The ComfyUI output directory is not configured"
`comfyui_get_outputs` needs `--comfyui-output-dir` (or `COMFYUI_OUTPUT_DIR`) to turn ComfyUI's relative filenames into absolute paths. Point it at the `output` folder inside your ComfyUI installation and restart the MCP server.

### `comfyui_get_outputs` returns paths that don't exist
The configured output directory belongs to a different ComfyUI installation than the one serving `--comfyui-url`. If you have more than one ComfyUI, confirm which is actually running before setting the path.

### A render fails with CUDA out of memory
`comfyui_poll_workflow` surfaces this from ComfyUI's messages. Render a shorter clip (fewer frames) or a lower resolution — retrying unchanged will fail identically.

## Development

Run the test suite:

```bash
python -m pytest tests/
```

The tests run against a fake ComfyUI HTTP layer, so no GPU and no running ComfyUI is needed.

## Tips for Better Results

The Z-Image Turbo model responds well to:

1. **Detailed descriptions**: "A serene mountain lake at golden hour, snow-capped peaks reflected in still water, photorealistic"

2. **Style specifications**: "...in the style of watercolor illustration" or "...digital art, trending on artstation"

3. **Composition guidance**: "wide angle shot", "close-up portrait", "bird's eye view"

4. **Lighting details**: "dramatic lighting", "soft diffused light", "backlit silhouette"

Since this model doesn't use negative prompts, focus on describing what you want rather than what you don't want.

## License

[MIT License](LICENSE) - feel free to modify and share.
