"""Restart only the verified idle MORPH server, then check ReActor registration."""
from pathlib import Path
import importlib.util
import json
import time
import traceback
import urllib.request
from datetime import datetime, timezone

root = Path(r"D:\MORPH-Studio")
spec = importlib.util.spec_from_file_location("morph_start", root / "tools/lmstudio-wan-chat/start_mcp.py")
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
wrapper.configure_environment()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(endpoint):
    with opener.open("http://127.0.0.1:8188" + endpoint, timeout=30) as response:
        return json.load(response)

report = {"at": datetime.now(timezone.utc).isoformat(), "success": False, "renderSubmitted": False}
try:
    with wrapper.StartLock():
        owner, old_pid = wrapper.inspect_listener()
        assert owner == "owned", (owner, old_pid)
        queue = get("/queue")
        assert not queue["queue_running"] and not queue["queue_pending"], "Queue is busy; no process stopped"
        report.update(previousPid=old_pid, previousOwner=owner, queueBefore=queue)
        wrapper.powershell_json(f"Stop-Process -Id {old_pid} -ErrorAction Stop; 'null'")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            owner, pid = wrapper.inspect_listener()
            if owner == "free":
                break
            assert owner == "owned" and pid == old_pid, "Listener changed owner"
            time.sleep(0.5)
        assert owner == "free", "Previous listener did not close"
    time.sleep(1)
    report["comfyPid"] = wrapper.ensure_comfy()
    info = get("/object_info/ReActorFaceSwap")
    assert "ReActorFaceSwap" in info, "ReActorFaceSwap was not registered"
    node = info["ReActorFaceSwap"]
    (root / "reports/reactor-lmstudio/reactor-object-info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    workflow = json.loads((root / "workflows/LMStudio-Gesichtstausch-ReActor-api.json").read_text(encoding="utf-8"))
    inputs = workflow["3"]["inputs"]
    required = node["input"]["required"]
    assert not set(required) - set(inputs), "Required workflow fields missing"
    enums = {}
    for field, definition in required.items():
        if isinstance(definition[0], list):
            enums[field] = definition[0]
            assert inputs[field] in definition[0], f"Unavailable value for {field}: {inputs[field]}"
    assert "inswapper_128.onnx" in enums["swap_model"]
    assert "GPEN-BFR-512.onnx" in enums["face_restore_model"]
    assert node["output"][0] == "IMAGE"
    report.update(registered=True, workflowRequiredFieldsMatch=True, modelEnums=enums,
                  queueAfter=get("/queue"), success=True)
except Exception as exc:
    report.update(error=str(exc), traceback=traceback.format_exc())
path = root / "reports/reactor-lmstudio/activation.json"
path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["success"] else 1)
