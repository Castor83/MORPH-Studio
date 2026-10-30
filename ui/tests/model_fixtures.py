"""Header-only synthetic model fixtures; sparse data are never model weights."""
import json
import os
import struct
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
KREA_SHAPES = {
    'first.weight': [6144, 64],
    'txtfusion.projector.weight': [1, 12],
    'txtfusion.layerwise_blocks.0.prenorm.scale': [2560],
    'blocks.0.attn.wq.weight': [6144, 6144],
    'blocks.0.attn.wk.weight': [1536, 6144],
}
KREA_ENCODER_SHAPES = {
    'model.visual.deepstack_merger_list.0.norm.weight': [4096],
    'model.visual.merger.linear_fc2.weight': [2560, 4096],
    'model.embed_tokens.weight': [151936, 2560],
}


def model_shapes(family):
    vae = {'first_stage_model.quant_conv.weight': [8, 8, 1, 1],
           'first_stage_model.post_quant_conv.weight': [4, 4, 1, 1]}
    shapes = {
        'sd15': dict(vae, **{
            'model.diffusion_model.input_blocks.0.0.weight': [320, 4, 3, 3],
            'model.diffusion_model.input_blocks.1.1.transformer_blocks.0.attn2.to_k.weight': [320, 768],
            'cond_stage_model.transformer.text_model.embeddings.token_embedding.weight': [49408, 768]}),
        'sdxl': dict(vae, **{
            'model.diffusion_model.input_blocks.0.0.weight': [320, 4, 3, 3],
            'model.diffusion_model.input_blocks.4.1.transformer_blocks.0.attn2.to_k.weight': [640, 2048],
            'model.diffusion_model.label_emb.0.0.weight': [1280, 2816],
            'conditioner.embedders.0.transformer.text_model.embeddings.token_embedding.weight': [49408, 768],
            'conditioner.embedders.1.model.token_embedding.weight': [49408, 1280]}),
        'flux': {
            'double_blocks.0.img_attn.norm.key_norm.scale': [128],
            'double_blocks.0.img_attn.qkv.weight': [9216, 3072],
            'single_blocks.0.linear1.weight': [21504, 3072],
            'img_in.weight': [3072, 64], 'txt_in.weight': [3072, 4096],
            'guidance_in.in_layer.weight': [3072, 256]},
        'wan': {
            'patch_embedding.weight': [5120, 36, 1, 2, 2],
            'head.modulation': [1, 2, 5120], 'head.head.weight': [64, 5120],
            'blocks.0.ffn.0.weight': [13824, 5120],
            'text_embedding.0.weight': [5120, 4096],
            'img_emb.proj.0.bias': [1280]},
        'qwen_model': {
            'img_in.weight': [4096, 64], 'modulation.1.weight': [16384, 4096],
            'transformer_blocks.0.attn.norm_q.weight': [128],
            'transformer_blocks.0.img_mlp.gate_up.weight': [24576, 4096],
            'txt_in.text_norm.weight': [4096], 'proj_out.weight': [64, 4096]},
        'qwen_encoder': {
            'model.visual.deepstack_merger_list.0.norm.weight': [4608],
            'model.visual.merger.linear_fc2.weight': [4096, 4608],
            'model.embed_tokens.weight': [151936, 4096]},
        'qwen_vae': {
            'decoder.middle.0.residual.0.gamma': [1152, 1, 1, 1],
            'decoder.upsamples.0.upsamples.0.residual.2.weight': [1152, 1152, 1, 3, 3],
            'decoder.head.2.weight': [4, 144, 1, 3, 3],
            'decoder.head.0.gamma': [144, 1, 1, 1],
            'encoder.conv1.weight': [96, 4, 1, 3, 3],
            'conv1.weight': [128, 128, 1, 1, 1], 'conv2.weight': [64, 64, 1, 1, 1]},
        'clip_l': {'text_model.embeddings.token_embedding.weight': [49408, 768],
                   'text_model.encoder.layers.0.self_attn.k_proj.weight': [768, 768]},
        't5': {'shared.weight': [32128, 4096],
               'encoder.block.0.layer.0.SelfAttention.k.weight': [4096, 4096]},
        'umt5': {'shared.weight': [256384, 4096],
                 'encoder.block.0.layer.0.SelfAttention.k.weight': [4096, 4096]},
        'flux_vae': {'encoder.conv_out.weight': [32, 512, 3, 3],
                     'decoder.conv_in.weight': [512, 16, 3, 3]},
        'wan_vae': {'decoder.middle.0.residual.0.gamma': [384, 1, 1, 1],
                    'decoder.head.2.weight': [3, 96, 3, 3, 3],
                    'encoder.conv1.weight': [96, 3, 3, 3, 3],
                    'conv1.weight': [32, 32, 1, 1, 1], 'conv2.weight': [16, 16, 1, 1, 1]},
        'lora': {'diffusion_model.blocks.0.self_attn.q.lora_A.weight': [64, 5120],
                 'diffusion_model.blocks.0.self_attn.q.lora_B.weight': [5120, 64]},
        'unknown': {'unknown.weight': [1]},
    }
    return shapes[family]


def _sparse(stream):
    if os.name == 'nt':
        import ctypes
        import msvcrt
        from ctypes import wintypes
        ioctl = ctypes.WinDLL('kernel32', use_last_error=True).DeviceIoControl
        ioctl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                         wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        ioctl.restype = wintypes.BOOL
        result = wintypes.DWORD()
        if not ioctl(msvcrt.get_osfhandle(stream.fileno()), 0x900C4,
                     None, 0, None, 0, ctypes.byref(result), None):
            raise ctypes.WinError(ctypes.get_last_error())


def _set_length(stream, size):
    stream.flush()
    if os.name != 'nt':
        stream.truncate(size)
        return
    # CRT _chsize_s may write zeros even on sparse files. Native EOF is constant-time.
    import ctypes
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    pointer = kernel.SetFilePointerEx
    pointer.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                        ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
    pointer.restype = wintypes.BOOL
    end = kernel.SetEndOfFile
    end.argtypes = [wintypes.HANDLE]
    end.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(stream.fileno())
    if not pointer(handle, size, None, 0) or not end(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def write_raw(path, header, data_size=0):
    path = Path(path)
    if not path.resolve().is_relative_to(PROJECT / 'temp'):
        raise ValueError('Synthetic fixtures belong under the MORPH project temp directory.')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        _sparse(stream)
        stream.write(struct.pack('<Q', len(header)))
        stream.write(header)
        _set_length(stream, 8 + len(header) + data_size)
    return path


def write_tensors(path, shapes, metadata=None, dtype='F16'):
    sizes = {'F16': 2, 'BF16': 2, 'F32': 4, 'U8': 1}
    header, offset = {}, 0
    if metadata is not None:
        header['__metadata__'] = metadata
    for name, shape in shapes.items():
        count = 1
        for dimension in shape:
            count *= dimension
        end = offset + count * sizes[dtype]
        header[name] = {'dtype': dtype, 'shape': shape, 'data_offsets': [offset, end]}
        offset = end
    return write_raw(path, json.dumps(header, separators=(',', ':')).encode(), offset)


def write_model(path, family):
    return write_tensors(path, model_shapes(family))


def gguf_fixture(path, shapes=KREA_SHAPES, architecture='krea2'):
    """Minimal GGUF tensor descriptors with sparse dummy data; never weights."""
    path = Path(path)
    if not path.resolve().is_relative_to(PROJECT / 'temp'):
        raise ValueError('Synthetic fixtures belong under the MORPH project temp directory.')

    def string(value):
        raw = value.encode('utf-8')
        return struct.pack('<Q', len(raw)) + raw

    header = bytearray(struct.pack('<4sIQQ', b'GGUF', 3, len(shapes), 1))
    header += string('general.architecture') + struct.pack('<I', 8) + string(architecture)
    offset = 0
    for name, shape in shapes.items():
        header += string(name) + struct.pack('<I', len(shape))
        header += struct.pack('<' + 'Q' * len(shape), *reversed(shape))
        header += struct.pack('<IQ', 0, offset)
        count = 1
        for dimension in shape:
            count *= dimension
        offset += count * 4
        offset = (offset + 31) // 32 * 32
    header += bytes((-len(header)) % 32)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        _sparse(stream)
        stream.write(header)
        _set_length(stream, len(header) + offset)
    return path
