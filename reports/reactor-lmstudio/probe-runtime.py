"""Check isolated package imports and one tiny CUDA ONNX operation."""
import os
from pathlib import Path
import json
import traceback
from datetime import datetime, timezone

root = Path(r"D:\MORPH-Studio")
(root / "cache/ultralytics/Ultralytics").mkdir(parents=True, exist_ok=True)
os.environ.update(YOLO_CONFIG_DIR=str(root / "cache/ultralytics"), YOLO_OFFLINE="1",
                  NO_ALBUMENTATIONS_UPDATE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
report = {"at": datetime.now(timezone.utc).isoformat(), "imports": {}, "success": False}
try:
    import torch
    import numpy as np
    import cv2
    import onnx
    import onnxruntime as ort
    import albumentations
    import segment_anything
    import ultralytics
    for name, mod in [("torch", torch), ("numpy", np), ("cv2", cv2), ("onnx", onnx),
                      ("onnxruntime", ort), ("albumentations", albumentations),
                      ("segment_anything", segment_anything), ("ultralytics", ultralytics)]:
        report["imports"][name] = {"version": getattr(mod, "__version__", None), "path": mod.__file__}
    assert "reactor-runtime" not in cv2.__file__, "Existing OpenCV was shadowed"
    assert "reactor-runtime" not in np.__file__, "Existing NumPy was shadowed"
    assert "reactor-runtime" not in torch.__file__, "Existing Torch was shadowed"
    report["availableProviders"] = ort.get_available_providers()
    tensor = onnx.TensorProto.FLOAT
    graph = onnx.helper.make_graph([onnx.helper.make_node("MatMul", ["x", "y"], ["z"])],
        "morph-reactor-cuda-check", [onnx.helper.make_tensor_value_info("x", tensor, [2, 2]),
        onnx.helper.make_tensor_value_info("y", tensor, [2, 2])],
        [onnx.helper.make_tensor_value_info("z", tensor, [2, 2])])
    model = onnx.helper.make_model(graph, opset_imports=[onnx.helper.make_opsetid("", 18)])
    model.ir_version = 10
    options = ort.SessionOptions()
    options.enable_profiling = True
    options.profile_file_prefix = str(root / "reports/reactor-lmstudio/ort-cuda-profile")
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    session = ort.InferenceSession(model.SerializeToString(), sess_options=options,
                                  providers=["CUDAExecutionProvider"])
    assert "CUDAExecutionProvider" in session.get_providers(), session.get_providers()
    result = session.run(None, {"x": np.array([[1, 2], [3, 4]], dtype=np.float32),
                               "y": np.eye(2, dtype=np.float32)})[0]
    np.testing.assert_array_equal(result, [[1, 2], [3, 4]])
    profile_path = session.end_profiling()
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    math_providers = [item.get("args", {}).get("provider") for item in profile
                      if item.get("cat") == "Node" and item.get("args", {}).get("op_name") == "MatMul"]
    assert math_providers and set(math_providers) == {"CUDAExecutionProvider"}, math_providers
    report["cudaProbe"] = {"providers": session.get_providers(), "result": result.tolist(),
                           "cpuFallbackDisabled": True, "matmulProviders": math_providers,
                           "profile": profile_path}
    report["success"] = True
except Exception as exc:
    report["error"] = str(exc)
    report["traceback"] = traceback.format_exc()
target = root / "reports/reactor-lmstudio/runtime-probe.json"
target.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["success"] else 1)
