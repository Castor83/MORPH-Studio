"""
ComfyUI MCP Server

An MCP server that allows AI assistants to generate images using ComfyUI.
Designed for integration with Claude Code and other MCP-compatible clients.
"""

import argparse
import json
import os
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from PIL import Image

import comfy_core
from comfy_core import DEFAULT_COMFYUI_URL, get_comfyui_url, mcp

# ============================================================================
# Configuration
# ============================================================================

WORKFLOW_PATH = Path(__file__).parent / "z-image-api.json"
POLL_INTERVAL = 0.5  # seconds between status checks
MAX_WAIT_TIME = 300  # maximum seconds to wait for a single image generation
BATCH_MAX_WAIT_TIME = 14400  # maximum seconds to wait for batch generation (4 hours)

# The ComfyUI URL and output directory live in comfy_core so that this module
# and workflow_tools share one configuration, resolved once at startup from
# CLI args → env var → default. Read it with get_comfyui_url().

# ============================================================================
# Server Initialization
# ============================================================================

# The MCPServer instance also lives in comfy_core; both this module and
# workflow_tools register their tools on it.

# ============================================================================
# Batch Job Tracking (in-memory store)
# ============================================================================

# Stores active and completed batch jobs keyed by batch_id
# Each entry: {
#   "batch_id": str,
#   "start_time": float,
#   "total_requested": int,
#   "pending": {prompt_id: (index, ImageRequest, seed)},
#   "completed": [result_dict, ...],
#   "failed": [(index, error_msg), ...],
#   "queue_errors": [(index, error_msg), ...],
#   "images": [ImageRequest, ...],   # original requests for error reporting
#   "status": "queuing" | "processing" | "completed" | "timed_out"
# }
BATCH_JOBS: Dict[str, dict] = {}

# ============================================================================
# Workflow Management
# ============================================================================

def load_workflow() -> dict:
    """Load the base workflow template."""
    with open(WORKFLOW_PATH, "r") as f:
        return json.load(f)


def prepare_workflow(
    prompt: str,
    save_path: str,
    width: int,
    height: int,
    seed: Optional[int] = None,
    file_format: str = "jpg"
) -> dict:
    """
    Prepare workflow with injected parameters.

    Node mapping (from z-image-api.json):
    - Node 7: CLIPTextEncode - positive prompt (text field)
    - Node 11: EmptyLatentImage - dimensions (width, height)
    - Node 6: KSampler - seed
    - Node 14: NukeWrite - file_path (output save location), file_type (output format)
    """
    workflow = load_workflow()

    # Inject positive prompt into Node 7
    workflow["7"]["inputs"]["text"] = prompt

    # Inject dimensions into Node 11 (ensure divisible by 8)
    workflow["11"]["inputs"]["width"] = (width // 8) * 8
    workflow["11"]["inputs"]["height"] = (height // 8) * 8

    # Inject seed into Node 6 (generate random if not provided)
    if seed is None:
        seed = int(time.time() * 1000) % (2**53)  # JavaScript-safe integer
    workflow["6"]["inputs"]["seed"] = seed

    # Set the output file path on Node 14 (NukeWrite)
    # Normalize path to use forward slashes for cross-platform compatibility
    normalized_path = save_path.replace("\\", "/")
    workflow["14"]["inputs"]["file_path"] = normalized_path

    # Set the output file format on Node 14 (NukeWrite)
    workflow["14"]["inputs"]["file_type"] = file_format

    return workflow


# ============================================================================
# ComfyUI API Communication
# ============================================================================

def queue_prompt(workflow: dict) -> str:
    """
    Queue a workflow for execution in ComfyUI.
    
    Returns:
        prompt_id: Unique identifier for tracking the generation
    """
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    
    req = urllib.request.Request(
        f"{get_comfyui_url()}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["prompt_id"]
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Failed to connect to ComfyUI at {get_comfyui_url()}. "
            f"Make sure ComfyUI is running. Error: {e}"
        )


def get_history(prompt_id: str) -> Optional[dict]:
    """Get the execution history for a prompt."""
    try:
        req = urllib.request.Request(f"{get_comfyui_url()}/history/{prompt_id}")
        with urllib.request.urlopen(req, timeout=10) as response:
            history = json.loads(response.read().decode("utf-8"))
            return history.get(prompt_id)
    except urllib.error.URLError:
        return None


def wait_for_completion(prompt_id: str) -> dict:
    """
    Poll ComfyUI until the generation is complete.
    
    Returns:
        dict: The execution history containing output information
    """
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > MAX_WAIT_TIME:
            raise TimeoutError(
                f"Image generation timed out after {MAX_WAIT_TIME} seconds. "
                "The generation may still complete - check ComfyUI directly."
            )
        
        history = get_history(prompt_id)
        
        if history is not None:
            # Check if execution completed (has outputs)
            if history.get("outputs"):
                return history
            # Check for errors
            if history.get("status", {}).get("status_str") == "error":
                error_msg = history.get("status", {}).get("messages", [])
                raise RuntimeError(f"ComfyUI execution failed: {error_msg}")
        
        time.sleep(POLL_INTERVAL)


def get_image_path_from_history(history: dict, save_path: str, file_type: str = "jpg") -> Optional[Path]:
    """
    Extract the generated image path from execution history.
    
    Args:
        history: The execution history from ComfyUI
        save_path: The base save path specified in the workflow (without extension)
        file_type: The file extension/type used by NukeWrite (default: jpg)
        
    Returns:
        Path to the generated image, or None if not found
    """
    outputs = history.get("outputs", {})
    
    # Node 14 is NukeWrite in our workflow
    nuke_write_output = outputs.get("14", {})
    
    # NukeWrite returns the actual file path in its output
    if nuke_write_output:
        # Try to get the file path from NukeWrite output
        images = nuke_write_output.get("images", [])
        if images:
            # NukeWrite may return the full path
            filename = images[0].get("filename", "")
            if filename:
                file_path = Path(filename)
                # Verify the file actually exists before returning
                if file_path.exists():
                    return file_path
                # If not, fall through to fallback logic below
    
    # Fallback: construct path from save_path parameter
    # Normalize path for the current OS
    normalized_path = Path(save_path.replace("\\", "/"))
    
    # Try with _0001 suffix (auto_sequence with frame_padding=4, underscore separator)
    sequenced_path_underscore = normalized_path.parent / f"{normalized_path.name}_0001.{file_type}"
    if sequenced_path_underscore.exists():
        return sequenced_path_underscore

    # Try with .0001 suffix (auto_sequence with frame_padding=4, dot separator)
    sequenced_path_dot = normalized_path.parent / f"{normalized_path.name}.0001.{file_type}"
    if sequenced_path_dot.exists():
        return sequenced_path_dot
    
    # Try direct extension
    direct_path = normalized_path.parent / f"{normalized_path.name}.{file_type}"
    if direct_path.exists():
        return direct_path
    
    return None


# ============================================================================
# Input Models
# ============================================================================

class GenerateImageInput(BaseModel):
    """Input parameters for image generation."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    prompt: str = Field(
        ...,
        description="Natural language description of the image. Use descriptive sentences, not comma-separated tags. See tool docstring for prompt writing guide.",
        min_length=1,
        max_length=2000
    )
    
    save_path: str = Field(
        ...,
        description="Full absolute path where the image will be saved (WITHOUT file extension). ALWAYS use forward slashes. The image will be saved to EXACTLY this path with _0001.{file_format} appended (e.g. _0001.jpg, _0001.webp). Example: 'D:/projects/outputs/sunset' saves to 'D:/projects/outputs/sunset_0001.jpg' (or .webp/.png depending on file_format). Parent directory is created automatically if it doesn't exist.",
        min_length=1
    )
    
    width: int = Field(
        ...,
        description="Image width in pixels. Choose based on use case: 1024 (square/social), 1280 (landscape), 1536 (high-res landscape), 1920 (full HD), 768/864 (portrait). Must be divisible by 8.",
        ge=256,
        le=4096
    )
    
    height: int = Field(
        ...,
        description="Image height in pixels. Choose based on use case: 1024 (square/social), 720/768 (landscape), 864 (cinematic 16:9), 1080 (full HD), 1280/1536 (portrait). Must be divisible by 8.",
        ge=256,
        le=4096
    )
    
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible generation. Leave empty for random seed.",
        ge=0
    )

    file_format: str = Field(
        default="jpg",
        description=(
            "Output image format. Supported values: 'jpg', 'png', 'webp'. "
            "FORMAT SELECTION GUIDE: "
            "- Use 'jpg' (default) for most use cases: general images, social media, print, mockups, portfolios. "
            "- Use 'webp' when generating images for WEBSITES or WEB APPLICATIONS (HTML pages, React/Vue/Angular/Svelte apps, Next.js, web dashboards, landing pages, e-commerce sites, blogs, etc.). "
            "WebP provides 25-35% smaller file sizes than JPEG at equivalent quality, which improves web page load times and Core Web Vitals scores. "
            "- Use 'png' only when transparency or lossless quality is required."
        )
    )


class ListImagesInput(BaseModel):
    """Input parameters for listing generated images."""
    
    model_config = ConfigDict(extra="forbid")
    
    directory: str = Field(
        ...,
        description="Directory path to list images from.",
        min_length=1
    )
    
    limit: int = Field(
        default=10,
        description="Maximum number of images to list (most recent first).",
        ge=1,
        le=100
    )


class ConvertToWebpInput(BaseModel):
    """Input parameters for converting images to WebP format."""
    
    model_config = ConfigDict(extra="forbid")
    
    source_path: str = Field(
        ...,
        description="Path to the source image file (jpg, png, jpeg) to convert to WebP.",
        min_length=1
    )
    
    output_directory: Optional[str] = Field(
        default=None,
        description="Optional output directory for the WebP file. If not provided, creates a 'webp' subfolder in the source image's directory."
    )
    
    quality: int = Field(
        default=85,
        description="WebP quality (1-100). Higher = better quality but larger file. 80-85 is ideal for web. Default: 85",
        ge=1,
        le=100
    )
    
    preserve_filename: bool = Field(
        default=True,
        description="If True, keeps the original filename (with .webp extension). If False, can specify custom name."
    )
    
    custom_filename: Optional[str] = Field(
        default=None,
        description="Custom filename for the WebP output (without extension). Only used if preserve_filename is False."
    )


class BatchConvertToWebpInput(BaseModel):
    """Input parameters for batch converting images to WebP format."""
    
    model_config = ConfigDict(extra="forbid")
    
    source_directory: str = Field(
        ...,
        description="Directory containing images to convert to WebP.",
        min_length=1
    )
    
    output_directory: Optional[str] = Field(
        default=None,
        description="Output directory for WebP files. If not provided, creates a 'webp' subfolder in the source directory."
    )
    
    quality: int = Field(
        default=85,
        description="WebP quality (1-100). Higher = better quality but larger file. 80-85 is ideal for web. Default: 85",
        ge=1,
        le=100
    )
    
    recursive: bool = Field(
        default=False,
        description="If True, also process images in subdirectories, preserving folder structure."
    )


class ImageRequest(BaseModel):
    """A single image generation request within a batch."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    prompt: str = Field(
        ...,
        description="Natural language description of the image. Use descriptive sentences, not comma-separated tags.",
        min_length=1,
        max_length=2000
    )

    save_path: str = Field(
        ...,
        description="Full absolute path where the image will be saved (WITHOUT file extension). ALWAYS use forward slashes. Each image MUST have a unique save_path. Example: 'D:/projects/outputs/hero-banner'",
        min_length=1
    )

    width: int = Field(
        default=1024,
        description="Image width in pixels. Must be divisible by 8.",
        ge=256,
        le=4096
    )

    height: int = Field(
        default=1024,
        description="Image height in pixels. Must be divisible by 8.",
        ge=256,
        le=4096
    )

    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible generation. Leave empty for random seed.",
        ge=0
    )

    file_format: str = Field(
        default="jpg",
        description=(
            "Output image format: 'jpg' (default), 'webp' (for web projects), or 'png' (for transparency). "
            "Use 'webp' when generating images for websites or web applications."
        )
    )


class BatchGenerateImagesInput(BaseModel):
    """Input parameters for batch image generation."""

    model_config = ConfigDict(extra="forbid")

    images: List[ImageRequest] = Field(
        ...,
        description=(
            "List of image generation requests (1-100 images). Each item specifies its own prompt, "
            "save_path, dimensions, seed, and file_format. All images are queued to ComfyUI at once "
            "and processed sequentially. Every save_path must be unique."
        ),
        min_length=1,
        max_length=100
    )


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool(
    name="generate_image",
    annotations={
        "title": "Generate Image with ComfyUI",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def generate_image(params: GenerateImageInput) -> str:
    """
    Generate an image using ComfyUI with the Z-Image Turbo model.
    
    This tool submits a prompt to ComfyUI, waits for generation to complete,
    and saves the image to the specified path.
    
    The Z-Image Turbo model is fast (12 steps) and produces high-quality images.
    
    ═══════════════════════════════════════════════════════════════════════════════
    PROMPT WRITING GUIDE (IMPORTANT - READ BEFORE USING)
    ═══════════════════════════════════════════════════════════════════════════════
    
    This model uses NATURAL LANGUAGE prompts, NOT comma-separated tags like SDXL.
    Write descriptive sentences as if describing the image to another person.
    
    PROMPT STRUCTURE (Subject + Action + Style + Context):
    ─────────────────────────────────────────────────────────
    1. Subject: The main focus (person, object, character) - PUT THIS FIRST
    2. Action: What the subject is doing, their pose or state
    3. Style: Artistic approach, medium, or aesthetic
    4. Context: Setting, lighting, time, mood, atmosphere
    
    Word order matters - the model pays more attention to what comes first.
    Front-load your most important elements.
    
    OPTIMAL PROMPT LENGTH:
    ─────────────────────────────────────────────────────────
    - Short (10-30 words): Quick concepts, style exploration
    - Medium (30-80 words): Ideal for most projects
    - Long (80+ words): Complex scenes with detailed specifications
    
    IMPORTANT RULES:
    ─────────────────────────────────────────────────────────
    - NO negative prompts - describe what you WANT, not what to avoid
    - Instead of "no crowds", write "peaceful solitude"
    - Instead of "without glasses", write "clear, unobstructed eyes"
    - Be specific: "luxury leather handbag" not just "bag"
    
    PHOTOGRAPHY TERMS (the model understands these):
    ─────────────────────────────────────────────────────────
    - Lighting: "golden hour", "soft studio lighting", "dramatic side lighting",
      "Rembrandt lighting", "backlit", "overcast natural light"
    - Camera: "shot on 85mm lens", "f/2.8 shallow depth of field", "wide angle 24mm"
    - Angles: "eye level", "low angle", "bird's eye view", "over-the-shoulder"
    
    STYLE DESCRIPTORS:
    ─────────────────────────────────────────────────────────
    - Photography: "editorial fashion", "product photography", "lifestyle",
      "documentary style", "cinematic", "photorealistic"
    - Art: "oil painting", "watercolor illustration", "digital art",
      "concept art", "anime style", "minimalist design"
    
    EXAMPLE PROMPTS:
    ─────────────────────────────────────────────────────────
    Portrait:
      "Professional headshot of a confident business executive in her 40s,
       warm genuine smile, wearing navy blazer, clean white background,
       soft studio lighting, shot on 85mm lens at f/2.8"
    
    Landscape:
      "Ancient Greek temple ruins at sunset with scattered marble columns,
       golden hour lighting casting long shadows, cinematic photography style,
       dramatic clouds in orange and purple sky"
    
    Product:
      "Luxury leather handbag displayed on polished marble surface,
       soft directional lighting from the left, warm amber tones,
       professional product photography, clean minimal composition"
    
    Character:
      "Elderly wizard with flowing white beard and piercing blue eyes,
       casting a glowing spell with raised hands, fantasy art style,
       standing in a mystical forest clearing with soft ethereal light"
    
    ═══════════════════════════════════════════════════════════════════════════════

    ═══════════════════════════════════════════════════════════════════════════════
    OUTPUT FORMAT GUIDE
    ═══════════════════════════════════════════════════════════════════════════════

    Choose the file_format based on where the image will be used:

    JPG (default): Best for general-purpose images. Use for social media assets,
        print materials, mockups, portfolio work, presentations, and any non-web
        context. Good quality-to-size ratio for most applications.

    WEBP: Use when building WEBSITES or WEB APPLICATIONS. This includes HTML
        pages, React/Vue/Angular/Svelte/Next.js apps, web dashboards, landing
        pages, e-commerce sites, blogs, and any browser-rendered content.
        WebP is 25-35% smaller than JPEG at the same visual quality, improving
        page load times and Core Web Vitals. All modern browsers support WebP.

    PNG: Use only when lossless quality or transparency is required (e.g., logos,
        icons, overlays with alpha channel).

    ═══════════════════════════════════════════════════════════════════════════════

    Args:
        params: GenerateImageInput containing:
            - prompt (str): Natural language description (see guide above)
            - save_path (str): Full path for output (without extension, use forward slashes)
            - width (int): Image width in pixels (choose based on aspect ratio needed)
            - height (int): Image height in pixels (choose based on aspect ratio needed)
            - seed (int, optional): Random seed for reproducibility
            - file_format (str): Output format - 'jpg' (default), 'webp' (for web projects), or 'png' (for transparency)
    
    Common Aspect Ratios:
        - Square (1:1): 1024x1024 - social media, icons
        - Landscape (16:9): 1920x1080, 1536x864 - cinematic, desktop wallpaper
        - Landscape (3:2): 1536x1024 - photography standard
        - Portrait (9:16): 1080x1920, 864x1536 - mobile, stories
        - Portrait (2:3): 1024x1536 - portrait photography
    
    Returns:
        JSON with success status, image_path, seed used, prompt, and dimensions.
    """
    # Normalize path for cross-platform compatibility
    normalized_save_path = params.save_path.replace("\\", "/")
    save_path_obj = Path(normalized_save_path)
    
    # Ensure the save directory exists
    save_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    # Prepare the workflow with injected parameters
    workflow = prepare_workflow(
        prompt=params.prompt,
        save_path=normalized_save_path,
        width=params.width,
        height=params.height,
        seed=params.seed,
        file_format=params.file_format
    )
    
    # Get the actual seed used (in case it was generated)
    actual_seed = workflow["6"]["inputs"]["seed"]
    
    try:
        # Queue the generation
        prompt_id = queue_prompt(workflow)
        
        # Wait for completion
        history = wait_for_completion(prompt_id)
        
        # Get the generated image path
        image_path = get_image_path_from_history(history, normalized_save_path, file_type=params.file_format)

        if not image_path or not image_path.exists():
            expected = save_path_obj.parent / f"{save_path_obj.name}_0001.{params.file_format}"
            return json.dumps({
                "success": False,
                "error": "Generation completed but image file not found.",
                "prompt_id": prompt_id,
                "expected_path": str(expected)
            }, indent=2)
        
        result = {
            "success": True,
            "image_path": str(image_path),
            "seed": actual_seed,
            "prompt": params.prompt,
            "dimensions": f"{params.width}x{params.height}"
        }
        
        return json.dumps(result, indent=2)
        
    except ConnectionError as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "hint": "Make sure ComfyUI is running at http://127.0.0.1:8188"
        }, indent=2)
    except TimeoutError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Unexpected error: {type(e).__name__}: {str(e)}"
        }, indent=2)


@mcp.tool(
    name="batch_generate_images",
    annotations={
        "title": "Batch Generate Images with ComfyUI",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def batch_generate_images(params: BatchGenerateImagesInput) -> str:
    """
    Queue multiple images for generation in ComfyUI and return immediately.

    This tool is NON-BLOCKING. It queues all image requests to ComfyUI's internal
    queue and returns a batch_id immediately (within seconds). ComfyUI then processes
    them sequentially in the background, which can take minutes to hours depending
    on the number of images.

    WORKFLOW (two-step process):
    1. Call batch_generate_images → returns batch_id immediately
    2. Wait at least 50 seconds, then call check_batch_status with the batch_id
    3. If status is not "completed", wait another 50 seconds and call check_batch_status again
    4. Repeat until status is "completed". Do NOT call check_batch_status more often than
       every 50 seconds - image generation takes time and frequent calls waste API tokens

    Accepts up to 100 image requests, each with its own prompt, dimensions, format,
    and save path. Each image in the batch can have completely different settings.

    See the generate_image tool docstring for the full prompt writing guide.

    Args:
        params: BatchGenerateImagesInput containing:
            - images (list): 1-100 ImageRequest objects, each with:
                - prompt (str): Natural language image description
                - save_path (str): Unique output path (no extension, forward slashes)
                - width (int): Image width, default 1024
                - height (int): Image height, default 1024
                - seed (int, optional): For reproducibility
                - file_format (str): 'jpg' (default), 'webp' (web projects), 'png' (transparency)

    Returns:
        JSON with batch_id and queuing summary. Use batch_id with check_batch_status
        to monitor progress and retrieve results.
    """
    images = params.images
    total = len(images)

    # Validate unique save paths
    save_paths = [img.save_path.replace("\\", "/") for img in images]
    if len(set(save_paths)) != len(save_paths):
        return json.dumps({
            "success": False,
            "error": "Duplicate save_path detected. Each image must have a unique save_path."
        }, indent=2)

    batch_id = uuid.uuid4().hex[:12]
    start_time = time.time()

    # Queue all workflows to ComfyUI
    queued = []        # List of (index, prompt_id, image_request, seed)
    queue_errors = []  # List of (index, error_message)

    for i, img in enumerate(images):
        normalized_path = img.save_path.replace("\\", "/")
        Path(normalized_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            workflow = prepare_workflow(
                prompt=img.prompt,
                save_path=normalized_path,
                width=img.width,
                height=img.height,
                seed=img.seed,
                file_format=img.file_format
            )
            actual_seed = workflow["6"]["inputs"]["seed"]
            prompt_id = queue_prompt(workflow)
            queued.append((i, prompt_id, img, actual_seed))
        except ConnectionError as e:
            queue_errors.append((i, f"Connection error: {e}"))
        except Exception as e:
            queue_errors.append((i, f"{type(e).__name__}: {e}"))

    # If nothing was queued, return early (no batch_id stored)
    if not queued:
        return json.dumps({
            "success": False,
            "total_requested": total,
            "queued": 0,
            "failed_to_queue": total,
            "error": "Failed to queue any images to ComfyUI.",
            "failed_items": [
                {"index": idx, "prompt": images[idx].prompt[:100], "error": err}
                for idx, err in queue_errors
            ],
            "hint": "Make sure ComfyUI is running at http://127.0.0.1:8188"
        }, indent=2)

    # Store batch job for tracking via check_batch_status
    BATCH_JOBS[batch_id] = {
        "batch_id": batch_id,
        "start_time": start_time,
        "total_requested": total,
        "pending": {prompt_id: (idx, img, seed) for idx, prompt_id, img, seed in queued},
        "completed": [],
        "failed": [],
        "queue_errors": queue_errors,
        "images": images,
        "status": "processing"
    }

    queue_time = round(time.time() - start_time, 1)

    return json.dumps({
        "success": True,
        "batch_id": batch_id,
        "total_requested": total,
        "queued": len(queued),
        "failed_to_queue": len(queue_errors),
        "queue_time_seconds": queue_time,
        "status": "processing",
        "message": f"Successfully queued {len(queued)} of {total} images. "
                   f"Wait at least 50 seconds, then call check_batch_status with batch_id '{batch_id}' to monitor progress. "
                   f"Do NOT call check_batch_status more frequently than every 50 seconds.",
        "failed_items": [
            {"index": idx, "prompt": images[idx].prompt[:100], "error": err}
            for idx, err in queue_errors
        ] if queue_errors else []
    }, indent=2)


class CheckBatchStatusInput(BaseModel):
    """Input parameters for checking batch generation status."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str = Field(
        ...,
        description="The batch_id returned by batch_generate_images.",
        min_length=1
    )


@mcp.tool(
    name="check_batch_status",
    annotations={
        "title": "Check Batch Generation Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def check_batch_status(params: CheckBatchStatusInput) -> str:
    """
    Check the progress of a batch image generation job.

    Call this after batch_generate_images to monitor progress. Each call polls
    ComfyUI for the latest status of all pending images in the batch.

    IMPORTANT TIMING: Wait at least 50 seconds between each call to this tool.
    Image generation takes time - calling too frequently wastes API calls without
    new results. A good pattern is:
    1. Call batch_generate_images → get batch_id
    2. Wait 50 seconds
    3. Call check_batch_status → see progress
    4. If status is not "completed", wait another 50 seconds and repeat step 3

    Args:
        params: CheckBatchStatusInput containing:
            - batch_id (str): The batch_id from batch_generate_images

    Returns:
        JSON with current status, progress counts, completed image results, and failures.
    """
    batch_id = params.batch_id

    if batch_id not in BATCH_JOBS:
        return json.dumps({
            "success": False,
            "error": f"Batch '{batch_id}' not found. It may have expired or the server was restarted."
        }, indent=2)

    job = BATCH_JOBS[batch_id]

    # If already finalized, return cached result
    if job["status"] in ("completed", "timed_out"):
        return _build_batch_response(job)

    # Check timeout
    elapsed = time.time() - job["start_time"]
    max_wait = min(job["total_requested"] * MAX_WAIT_TIME, BATCH_MAX_WAIT_TIME)

    if elapsed > max_wait:
        # Mark all remaining as timed out
        for prompt_id, (idx, img, seed) in job["pending"].items():
            job["failed"].append((idx, f"Timed out after {int(elapsed)}s"))
        job["pending"] = {}
        job["status"] = "timed_out"
        return _build_batch_response(job)

    # Poll all pending prompt_ids
    resolved_ids = []
    for prompt_id, (idx, img, seed) in job["pending"].items():
        history = get_history(prompt_id)
        if history is None:
            continue

        # Check for errors
        if history.get("status", {}).get("status_str") == "error":
            error_msg = history.get("status", {}).get("messages", [])
            job["failed"].append((idx, f"ComfyUI execution failed: {error_msg}"))
            resolved_ids.append(prompt_id)
            continue

        # Check for completion
        if history.get("outputs"):
            normalized_path = img.save_path.replace("\\", "/")
            image_path = get_image_path_from_history(history, normalized_path, file_type=img.file_format)

            if image_path and image_path.exists():
                job["completed"].append({
                    "index": idx,
                    "success": True,
                    "image_path": str(image_path),
                    "prompt": img.prompt,
                    "seed": seed,
                    "dimensions": f"{(img.width // 8) * 8}x{(img.height // 8) * 8}",
                    "file_format": img.file_format
                })
                resolved_ids.append(prompt_id)
            else:
                # File not on disk yet - increment retry counter and keep as pending.
                # The file may still be flushing to disk. Only fail after 5 retries
                # (i.e. ~250 seconds of the file missing after ComfyUI reported done).
                retries = job.setdefault("_file_retries", {})
                retries[prompt_id] = retries.get(prompt_id, 0) + 1
                if retries[prompt_id] >= 5:
                    expected = Path(normalized_path).parent / f"{Path(normalized_path).name}_0001.{img.file_format}"
                    job["failed"].append((idx, f"Generation completed but image not found after retries at: {expected}"))
                    resolved_ids.append(prompt_id)
                # else: leave as pending, will retry on next check_batch_status call

    # Remove resolved from pending
    for pid in resolved_ids:
        del job["pending"][pid]

    # Update status if all done
    if not job["pending"]:
        job["status"] = "completed"

    return _build_batch_response(job)


def _build_batch_response(job: dict) -> str:
    """Build the JSON response for a batch job's current state."""
    elapsed = round(time.time() - job["start_time"], 1)
    completed_results = sorted(job["completed"], key=lambda r: r["index"])
    all_errors = job["queue_errors"] + job["failed"]
    failed_count = len(all_errors)
    completed_count = len(completed_results)
    pending_count = len(job["pending"])

    # Truncate results for context window friendliness
    max_shown = 20
    shown_results = completed_results[:max_shown]

    failed_items = [
        {"index": idx, "prompt": job["images"][idx].prompt[:100], "error": err}
        for idx, err in sorted(all_errors, key=lambda x: x[0])
    ]

    result = {
        "success": completed_count > 0 or pending_count > 0,
        "batch_id": job["batch_id"],
        "status": job["status"],
        "total_requested": job["total_requested"],
        "completed": completed_count,
        "pending": pending_count,
        "failed": failed_count,
        "elapsed_seconds": elapsed,
        "results": shown_results,
        "failed_items": failed_items
    }

    if completed_count > max_shown:
        result["note"] = f"Showing first {max_shown} of {completed_count} completed images."

    if pending_count > 0:
        result["message"] = f"{completed_count} done, {pending_count} still processing. Wait at least 50 seconds before calling check_batch_status again."

    return json.dumps(result, indent=2)


@mcp.tool(
    name="list_generated_images",
    annotations={
        "title": "List Generated Images",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def list_generated_images(params: ListImagesInput) -> str:
    """
    List images from a specified directory.
    
    Useful for finding previously generated images or checking what's available.
    
    Args:
        params: ListImagesInput containing:
            - directory (str): Directory path to list images from
            - limit (int): Maximum images to return (default: 10)
    
    Returns:
        JSON string with:
            - images (list): List of image info (path, size, modified time)
            - total (int): Total number of images found
            - showing (int): Number of images in this response
    """
    search_dir = Path(params.directory)
    
    if not search_dir.exists():
        return json.dumps({
            "success": False,
            "error": f"Directory not found: {search_dir}"
        }, indent=2)
    
    # Find all image files
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    images = []
    
    for file in search_dir.iterdir():
        if file.is_file() and file.suffix.lower() in image_extensions:
            stat = file.stat()
            images.append({
                "path": str(file),
                "filename": file.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            })
    
    # Sort by modification time (most recent first)
    images.sort(key=lambda x: x["modified"], reverse=True)
    
    return json.dumps({
        "success": True,
        "images": images[:params.limit],
        "total": len(images),
        "showing": min(len(images), params.limit),
        "directory": str(search_dir)
    }, indent=2)


@mcp.tool(
    name="check_comfyui_status",
    annotations={
        "title": "Check ComfyUI Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def check_comfyui_status() -> str:
    """
    Check if ComfyUI is running and accessible.
    
    Returns:
        JSON string with:
            - running (bool): Whether ComfyUI is accessible
            - url (str): The ComfyUI URL being used
            - queue_remaining (int): Number of items in queue (if available)
    """
    try:
        req = urllib.request.Request(f"{get_comfyui_url()}/queue")
        with urllib.request.urlopen(req, timeout=5) as response:
            queue_data = json.loads(response.read().decode("utf-8"))
            
            return json.dumps({
                "running": True,
                "url": get_comfyui_url(),
                "queue_pending": len(queue_data.get("queue_pending", [])),
                "queue_running": len(queue_data.get("queue_running", []))
            }, indent=2)
            
    except urllib.error.URLError as e:
        return json.dumps({
            "running": False,
            "url": get_comfyui_url(),
            "error": f"Cannot connect to ComfyUI: {e}",
            "hint": "Start ComfyUI and ensure it's running on port 8188"
        }, indent=2)


@mcp.tool(
    name="convert_to_webp",
    annotations={
        "title": "Convert Image to WebP",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def convert_to_webp(params: ConvertToWebpInput) -> str:
    """
    Convert an image (JPG, PNG, JPEG) to WebP format for web optimization.
    
    WebP provides superior compression, typically 25-35% smaller than JPEG
    at equivalent quality, making web pages load significantly faster.
    
    The converted file is saved to a 'webp' subfolder by default, keeping
    your original images organized separately from optimized web versions.
    
    Args:
        params: ConvertToWebpInput containing:
            - source_path (str): Path to source image (jpg, png, jpeg)
            - output_directory (str, optional): Custom output directory (default: 'webp' subfolder)
            - quality (int): WebP quality 1-100 (default: 85, ideal for web: 80-85)
            - preserve_filename (bool): Keep original filename (default: True)
            - custom_filename (str, optional): Custom output filename if preserve_filename is False
    
    Returns:
        JSON with:
            - success (bool): Whether conversion succeeded
            - webp_path (str): Path to the converted WebP file
            - original_size_kb (float): Original file size in KB
            - webp_size_kb (float): WebP file size in KB
            - compression_ratio (str): Size reduction percentage
    
    Usage Tips:
        - Use quality 80-85 for most web images (best balance)
        - Use quality 90+ for high-quality hero images
        - Use quality 60-75 for thumbnails or background images
        - Always use the WebP version in <picture> tags or with fallback
    
    Example HTML usage:
        <picture>
            <source srcset="image.webp" type="image/webp">
            <img src="image.jpg" alt="Description">
        </picture>
    """
    # Normalize source path
    source_path = Path(params.source_path.replace("\\", "/"))
    
    # Validate source file exists
    if not source_path.exists():
        return json.dumps({
            "success": False,
            "error": f"Source file not found: {source_path}"
        }, indent=2)
    
    # Validate source is an image
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}
    if source_path.suffix.lower() not in valid_extensions:
        return json.dumps({
            "success": False,
            "error": f"Unsupported image format: {source_path.suffix}. Supported: {', '.join(valid_extensions)}"
        }, indent=2)
    
    # Determine output directory
    if params.output_directory:
        output_dir = Path(params.output_directory.replace("\\", "/"))
    else:
        # Default: create 'webp' subfolder in source directory
        output_dir = source_path.parent / "webp"
    
    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine output filename
    if params.preserve_filename or not params.custom_filename:
        output_filename = source_path.stem + ".webp"
    else:
        output_filename = params.custom_filename + ".webp"
    
    output_path = output_dir / output_filename
    
    try:
        # Get original file size
        original_size = source_path.stat().st_size
        
        # Open and convert image
        with Image.open(source_path) as img:
            # Convert to RGB if necessary (WebP doesn't support all modes)
            if img.mode in ("RGBA", "LA", "P"):
                # Preserve transparency for RGBA
                if img.mode == "RGBA":
                    img.save(output_path, "WEBP", quality=params.quality, method=6)
                else:
                    img = img.convert("RGBA")
                    img.save(output_path, "WEBP", quality=params.quality, method=6)
            else:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(output_path, "WEBP", quality=params.quality, method=6)
        
        # Get WebP file size
        webp_size = output_path.stat().st_size
        
        # Calculate compression ratio
        reduction = ((original_size - webp_size) / original_size) * 100
        
        return json.dumps({
            "success": True,
            "webp_path": str(output_path),
            "original_path": str(source_path),
            "original_size_kb": round(original_size / 1024, 2),
            "webp_size_kb": round(webp_size / 1024, 2),
            "compression_ratio": f"{reduction:.1f}% smaller",
            "quality_used": params.quality
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Conversion failed: {type(e).__name__}: {str(e)}"
        }, indent=2)


@mcp.tool(
    name="batch_convert_to_webp",
    annotations={
        "title": "Batch Convert Images to WebP",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def batch_convert_to_webp(params: BatchConvertToWebpInput) -> str:
    """
    Convert all images in a directory to WebP format.
    
    Batch converts all JPG, JPEG, and PNG files in a directory to WebP,
    preserving the folder structure if recursive mode is enabled.
    
    This is ideal for converting entire image folders for web optimization.
    WebP typically provides 25-35% smaller file sizes than JPEG at equivalent quality.
    
    Args:
        params: BatchConvertToWebpInput containing:
            - source_directory (str): Directory containing images to convert
            - output_directory (str, optional): Custom output directory (default: 'webp' subfolder)
            - quality (int): WebP quality 1-100 (default: 85)
            - recursive (bool): If True, also process subdirectories
    
    Returns:
        JSON with conversion summary including:
            - converted_count: Number of images converted
            - total_savings_kb: Total file size reduction in KB
            - compression_ratio: Overall size reduction percentage
            - converted_files: List of converted file paths
    """
    source_dir = Path(params.source_directory.replace("\\", "/"))
    
    if not source_dir.exists():
        return json.dumps({
            "success": False,
            "error": f"Source directory not found: {source_dir}"
        }, indent=2)
    
    # Determine output directory
    if params.output_directory:
        output_dir = Path(params.output_directory.replace("\\", "/"))
    else:
        output_dir = source_dir / "webp"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all images
    valid_extensions = {".jpg", ".jpeg", ".png"}
    if params.recursive:
        image_files = [f for f in source_dir.rglob("*") if f.suffix.lower() in valid_extensions]
    else:
        image_files = [f for f in source_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]
    
    if not image_files:
        return json.dumps({
            "success": True,
            "message": "No images found to convert",
            "directory": str(source_dir)
        }, indent=2)
    
    converted = []
    failed = []
    total_original_size = 0
    total_webp_size = 0
    
    for img_path in image_files:
        try:
            # Determine relative path for recursive mode
            if params.recursive:
                relative_path = img_path.relative_to(source_dir)
                webp_output_dir = output_dir / relative_path.parent
                webp_output_dir.mkdir(parents=True, exist_ok=True)
            else:
                webp_output_dir = output_dir
            
            output_path = webp_output_dir / (img_path.stem + ".webp")
            
            original_size = img_path.stat().st_size
            total_original_size += original_size
            
            with Image.open(img_path) as img:
                if img.mode in ("RGBA", "LA", "P"):
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    img.save(output_path, "WEBP", quality=params.quality, method=6)
                else:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(output_path, "WEBP", quality=params.quality, method=6)
            
            webp_size = output_path.stat().st_size
            total_webp_size += webp_size
            
            converted.append({
                "original": str(img_path),
                "webp": str(output_path),
                "saved_kb": round((original_size - webp_size) / 1024, 2)
            })
            
        except Exception as e:
            failed.append({
                "file": str(img_path),
                "error": str(e)
            })
    
    total_reduction = ((total_original_size - total_webp_size) / total_original_size * 100) if total_original_size > 0 else 0
    
    return json.dumps({
        "success": True,
        "converted_count": len(converted),
        "failed_count": len(failed),
        "total_original_size_kb": round(total_original_size / 1024, 2),
        "total_webp_size_kb": round(total_webp_size / 1024, 2),
        "total_savings_kb": round((total_original_size - total_webp_size) / 1024, 2),
        "compression_ratio": f"{total_reduction:.1f}% smaller",
        "output_directory": str(output_dir),
        "converted_files": converted[:20],  # Limit output for readability
        "failed_files": failed,
        "note": f"Showing first 20 of {len(converted)} converted files" if len(converted) > 20 else None
    }, indent=2)


# ============================================================================
# Workflow and Upload Tools
# ============================================================================

# Importing these modules registers their tools on the shared MCPServer instance:
#   workflow_tools - comfyui_run_workflow, comfyui_poll_workflow,
#                    comfyui_get_outputs, comfyui_list_queue, comfyui_cancel
#   upload_tools   - comfyui_upload_image, comfyui_list_input_images
# Kept at the bottom so the import order reads plainly.
import workflow_tools  # noqa: E402,F401
import upload_tools  # noqa: E402,F401


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ComfyUI MCP Server")
    parser.add_argument(
        "--comfyui-url",
        default=os.environ.get("COMFYUI_URL", DEFAULT_COMFYUI_URL),
        help=f"ComfyUI server URL (default: {DEFAULT_COMFYUI_URL}). Can also be set via COMFYUI_URL env var."
    )
    parser.add_argument(
        "--comfyui-output-dir",
        default=os.environ.get("COMFYUI_OUTPUT_DIR"),
        help=(
            "Path to the ComfyUI output directory - the 'output' folder inside "
            "your ComfyUI installation. Needed by comfyui_get_outputs to return "
            "absolute paths for rendered files. Can also be set via the "
            "COMFYUI_OUTPUT_DIR env var."
        )
    )
    args, _ = parser.parse_known_args()

    comfy_core.configure(url=args.comfyui_url, output_dir=args.comfyui_output_dir)
    mcp.run()
