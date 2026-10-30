"""The server must expose the original tools and the new workflow tools together."""

import asyncio

import server

EXISTING_TOOLS = {
    "generate_image",
    "batch_generate_images",
    "check_batch_status",
    "list_generated_images",
    "check_comfyui_status",
    "convert_to_webp",
    "batch_convert_to_webp",
}

WORKFLOW_TOOLS = {
    "comfyui_run_workflow",
    "comfyui_poll_workflow",
    "comfyui_get_outputs",
    "comfyui_list_queue",
    "comfyui_cancel",
}

UPLOAD_TOOLS = {
    "comfyui_upload_image",
    "comfyui_list_input_images",
}


def tool_names():
    return {tool.name for tool in asyncio.run(server.mcp.list_tools())}


def test_the_original_tools_are_still_registered():
    assert EXISTING_TOOLS <= tool_names()


def test_the_workflow_tools_are_registered():
    assert WORKFLOW_TOOLS <= tool_names()


def test_the_upload_tools_are_registered():
    assert UPLOAD_TOOLS <= tool_names()


def test_every_tool_is_registered_exactly_once():
    names = [tool.name for tool in asyncio.run(server.mcp.list_tools())]

    assert len(names) == len(set(names))


def test_the_url_configured_at_startup_is_the_one_the_tools_use():
    """server.py and workflow_tools.py must not drift onto separate config."""
    import comfy_core

    comfy_core.configure("http://192.168.1.50:8188", None)
    try:
        assert server.get_comfyui_url() == "http://192.168.1.50:8188"
    finally:
        comfy_core.configure("http://127.0.0.1:8188", None)
