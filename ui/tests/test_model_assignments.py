"""Regressions for existing model headers; sparse fixtures never run models."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.model_library import ModelLibrary
from morph_ui.paths import ProjectPaths
from model_fixtures import PROJECT, KREA_SHAPES, _set_length, gguf_fixture, write_tensors


class ModelAssignmentTests(unittest.TestCase):
    def setUp(self):
        base = PROJECT / 'temp/morph-model-assignment-tests'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='assign-', dir=base)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / 'project'
        root.mkdir()
        self.paths = ProjectPaths(root)
        self.library = ModelLibrary(self.paths)

    def test_lokr_adapter_is_a_supplement_not_an_unknown_checkpoint(self):
        path = self.paths.models / 'loras/adapter.safetensors'
        write_tensors(path, {'diffusion_model.blocks.0.attn.wq.lokr_w1': [4, 4],
                             'diffusion_model.blocks.0.attn.wq.lokr_w2': [16, 16]})
        self.assertEqual(self.library.inventory()[0]['role'], 'lora')

    def test_qwen3vl4b_is_krea_encoder_and_cannot_be_qwen21_encoder(self):
        write_tensors(self.paths.models / 'text_encoders/encoder.safetensors', {
            'model.visual.deepstack_merger_list.0.norm.weight': [4096],
            'model.visual.merger.linear_fc2.weight': [2560, 4096],
            'model.embed_tokens.weight': [151936, 2560]})
        self.assertEqual(self.library.inventory()[0]['role'], 'krea_encoder')
        self.assertEqual(self.library.choices('qwen_encoder'), [])

    def test_krea_safetensors_is_identified_without_offering_it_to_gguf_loader(self):
        write_tensors(self.paths.models / 'diffusion_models/krea.safetensors', KREA_SHAPES,
                      {'aitk_quantization': 'convrot8'})
        item = self.library.inventory()[0]
        self.assertEqual((item['kind'], item['family'], item['role']),
                         ('diffusion_model', 'krea2', 'unsupported'))
        self.assertIn('GGUF', item['reason'])

    def test_flux2_vae_is_a_component_not_a_checkpoint(self):
        write_tensors(self.paths.models / 'checkpoints/decoder.safetensors', {
            'encoder.conv_out.weight': [64, 512, 3, 3],
            'decoder.conv_in.weight': [512, 32, 3, 3],
            'quant_conv.weight': [64, 64, 1, 1],
            'post_quant_conv.weight': [32, 32, 1, 1]})
        self.assertEqual(self.library.inventory()[0]['role'], 'flux2_vae')

    def test_qwen3_text_only_encoder_is_not_qwen_image21_encoder(self):
        write_tensors(self.paths.models / 'text_encoders/encoder.safetensors', {
            'model.embed_tokens.weight': [151936, 4096],
            'model.layers.0.post_attention_layernorm.weight': [4096],
            'model.layers.0.self_attn.q_norm.weight': [128],
            'model.layers.0.self_attn.k_proj.weight': [1024, 4096],
            'model.layers.0.self_attn.q_proj.weight': [4096, 4096]})
        self.assertEqual(self.library.inventory()[0]['role'], 'qwen3_encoder')
        self.assertEqual(self.library.choices('qwen_encoder'), [])

    def test_krea_gguf_uses_architecture_and_tensor_shapes(self):
        gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf')
        choices = self.library.choices('krea_model')
        self.assertEqual([item['id'] for item in choices], ['diffusion_models/editor.gguf'])
        self.assertEqual(choices[0]['format'], 'gguf')

    def test_krea_gguf_declaration_alone_is_not_a_loader_choice(self):
        gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf', {'wrong.weight': [1]})
        self.assertEqual(self.library.choices('krea_model'), [])

    def test_krea_shapes_with_other_gguf_architecture_are_not_a_loader_choice(self):
        gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf', architecture='other')
        self.assertEqual(self.library.choices('krea_model'), [])

    def test_gguf_overlapping_tensor_ranges_are_rejected(self):
        path = gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf')
        with path.open('r+b') as stream:
            raw = stream.read(2048)
            marker = b'txtfusion.projector.weight'
            # Offset follows name, rank, two dimensions, and quantization type.
            position = raw.index(marker) + len(marker) + 4 + 16 + 4
            stream.seek(position)
            stream.write(struct.pack('<Q', 0))
        self.assertEqual(self.library.inventory()[0]['role'], 'invalid')

    def test_gguf_header_reads_never_touch_tensor_weights(self):
        path = gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf')
        original = Path.open
        reads = []

        class Reader:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def fileno(self):
                return self.stream.fileno()
            def read(self, size=-1):
                reads.append(size)
                if size < 0 or self.stream.tell() + size > 2048:
                    raise AssertionError('Attempted weight read')
                return self.stream.read(size)

        def opened(target, *args, **kwargs):
            stream = original(target, *args, **kwargs)
            return Reader(stream) if target == path else stream

        with patch.object(Path, 'open', opened):
            self.assertEqual(len(self.library.choices('krea_model')), 1)
        self.assertTrue(reads)

    def test_gguf_file_changed_after_inventory_is_rejected(self):
        from morph_ui.paths import UiError
        path = gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf')
        self.library.inventory()
        with path.open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaises(UiError):
            self.library.resolve('diffusion_models/editor.gguf', 'krea_model')

    def test_truncated_gguf_and_excessive_header_are_rejected(self):
        path = gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf')
        with path.open('r+b') as stream:
            _set_length(stream, 128)
        self.assertEqual(self.library.inventory()[0]['role'], 'invalid')
        path.write_bytes(struct.pack('<4sIQQQ', b'GGUF', 3, 1, 1, 2**40))
        self.assertEqual(self.library.inventory()[0]['role'], 'invalid')

    def test_gguf_zero_dimensions_and_nested_metadata_arrays_are_rejected(self):
        path = gguf_fixture(self.paths.models / 'diffusion_models/editor.gguf',
                            {'zero.weight': [0]})
        self.assertEqual(self.library.inventory()[0]['role'], 'invalid')
        key = b'nested'
        header = struct.pack('<4sIQQQ', b'GGUF', 3, 1, 1, len(key)) + key
        # Array-of-array is rejected before parsing any nested contents.
        path.write_bytes(header + struct.pack('<IIQ', 9, 9, 1))
        self.assertEqual(self.library.inventory()[0]['role'], 'invalid')


if __name__ == '__main__':
    unittest.main()
