"""Safe, local model discovery from bounded file headers, without reading weights.

Family signatures follow the installed ComfyUI model_detection.py/sd.py. They
identify architecture and checkpoint components; they do not certify every
weight or prove that an inference will succeed. Variant roles which architecture
cannot distinguish also require an explicit supported filename declaration.
"""
import hashlib
import json
import os
import re
import stat
import struct
from pathlib import Path

from .paths import UiError

FOLDERS = ('checkpoints', 'diffusion_models', 'text_encoders', 'vae', 'loras', 'unet', 'clip')
HEADER_LIMIT = 8 * 1024 * 1024
TENSOR_RANK_LIMIT = 64
TENSOR_DIMENSION_LIMIT = 2 ** 64 - 1
DTYPE_BYTES = {
    'BOOL': 1, 'U8': 1, 'I8': 1, 'U16': 2, 'I16': 2, 'F16': 2, 'BF16': 2,
    'U32': 4, 'I32': 4, 'F32': 4, 'U64': 8, 'I64': 8, 'F64': 8,
    'F8_E4M3': 1, 'F8_E5M2': 1, 'F8_E4M3FNUZ': 1, 'F8_E5M2FNUZ': 1,
    'F8_E8M0': 1,
}
ROLE_FOLDERS = {
    'checkpoint': 'checkpoints', 'kontext': 'diffusion_models',
    'wan_high': 'diffusion_models', 'wan_low': 'diffusion_models',
    'qwen_model': 'diffusion_models', 'qwen_encoder': 'text_encoders',
    'qwen_vae': 'vae', 'clip_l': 'text_encoders', 't5': 'text_encoders',
    'umt5': 'text_encoders', 'flux_vae': 'vae', 'wan_vae': 'vae', 'lora': 'loras',
    'krea_model': 'diffusion_models', 'krea_encoder': 'text_encoders',
    'flux2_vae': 'vae', 'qwen3_encoder': 'text_encoders',
}
# GGML block sizes from the installed gguf/constants.py; no runtime/model import.
GGUF_BLOCKS = {
    0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20), 6: (32, 22),
    7: (32, 24), 8: (32, 34), 9: (32, 40), 10: (256, 84),
    11: (256, 110), 12: (256, 144), 13: (256, 176), 14: (256, 210),
    15: (256, 292), 16: (256, 66), 17: (256, 74), 18: (256, 98),
    19: (256, 50), 20: (32, 18), 21: (256, 110), 22: (256, 82),
    23: (256, 136), 24: (1, 1), 25: (1, 2), 26: (1, 4), 27: (1, 8),
    28: (1, 8), 29: (256, 56), 30: (1, 2), 34: (256, 54),
    35: (256, 66), 39: (32, 17), 40: (64, 36), 41: (128, 18),
}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Doppelter JSON-Schlüssel im Safetensors-Header.')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('Nicht endlicher JSON-Wert im Safetensors-Header.')


def _identity(info):
    # On this Windows Python, lstat.ctime still means creation time while
    # fstat.ctime means metadata change time. Birthtime is consistent for both.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, getattr(info, 'st_birthtime_ns', None)


def _is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


class ModelLibrary:
    def __init__(self, paths):
        self.paths = paths
        # Preserve the lexical location: resolving an existing junction first
        # would hide the very reparse point this inventory must exclude.
        self.base = Path(paths.root) / 'ComfyUI_windows_portable/ComfyUI/models'
        self._catalog = None

    def _safe_path(self, path, *, file=False):
        root = Path(self.paths.root)
        try:
            relative = path.relative_to(root)
            current = root
            for part in relative.parts:
                current = current / part
                info = current.lstat()
                if _is_link(info):
                    raise ValueError('Modellverknüpfungen und Reparse-Punkte werden nicht verwendet.')
                if current != path and not stat.S_ISDIR(info.st_mode):
                    raise ValueError('Ein Modellpfad enthält keinen regulären Ordner.')
            if not relative.parts:
                info = path.lstat()
            expected = stat.S_ISREG if file else stat.S_ISDIR
            if not expected(info.st_mode):
                raise ValueError('Der Modellpfad ist keine reguläre Datei oder kein regulärer Ordner.')
            resolved = path.resolve(strict=True)
            if resolved != path or not resolved.is_relative_to(root) or not resolved.is_relative_to(self.base):
                raise ValueError('Der Modellpfad verlässt den freigegebenen Modellbereich.')
            return info
        except (OSError, RuntimeError) as error:
            raise ValueError('Die Modelldatei ist nicht mehr sicher lesbar.') from error

    def _header(self, path):
        before = self._safe_path(path, file=True)
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if _identity(opened) != _identity(before) or not stat.S_ISREG(opened.st_mode):
                raise ValueError('Die Modelldatei wurde während der Prüfung ersetzt.')
            prefix = stream.read(8)
            if len(prefix) != 8:
                raise ValueError('Safetensors-Headerlänge fehlt.')
            length = struct.unpack('<Q', prefix)[0]
            if not 2 <= length <= HEADER_LIMIT or 8 + length > opened.st_size:
                raise ValueError('Safetensors-Header fehlt, ist abgeschnitten oder größer als 8 MiB.')
            raw = stream.read(length)
            if len(raw) != length or not raw.startswith(b'{'):
                raise ValueError('Safetensors-JSON-Header ist abgeschnitten oder ungültig.')
            try:
                header = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                                    parse_constant=_reject_constant)
            except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
                raise ValueError('Safetensors-JSON-Header ist ungültig.') from error
            if not isinstance(header, dict):
                raise ValueError('Safetensors-Header ist kein JSON-Objekt.')
            metadata = header.get('__metadata__', {})
            if not isinstance(metadata, dict) or any(not isinstance(value, str) for value in metadata.values()):
                raise ValueError('Safetensors-Metadaten müssen Textwerte enthalten.')
            tensors, intervals = {}, []
            data_size = opened.st_size - 8 - length
            for key, tensor in header.items():
                if key == '__metadata__':
                    continue
                if not isinstance(tensor, dict) or set(tensor) != {'dtype', 'shape', 'data_offsets'}:
                    raise ValueError('Ungültige Tensorbeschreibung im Safetensors-Header.')
                dtype, shape, offsets = tensor['dtype'], tensor['shape'], tensor['data_offsets']
                if not isinstance(dtype, str) or dtype not in DTYPE_BYTES:
                    raise ValueError('Nicht unterstützter Safetensors-Datentyp.')
                if not isinstance(shape, list) or len(shape) > TENSOR_RANK_LIMIT:
                    raise ValueError('Tensorformen benötigen höchstens 64 Dimensionen.')
                if any(type(value) is not int or not 0 <= value <= TENSOR_DIMENSION_LIMIT for value in shape):
                    raise ValueError('Tensorformen benötigen nichtnegative ganzzahlige Dimensionen.')
                if not isinstance(offsets, list) or len(offsets) != 2 or any(type(value) is not int for value in offsets):
                    raise ValueError('Tensor-Datenbereiche benötigen zwei ganze Zahlen.')
                start, end = offsets
                if start < 0 or end < start or end > data_size:
                    raise ValueError('Tensor-Datenbereich passt nicht zu Dateigröße, Form und Datentyp.')
                element_bytes = DTYPE_BYTES[dtype]
                element_limit = (end - start) // element_bytes
                # Empty tensors can have large other dimensions. Detect zero
                # first, and bound every nonempty product before multiplying.
                count = 0 if 0 in shape else 1
                if count:
                    for dimension in shape:
                        if dimension > element_limit // count:
                            raise ValueError('Tensor-Datenbereich passt nicht zu Dateigröße, Form und Datentyp.')
                        count *= dimension
                if end - start != count * element_bytes:
                    raise ValueError('Tensor-Datenbereich passt nicht zu Dateigröße, Form und Datentyp.')
                intervals.append((start, end))
                tensors[key] = tuple(shape)
            if not tensors:
                raise ValueError('Safetensors-Header enthält keine Tensoren.')
            cursor = 0
            for start, end in sorted(intervals):
                if start != cursor:
                    raise ValueError('Safetensors-Datenbereiche überlappen oder enthalten Lücken.')
                cursor = end
            if cursor != data_size:
                raise ValueError('Safetensors-Datei enthält nicht deklarierte Daten.')
            after = os.fstat(stream.fileno())
        if _identity(after) != _identity(opened) or _identity(self._safe_path(path, file=True)) != _identity(opened):
            raise ValueError('Die Modelldatei wurde während der Prüfung verändert.')
        return tensors, (_identity(opened), hashlib.sha256(raw).hexdigest())

    def _family(self, tensors, name):
        def shape(key, value):
            return tensors.get(key) == tuple(value)

        def any_shape(keys, value):
            return any(shape(key, value) for key in keys)

        def attention_width(width):
            return any(key.startswith('model.diffusion_model.') and key.endswith('.attn2.to_k.weight')
                       and len(value) == 2 and value[1] == width for key, value in tensors.items())

        lora_keys = [key for key in tensors if re.search(r'(?:lora_[AB]|lora_(?:up|down))\.(?:weight|bias)$', key)]
        lokr_keys = [key for key in tensors if re.search(r'\.lokr_w[12](?:_[ab])?$', key)]
        if lora_keys or lokr_keys:
            return 'lora', 'lora', 'lora', 'LoRA-Zusatz; benötigt einen eigenen Zusatzmodell-Workflow.'

        if (shape('first.weight', [6144, 64]) and shape('txtfusion.projector.weight', [1, 12])
                and shape('txtfusion.layerwise_blocks.0.prenorm.scale', [2560])
                and shape('blocks.0.attn.wq.weight', [6144, 6144])
                and shape('blocks.0.attn.wk.weight', [1536, 6144])):
            return ('diffusion_model', 'krea2', 'unsupported',
                    'KREA-2-Safetensors erkannt; das vorhandene Edit-Werkzeug verwendet ein eigenes GGUF-Profil. Kein Austausch ohne passendes Ladeprofil.')

        input_shape = tensors.get('model.diffusion_model.input_blocks.0.0.weight')
        if input_shape is not None:
            if len(input_shape) == 4 and input_shape[1] != 4:
                return 'checkpoint', 'unknown', 'unsupported', 'Inpainting oder abweichende Eingangskanäle; kein Standard-Bildcheckpoint.'
            if input_shape == (384, 4, 3, 3) or shape('model.diffusion_model.label_emb.0.0.weight', [1536, 2560]):
                return 'checkpoint', 'sdxl', 'unsupported', 'SDXL-Refiner benötigt einen eigenen Workflow.'
            family = None
            if input_shape == (320, 4, 3, 3) and attention_width(2048) and shape('model.diffusion_model.label_emb.0.0.weight', [1280, 2816]):
                family = 'sdxl'
                clip = (shape('conditioner.embedders.0.transformer.text_model.embeddings.token_embedding.weight', [49408, 768])
                        and shape('conditioner.embedders.1.model.token_embedding.weight', [49408, 1280]))
            elif input_shape == (320, 4, 3, 3) and attention_width(768) and 'model.diffusion_model.label_emb.0.0.weight' not in tensors:
                family = 'sd15'
                clip = any_shape(['cond_stage_model.transformer.text_model.embeddings.token_embedding.weight',
                                  'cond_stage_model.transformer.token_embedding.weight'], [49408, 768])
            if family:
                vae = (shape('first_stage_model.quant_conv.weight', [8, 8, 1, 1])
                       and shape('first_stage_model.post_quant_conv.weight', [4, 4, 1, 1]))
                if clip and vae:
                    return 'checkpoint', family, 'checkpoint', None
                return 'checkpoint', family, 'unsupported', 'Teilcheckpoint: eingebetteter Textencoder oder VAE fehlt oder passt nicht.'

        if (shape('img_in.weight', [4096, 64]) and shape('modulation.1.weight', [16384, 4096])
                and shape('transformer_blocks.0.attn.norm_q.weight', [128])
                and shape('txt_in.text_norm.weight', [4096]) and shape('proj_out.weight', [64, 4096])
                and (shape('transformer_blocks.0.img_mlp.gate_up.weight', [24576, 4096])
                     or shape('transformer_blocks.0.img_mlp.proj.weight', [12288, 4096]))):
            return 'diffusion_model', 'qwen_image21', 'qwen_model', None

        if (any_shape(['model.visual.deepstack_merger_list.0.norm.weight', 'visual.deepstack_merger_list.0.norm.weight'], [4608])
                and any_shape(['model.visual.merger.linear_fc2.weight', 'visual.merger.linear_fc2.weight'], [4096, 4608])
                and any_shape(['model.embed_tokens.weight', 'model.language_model.embed_tokens.weight'], [151936, 4096])):
            return 'text_encoder', 'qwen3_vl8b', 'qwen_encoder', None

        if (any_shape(['model.visual.deepstack_merger_list.0.norm.weight', 'visual.deepstack_merger_list.0.norm.weight'], [4096])
                and any_shape(['model.visual.merger.linear_fc2.weight', 'visual.merger.linear_fc2.weight'], [2560, 4096])
                and any_shape(['model.embed_tokens.weight', 'model.language_model.embed_tokens.weight'], [151936, 2560])):
            return 'text_encoder', 'qwen3_vl4b', 'krea_encoder', None

        if (shape('model.embed_tokens.weight', [151936, 4096])
                and shape('model.layers.0.post_attention_layernorm.weight', [4096])
                and shape('model.layers.0.self_attn.q_norm.weight', [128])
                and shape('model.layers.0.self_attn.k_proj.weight', [1024, 4096])
                and shape('model.layers.0.self_attn.q_proj.weight', [4096, 4096])):
            return ('text_encoder', 'qwen3_8b', 'qwen3_encoder',
                    'Qwen3-8B-Textencoder; keines der sechs vorhandenen Werkzeuge verwendet dieses Ladeprofil.')

        if (shape('decoder.head.2.weight', [4, 144, 1, 3, 3])
                and shape('decoder.middle.0.residual.0.gamma', [1152, 1, 1, 1])
                and shape('decoder.upsamples.0.upsamples.0.residual.2.weight', [1152, 1152, 1, 3, 3])
                and shape('encoder.conv1.weight', [96, 4, 1, 3, 3])
                and shape('decoder.head.0.gamma', [144, 1, 1, 1])
                and shape('conv1.weight', [128, 128, 1, 1, 1]) and shape('conv2.weight', [64, 64, 1, 1, 1])):
            return 'vae', 'qwen_image21_vae', 'qwen_vae', None

        if (shape('double_blocks.0.img_attn.qkv.weight', [9216, 3072])
                and shape('single_blocks.0.linear1.weight', [21504, 3072])
                and shape('img_in.weight', [3072, 64]) and shape('txt_in.weight', [3072, 4096])
                and any_shape(['double_blocks.0.img_attn.norm.key_norm.scale', 'double_blocks.0.img_attn.norm.key_norm.weight'], [128])
                and shape('guidance_in.in_layer.weight', [3072, 256])):
            if name == 'flux1-dev-kontext_fp8_scaled.safetensors':
                return 'diffusion_model', 'flux', 'kontext', None
            return 'diffusion_model', 'flux', 'unsupported', 'FLUX-Architektur erkannt; Kontext-Variante ist nicht ausdrücklich bestätigt.'

        wan_tensors = tensors
        if 'model.diffusion_model.head.modulation' in tensors:
            prefix = 'model.diffusion_model.'
            wan_tensors = {key[len(prefix):]: value for key, value in tensors.items() if key.startswith(prefix)}

        def wan_shape(key, value):
            return wan_tensors.get(key) == tuple(value)

        if (wan_shape('head.modulation', [1, 2, 5120]) and wan_shape('head.head.weight', [64, 5120])
                and wan_shape('blocks.0.ffn.0.weight', [13824, 5120])
                and wan_shape('text_embedding.0.weight', [5120, 4096])):
            # Wan2.2-I2V conditions through 36 input channels; unlike Wan2.1,
            # this profile can omit a separate CLIP image embedding module.
            if not wan_shape('patch_embedding.weight', [5120, 36, 1, 2, 2]):
                return 'diffusion_model', 'wan', 'unsupported', 'Wan-Modell passt nicht zum vorhandenen I2V-Profil mit 36 Eingangskanälen.'
            tokens = set(re.split(r'[^a-z0-9]+', name.lower()))
            phases = tokens.intersection({'high', 'low'})
            if len(phases) == 1:
                return 'diffusion_model', 'wan', 'wan_' + phases.pop(), None
            return 'diffusion_model', 'wan', 'unsupported', 'Wan-Rauschphase ist im Header nicht erkennbar; eindeutige High-/Low-Deklaration fehlt.'

        if (any_shape(['text_model.embeddings.token_embedding.weight', 'transformer.text_model.embeddings.token_embedding.weight'], [49408, 768])
                and any_shape(['text_model.encoder.layers.0.self_attn.k_proj.weight', 'transformer.text_model.encoder.layers.0.self_attn.k_proj.weight'], [768, 768])):
            return 'text_encoder', 'clip_l', 'clip_l', None
        if shape('encoder.block.0.layer.0.SelfAttention.k.weight', [4096, 4096]):
            if shape('shared.weight', [32128, 4096]):
                return 'text_encoder', 't5', 't5', None
            if shape('shared.weight', [256384, 4096]):
                return 'text_encoder', 'umt5', 'umt5', None
        if shape('encoder.conv_out.weight', [32, 512, 3, 3]) and shape('decoder.conv_in.weight', [512, 16, 3, 3]):
            return 'vae', 'flux_vae', 'flux_vae', None
        if (shape('encoder.conv_out.weight', [64, 512, 3, 3])
                and shape('decoder.conv_in.weight', [512, 32, 3, 3])
                and shape('quant_conv.weight', [64, 64, 1, 1])
                and shape('post_quant_conv.weight', [32, 32, 1, 1])):
            return ('vae', 'flux2_vae', 'flux2_vae',
                    'FLUX.2-Bilddecoder; gehört nicht zum vorhandenen FLUX.1-Kontext-Werkzeug.')
        if (shape('decoder.middle.0.residual.0.gamma', [384, 1, 1, 1])
                and shape('decoder.head.2.weight', [3, 96, 3, 3, 3])
                and shape('encoder.conv1.weight', [96, 3, 3, 3, 3])
                and shape('conv1.weight', [32, 32, 1, 1, 1]) and shape('conv2.weight', [16, 16, 1, 1, 1])):
            return 'vae', 'wan_vae', 'wan_vae', None
        return 'unknown', 'unknown', 'unsupported', 'Modellarchitektur nicht sicher erkannt; noch kein passender Workflow.'

    def _gguf_header(self, path):
        """Read metadata and tensor descriptors only; reject unbounded or short files."""
        before = self._safe_path(path, file=True)
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if _identity(opened) != _identity(before) or not stat.S_ISREG(opened.st_mode):
                raise ValueError('Die GGUF-Datei wurde während der Prüfung ersetzt.')
            raw = bytearray()

            def read(size):
                if size < 0 or len(raw) + size > HEADER_LIMIT:
                    raise ValueError('GGUF-Header ist größer als 8 MiB.')
                value = stream.read(size)
                if len(value) != size:
                    raise ValueError('GGUF-Header ist abgeschnitten.')
                raw.extend(value)
                return value

            def number(code):
                return struct.unpack('<' + code, read(struct.calcsize('<' + code)))[0]

            def string():
                return read(number('Q')).decode('utf-8')

            def value(kind, array=False):
                codes = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i',
                         6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}
                if kind in codes:
                    return number(codes[kind])
                if kind == 8:
                    return string()
                if kind == 9 and not array:
                    subtype, count = number('I'), number('Q')
                    if count > 262144:
                        raise ValueError('GGUF-Metadatenfeld ist zu groß.')
                    for _ in range(count):
                        value(subtype, array=True)
                    return None
                raise ValueError('Nicht unterstützter GGUF-Metadatentyp.')

            if read(4) != b'GGUF' or number('I') not in (2, 3):
                raise ValueError('GGUF-Kennung oder Version ist ungültig.')
            tensor_count, metadata_count = number('Q'), number('Q')
            if not 1 <= tensor_count <= 100000 or metadata_count > 100000:
                raise ValueError('GGUF-Header enthält eine ungültige Anzahl Einträge.')
            metadata = {}
            for _ in range(metadata_count):
                key = string()
                if key in metadata:
                    raise ValueError('Doppelter GGUF-Metadatenschlüssel.')
                metadata[key] = value(number('I'))
            alignment = metadata.get('general.alignment', 32)
            if type(alignment) is not int or not 1 <= alignment <= 4096 or alignment & (alignment - 1):
                raise ValueError('GGUF-Datenausrichtung ist ungültig.')
            tensors, intervals = {}, []
            for _ in range(tensor_count):
                name, rank = string(), number('I')
                if not name or name in tensors or not 1 <= rank <= 4:
                    raise ValueError('Ungültige GGUF-Tensorbeschreibung.')
                dimensions = [number('Q') for _ in range(rank)]
                kind, start = number('I'), number('Q')
                if kind not in GGUF_BLOCKS or not all(dimensions) or start % alignment:
                    raise ValueError('Nicht unterstützter GGUF-Tensortyp oder ungültiger Datenbereich.')
                block, block_bytes = GGUF_BLOCKS[kind]
                count = 1
                for dimension in dimensions:
                    if dimension > opened.st_size * block // block_bytes // count:
                        raise ValueError('GGUF-Tensor ist größer als die Datei.')
                    count *= dimension
                if dimensions[0] % block:
                    raise ValueError('GGUF-Tensor passt nicht zum Quantisierungsblock.')
                intervals.append((start, start + count // block * block_bytes))
                tensors[name] = tuple(reversed(dimensions))
            data_start = (len(raw) + alignment - 1) // alignment * alignment
            data_size, cursor = opened.st_size - data_start, 0
            for start, end in sorted(intervals):
                if start != (cursor + alignment - 1) // alignment * alignment or end > data_size:
                    raise ValueError('GGUF-Datenbereiche überlappen, fehlen oder sind abgeschnitten.')
                cursor = end
            if not cursor <= data_size < cursor + alignment:
                raise ValueError('GGUF-Dateigröße passt nicht zu den Tensorbeschreibungen.')
            after = os.fstat(stream.fileno())
        if _identity(after) != _identity(opened) or _identity(self._safe_path(path, file=True)) != _identity(opened):
            raise ValueError('Die GGUF-Datei wurde während der Prüfung verändert.')
        return tensors, metadata, (_identity(opened), hashlib.sha256(raw).hexdigest())

    def _inspect(self, path, model_id):
        format_name = path.suffix.lower().lstrip('.')
        item = {'id': model_id, 'name': path.name, 'path': str(path), 'format': format_name}
        if format_name == 'gguf':
            tensors, metadata, stamp = self._gguf_header(path)
        else:
            tensors, stamp = self._header(path)
        kind, family, role, reason = self._family(tensors, path.name)
        if format_name == 'gguf':
            if family == 'krea2' and metadata.get('general.architecture') == 'krea2':
                role, reason = 'krea_model', None
            else:
                kind = 'text_encoder' if model_id.startswith('text_encoders/') else 'diffusion_model'
                family, role = str(metadata.get('general.architecture', 'unknown')), 'unsupported'
                reason = 'GGUF-Komponente erkannt; kein passendes Ladeprofil in den sechs vorhandenen Werkzeugen.'
        elif family == 'wan_vae':
            reason = 'Gemeinsame Wan-/Qwen-Image-VAE-Architektur; Verwendung richtet sich nach dem konkreten Werkzeugprofil.'
        item.update(kind=kind, family=family, role=role)
        if reason:
            item['reason'] = reason
        return item, stamp

    def _walk(self, directory):
        try:
            self._safe_path(directory)
            entries = sorted(directory.iterdir(), key=lambda path: (path.name.casefold(), path.name))
        except (OSError, ValueError):
            return
        for path in entries:
            try:
                info = path.lstat()
                if _is_link(info):
                    continue
                if stat.S_ISDIR(info.st_mode):
                    yield from self._walk(path)
                elif stat.S_ISREG(info.st_mode) and path.suffix.lower() in ('.safetensors', '.gguf'):
                    self._safe_path(path, file=True)
                    yield path
            except (OSError, ValueError):
                continue

    def inventory(self):
        catalog, groups = {}, {}
        try:
            self._safe_path(self.base)
        except ValueError:
            self._catalog = {}
            return []
        for folder in FOLDERS:
            for path in self._walk(self.base / folder):
                model_id = path.relative_to(self.base).as_posix()
                try:
                    # Reuse unchanged discovery headers. Explicit resolve() still
                    # opens and validates the selected file before every build.
                    known = self._catalog.get(model_id) if self._catalog else None
                    current = self._safe_path(path, file=True)
                    if known and known[1] and known[1][0] == _identity(current):
                        item, stamp = dict(known[0]), known[1]
                    else:
                        item, stamp = self._inspect(path, model_id)
                except (OSError, ValueError, RecursionError) as error:
                    item = {'id': model_id, 'name': path.name, 'path': str(path),
                            'kind': 'invalid', 'family': 'invalid', 'role': 'invalid', 'reason': str(error)}
                    stamp = None
                catalog[model_id] = (item, stamp)
                # Genuine regular hardlinks are aliases, unlike rejected reparse points.
                inode = stamp[0][:2] if stamp and stamp[0][1] else ('path', model_id)
                groups.setdefault(inode, []).append(item)
        self._catalog = catalog
        items = []
        for aliases in groups.values():
            aliases.sort(key=lambda item: (item['id'].split('/')[0] != ROLE_FOLDERS.get(item['role']), item['id']))
            chosen = dict(aliases[0])
            if len(aliases) > 1:
                chosen['aliases'] = [item['id'] for item in aliases[1:]]
            items.append(chosen)
        return sorted(items, key=lambda item: item['id'])

    def _check_role(self, role):
        if not isinstance(role, str) or role not in ROLE_FOLDERS:
            raise UiError('model_role', 'Diese Modellrolle wird nicht unterstützt.')

    def choices(self, role):
        self._check_role(role)
        return [item for item in self.inventory() if item['role'] == role]

    def resolve(self, model_id, role):
        self._check_role(role)
        if (not isinstance(model_id, str) or not model_id or '\\' in model_id or ':' in model_id
                or '\x00' in model_id or model_id.startswith('/')
                or any(part in ('', '.', '..') for part in model_id.split('/'))
                or model_id.split('/')[0] not in FOLDERS):
            raise UiError('unsafe_model', 'Die Modellkennung ist kein freigegebener relativer Katalogpfad.')
        if self._catalog is None:
            self.inventory()
        known = self._catalog.get(model_id)
        if not known:
            raise UiError('model_missing', 'Die ausgewählte Modelldatei fehlt im sicheren lokalen Katalog: ' + Path(model_id).name, model_id, 404)
        try:
            item, stamp = self._inspect(self.base / model_id, model_id)
        except (OSError, ValueError, RecursionError) as error:
            raise UiError('model_invalid', 'Die ausgewählte Modelldatei ist nicht sicher lesbar: ' + Path(model_id).name, model_id) from error
        if stamp != known[1]:
            raise UiError('model_changed', 'Die Modelldatei wurde seit der Auswahl verändert. Bitte Modellliste neu laden.', model_id)
        if item['role'] != role:
            raise UiError('model_role', 'Das ausgewählte Modell passt nicht zu dieser Workflow-Rolle.', item.get('reason', item['family']))
        return item
