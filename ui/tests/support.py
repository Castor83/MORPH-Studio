import io
import shutil
import tempfile
from pathlib import Path
from PIL import Image
from model_fixtures import KREA_ENCODER_SHAPES, gguf_fixture, write_model, write_tensors

PROJECT = Path(__file__).resolve().parents[2]
TEMPLATES = ['Phase2-1-Fotobild-SDXL-api.json', 'LMStudio-Bildbearbeitung-Kontext-api.json', 'LMStudio-Gesichtstausch-ReActor-api.json', 'LMStudio-Video-aus-Bild-Wan-api.json', 'MORPH-Qwen-Image-21-api.json', 'KREA2-SNOFS-Edit-20261015-api.json']
MODEL_FILES = ['checkpoints/sd_xl_base_1.0.safetensors', 'diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors', 'text_encoders/clip_l.safetensors', 'text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors', 'vae/ae.safetensors', 'insightface/inswapper_128.onnx', 'diffusion_models/Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors', 'diffusion_models/Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors', 'text_encoders/nsfw_wan_umt5-xxl_fp8_scaled.safetensors', 'vae/wan_2.1_vae.safetensors', 'upscale_models/4x_foolhardy_Remacri.pth']
KREA_MODEL_FILES = ['diffusion_models/KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf', 'text_encoders/qwen3vl_4b_fp8_scaled.safetensors', 'vae/qwen_image_vae.safetensors']

def png():
    stream = io.BytesIO()
    Image.new('RGB', (3, 2), (130, 25, 15)).save(stream, format='PNG')
    return stream.getvalue()

class Sandbox:
    def __init__(self, case):
        base = PROJECT / 'temp/morph-ui-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='ui-', dir=base)
        case.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        (self.root / 'workflows').mkdir(parents=True)
        for name in TEMPLATES:
            shutil.copyfile(PROJECT / 'workflows' / name, self.root / 'workflows' / name)
        model_root = self.root / 'ComfyUI_windows_portable/ComfyUI/models'
        for name in MODEL_FILES + ['insightface/models/buffalo_l/' + n for n in ['1k3d68.onnx','2d106det.onnx','det_10g.onnx','genderage.onnx','w600k_r50.onnx']]:
            path = model_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == '.safetensors':
                family = {'sd_xl_base_1.0.safetensors':'sdxl', 'flux1-dev-kontext_fp8_scaled.safetensors':'flux', 'clip_l.safetensors':'clip_l', 't5xxl_fp8_e4m3fn_scaled.safetensors':'t5', 'ae.safetensors':'flux_vae', 'nsfw_wan_umt5-xxl_fp8_scaled.safetensors':'umt5', 'wan_2.1_vae.safetensors':'wan_vae'}.get(path.name, 'wan')
                write_model(path, family)
            else:
                path.write_bytes(b'own test fixture; never loaded')
        for name in KREA_MODEL_FILES:
            path = model_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == '.gguf':
                gguf_fixture(path)
            elif path.name == 'qwen3vl_4b_fp8_scaled.safetensors':
                write_tensors(path, KREA_ENCODER_SHAPES)
            else:
                write_model(path, 'wan_vae')
        rife = self.root / 'ComfyUI_windows_portable/ComfyUI/custom_nodes/ComfyUI-VFI/rife/train_log/flownet.pkl'
        rife.parent.mkdir(parents=True, exist_ok=True)
        rife.write_bytes(b'own test fixture; never loaded')
