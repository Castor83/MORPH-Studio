import json, sys, time
from pathlib import Path
import torch
root = Path(r'E:\MORPH-Studio')
assert torch.cuda.is_available(), 'CUDA unavailable'
started = time.perf_counter()
torch.manual_seed(42)
a = torch.randn(1024, 1024, device='cuda')
b = torch.randn(1024, 1024, device='cuda')
c = a @ b
torch.cuda.synchronize()
cpu = a.cpu() @ b.cpu()
error = (c.cpu() - cpu).abs().max().item()
assert torch.allclose(c.cpu(), cpu, rtol=1e-3, atol=1e-3), error
result = dict(python=sys.version, executable=sys.executable, torch=torch.__version__, cuda_runtime=torch.version.cuda,
              gpu=torch.cuda.get_device_name(0), vram_bytes=torch.cuda.get_device_properties(0).total_memory,
              capability=torch.cuda.get_device_capability(0), max_error=error,
              elapsed_seconds=time.perf_counter()-started, passed=True)
(root/'reports'/'gpu-test.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
