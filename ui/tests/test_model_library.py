import io
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths, UiError
try:
    from morph_ui.model_library import ModelLibrary
except ModuleNotFoundError:
    ModelLibrary = None
from model_fixtures import PROJECT, model_shapes, write_model, write_raw, write_tensors


class ModelLibraryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ModelLibrary, 'Sichere Modellbibliothek noch nicht implementiert')
        base = PROJECT / 'temp/morph-model-library-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='library-', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.root.mkdir()
        self.paths = ProjectPaths(self.root)
        self.library = ModelLibrary(self.paths)

    def model(self, model_id, family):
        return write_model(self.paths.models / model_id, family)

    def item(self, model_id):
        return next(item for item in self.library.inventory() if item['id'] == model_id)

    def test_complete_sd15_and_sdxl_checkpoints_are_choices(self):
        self.model('checkpoints/arbitrary.safetensors', 'sd15')
        self.model('checkpoints/nested/base.safetensors', 'sdxl')
        choices = self.library.choices('checkpoint')
        self.assertEqual([item['id'] for item in choices],
                         ['checkpoints/arbitrary.safetensors', 'checkpoints/nested/base.safetensors'])
        self.assertEqual([item['family'] for item in choices], ['sd15', 'sdxl'])
        self.assertEqual(choices[0]['kind'], 'checkpoint')
        self.assertEqual(choices[0]['name'], 'arbitrary.safetensors')
        self.assertEqual(choices[0]['path'], str(self.paths.models / 'checkpoints/arbitrary.safetensors'))

    def test_checkpoint_without_encoder_is_not_complete(self):
        shapes = model_shapes('sd15')
        del shapes['cond_stage_model.transformer.text_model.embeddings.token_embedding.weight']
        write_tensors(self.paths.models / 'checkpoints/no-clip.safetensors', shapes)
        self.assertEqual(self.library.choices('checkpoint'), [])
        self.assertTrue(self.item('checkpoints/no-clip.safetensors')['reason'])

    def test_checkpoint_without_vae_is_not_complete(self):
        shapes = {key: shape for key, shape in model_shapes('sdxl').items()
                  if not key.startswith('first_stage_model.')}
        write_tensors(self.paths.models / 'checkpoints/no-vae.safetensors', shapes)
        self.assertEqual(self.library.choices('checkpoint'), [])

    def test_sdxl_without_second_encoder_is_not_complete(self):
        shapes = model_shapes('sdxl')
        del shapes['conditioner.embedders.1.model.token_embedding.weight']
        write_tensors(self.paths.models / 'checkpoints/no-clip-g.safetensors', shapes)
        self.assertEqual(self.library.choices('checkpoint'), [])

    def test_inpaint_checkpoint_is_not_generic_checkpoint(self):
        shapes = model_shapes('sd15')
        shapes['model.diffusion_model.input_blocks.0.0.weight'] = [320, 9, 3, 3]
        write_tensors(self.paths.models / 'checkpoints/inpaint.safetensors', shapes)
        self.assertEqual(self.library.choices('checkpoint'), [])
        self.assertTrue(self.item('checkpoints/inpaint.safetensors')['reason'])

    def test_refiner_checkpoint_is_not_base_checkpoint(self):
        shapes = model_shapes('sdxl')
        shapes['model.diffusion_model.input_blocks.0.0.weight'] = [384, 4, 3, 3]
        shapes['model.diffusion_model.label_emb.0.0.weight'] = [1536, 2560]
        shapes['model.diffusion_model.input_blocks.4.1.transformer_blocks.0.attn2.to_k.weight'] = [768, 1280]
        write_tensors(self.paths.models / 'checkpoints/refiner.safetensors', shapes)
        self.assertEqual(self.library.choices('checkpoint'), [])

    def test_name_alone_never_proves_model_family(self):
        for name in ['checkpoints/sd_xl_base_1.0.safetensors',
                     'diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors',
                     'diffusion_models/Wan2.2_high.safetensors',
                     'vae/qwenImage21VAEOriginalBf16_v10.safetensors']:
            self.model(name, 'unknown')
        for role in ['checkpoint', 'kontext', 'wan_high', 'qwen_vae']:
            self.assertEqual(self.library.choices(role), [])

    def test_known_kontext_requires_flux_header(self):
        name = 'diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors'
        self.model(name, 'flux')
        self.assertEqual([item['id'] for item in self.library.choices('kontext')], [name])

    def test_unidentified_flux_variant_is_explained_and_excluded(self):
        self.model('unet/different-flux.safetensors', 'flux')
        self.assertEqual(self.library.choices('kontext'), [])
        item = self.item('unet/different-flux.safetensors')
        self.assertEqual(item['family'], 'flux')
        self.assertEqual(item['role'], 'unsupported')
        self.assertTrue(item['reason'])

    def test_wan_noise_phase_requires_both_header_and_declared_name(self):
        cases = [('Wan2.2_Remix_i2v_high_lighting.safetensors', 'wan_high'),
                 ('Wan2.2_Remix_i2v_low_lighting.safetensors', 'wan_low'),
                 ('Wan2.2_unmarked.safetensors', 'unsupported'),
                 ('Wan2.2_high_low.safetensors', 'unsupported'),
                 ('highlight.safetensors', 'unsupported')]
        for name, role in cases:
            self.model('diffusion_models/' + name, 'wan')
            self.assertEqual(self.item('diffusion_models/' + name)['role'], role)
        self.assertEqual(len(self.library.choices('wan_high')), 1)
        self.assertEqual(len(self.library.choices('wan_low')), 1)

    def test_wan_text_to_video_shape_cannot_enter_i2v_role(self):
        shapes = model_shapes('wan')
        shapes['patch_embedding.weight'] = [5120, 16, 1, 2, 2]
        write_tensors(self.paths.models / 'diffusion_models/Wan_high.safetensors', shapes)
        self.assertEqual(self.library.choices('wan_high'), [])

    def test_prefixed_wan22_i2v_without_clip_embedding_is_supported(self):
        shapes = model_shapes('wan')
        del shapes['img_emb.proj.0.bias']
        shapes = {'model.diffusion_model.' + key: value for key, value in shapes.items()}
        name = 'diffusion_models/Wan2.2_i2v_high.safetensors'
        write_tensors(self.paths.models / name, shapes)
        self.assertEqual([item['id'] for item in self.library.choices('wan_high')], [name])

    def test_direct_wan22_i2v_without_clip_embedding_is_supported(self):
        shapes = model_shapes('wan')
        del shapes['img_emb.proj.0.bias']
        name = 'diffusion_models/Wan2.2_i2v_low.safetensors'
        write_tensors(self.paths.models / name, shapes)
        self.assertEqual([item['id'] for item in self.library.choices('wan_low')], [name])

    def test_qwen_components_can_be_identified_in_checkpoint_folder(self):
        for family in ['qwen_model', 'qwen_encoder', 'qwen_vae']:
            name = 'checkpoints/' + family + '.safetensors'
            self.model(name, family)
            self.assertEqual([item['id'] for item in self.library.choices(family)], [name])
        self.assertEqual(self.library.choices('checkpoint'), [])

    def test_qwen_wrong_latent_or_encoder_or_rgba_shapes_are_rejected(self):
        cases = [('qwen_model', 'img_in.weight', [4096, 16]),
                 ('qwen_encoder', 'model.embed_tokens.weight', [151936, 2048]),
                 ('qwen_vae', 'decoder.head.2.weight', [3, 144, 1, 3, 3]),
                 ('qwen_vae', 'conv1.weight', [32, 16, 1, 1, 1])]
        for index, (family, key, shape) in enumerate(cases):
            with self.subTest(family=family, key=key):
                shapes = model_shapes(family)
                shapes[key] = shape
                name = f'checkpoints/bad-{index}.safetensors'
                write_tensors(self.paths.models / name, shapes)
                self.assertNotEqual(self.item(name)['role'], family)

    def test_lora_and_component_families_have_distinct_roles(self):
        for family in ['lora', 'clip_l', 't5', 'umt5', 'flux_vae', 'wan_vae']:
            name = 'checkpoints/' + family + '.safetensors'
            self.model(name, family)
            item = self.item(name)
            self.assertEqual(item['role'], family)
            self.assertEqual(item['family'], family)
        self.assertEqual(self.library.choices('checkpoint'), [])
        self.assertEqual(self.library.choices('wan_high'), [])

    def test_scan_is_recursive_only_in_fixed_model_folders(self):
        self.model('checkpoints/nested/valid.SAFETENSORS', 'sd15')
        self.model('elsewhere/hidden.safetensors', 'sd15')
        (self.paths.models / 'checkpoints/plain.pt').write_bytes(b'no model')
        self.assertEqual([item['id'] for item in self.library.inventory()],
                         ['checkpoints/nested/valid.SAFETENSORS'])

    def test_hardlinked_qwen_components_prefer_correct_loader_folder_once(self):
        for family, folder in [('qwen_model', 'diffusion_models'),
                               ('qwen_encoder', 'text_encoders'), ('qwen_vae', 'vae')]:
            original = 'checkpoints/' + family + '.safetensors'
            target = self.model(original, family)
            alias = folder + '/morph-ui-qwen21/' + family + '.safetensors'
            destination = self.paths.models / alias
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.link(target, destination)
            choices = self.library.choices(family)
            self.assertEqual([item['id'] for item in choices], [alias])
            self.assertIn(original, choices[0]['aliases'])
            self.assertEqual(self.library.resolve(original, family)['path'], str(target))
        self.assertEqual(len(self.library.inventory()), 3)

    def test_invalid_header_is_listed_with_reason_but_never_selected(self):
        path = self.paths.models / 'checkpoints/corrupt.safetensors'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'broken')
        item = self.item('checkpoints/corrupt.safetensors')
        self.assertEqual(item['role'], 'invalid')
        self.assertTrue(item['reason'])
        self.assertEqual(self.library.choices('checkpoint'), [])
        with self.assertRaises(UiError):
            self.library.resolve(item['id'], 'checkpoint')

    def test_duplicate_json_keys_are_rejected_at_every_level(self):
        cases = [b'{"x":{"dtype":"U8","shape":[1],"data_offsets":[0,1]},"x":{"dtype":"U8","shape":[1],"data_offsets":[0,1]}}',
                 b'{"x":{"dtype":"U8","dtype":"F16","shape":[1],"data_offsets":[0,1]}}',
                 b'{"__metadata__":{"kind":"one","kind":"two"},"x":{"dtype":"U8","shape":[1],"data_offsets":[0,1]}}']
        for index, header in enumerate(cases):
            name = f'checkpoints/duplicate-{index}.safetensors'
            write_raw(self.paths.models / name, header, 1)
            self.assertEqual(self.item(name)['role'], 'invalid')

    def test_header_size_and_truncation_are_bounded(self):
        path = self.paths.models / 'checkpoints/oversize.safetensors'
        path.parent.mkdir(parents=True)
        path.write_bytes(struct.pack('<Q', 8 * 1024 * 1024 + 1))
        self.assertEqual(self.item('checkpoints/oversize.safetensors')['role'], 'invalid')
        path.write_bytes(struct.pack('<Q', 200) + b'{}')
        self.assertEqual(self.item('checkpoints/oversize.safetensors')['role'], 'invalid')

    def test_tensor_structure_dtype_shape_offsets_and_size_are_validated(self):
        valid = {'dtype': 'U8', 'shape': [1], 'data_offsets': [0, 1]}
        cases = [None, {}, dict(valid, dtype='BAD'), dict(valid, shape=True),
                 dict(valid, shape=[True]), dict(valid, shape=[-1]),
                 dict(valid, shape=[1.0]), dict(valid, data_offsets=[False, 1]),
                 dict(valid, data_offsets=[0.0, 1]), dict(valid, data_offsets=[1, 0]),
                 dict(valid, data_offsets=[0, 2]), dict(valid, shape=[2]),
                 dict(valid, data_offsets=[-1, 0]), dict(valid, extra=7)]
        for index, tensor in enumerate(cases):
            with self.subTest(tensor=tensor):
                name = f'checkpoints/malformed-{index}.safetensors'
                write_raw(self.paths.models / name, json.dumps({'x': tensor}).encode(), 1)
                self.assertEqual(self.item(name)['role'], 'invalid')

    def test_header_top_level_metadata_and_nonfinite_values_are_validated(self):
        cases = [b'[]', b'{}', b'{"__metadata__":{"a":1}}',
                 b'{"x":{"dtype":"U8","shape":[NaN],"data_offsets":[0,1]}}',
                 b'{"__metadata__":[],"x":{"dtype":"U8","shape":[1],"data_offsets":[0,1]}}']
        for index, header in enumerate(cases):
            name = f'checkpoints/top-level-{index}.safetensors'
            write_raw(self.paths.models / name, header, 1)
            self.assertEqual(self.item(name)['role'], 'invalid')

    def test_data_offsets_must_cover_data_without_gaps_overlap_or_trailing_bytes(self):
        cases = [({'x': [1, 2]}, 2), ({'x': [0, 1], 'y': [0, 1]}, 1),
                 ({'x': [0, 1], 'y': [2, 3]}, 3), ({'x': [0, 1]}, 2)]
        for index, (offsets, data_size) in enumerate(cases):
            header = {key: {'dtype': 'U8', 'shape': [1], 'data_offsets': value}
                      for key, value in offsets.items()}
            name = f'checkpoints/gap-{index}.safetensors'
            write_raw(self.paths.models / name, json.dumps(header).encode(), data_size)
            self.assertEqual(self.item(name)['role'], 'invalid')

    def test_zero_size_tensors_and_scalar_tensor_are_valid(self):
        shapes = {'empty': [0, 100], 'scalar': [], 'empty-end': [0]}
        write_tensors(self.paths.models / 'vae/zero.safetensors', shapes)
        item = self.item('vae/zero.safetensors')
        self.assertEqual(item['role'], 'unsupported')
        self.assertEqual(item['family'], 'unknown')

    def test_excessive_tensor_rank_is_rejected_without_bigint_growth(self):
        # A final zero makes this empty, but multiplying the preceding dimensions
        # used to consume CPU before the parser ever reached that zero.
        tensor = {'dtype': 'U8', 'shape': [2 ** 63] * 30000 + [0],
                  'data_offsets': [0, 0]}
        name = 'vae/excessive-rank.safetensors'
        write_raw(self.paths.models / name, json.dumps({'x': tensor}).encode())
        self.assertEqual(self.item(name)['role'], 'invalid')

    def test_tensor_dimensions_larger_than_uint64_are_rejected_when_empty(self):
        tensor = {'dtype': 'U8', 'shape': [2 ** 64, 0], 'data_offsets': [0, 0]}
        name = 'vae/excessive-dimension.safetensors'
        write_raw(self.paths.models / name, json.dumps({'x': tensor}).encode())
        self.assertEqual(self.item(name)['role'], 'invalid')

    def test_empty_rank64_tensor_with_large_dimensions_and_scalar_are_valid(self):
        # The empty tensor occupies no bytes regardless of its other dimensions;
        # the rank-zero F16 scalar occupies exactly two bytes.
        tensors = {'empty': {'dtype': 'U8', 'shape': [2 ** 64 - 1] * 63 + [0],
                             'data_offsets': [0, 0]},
                   'scalar': {'dtype': 'F16', 'shape': [], 'data_offsets': [0, 2]}}
        name = 'vae/bounded-empty.safetensors'
        write_raw(self.paths.models / name, json.dumps(tensors).encode(), 2)
        self.assertEqual(self.item(name)['role'], 'unsupported')

    def test_nonempty_tensor_product_is_bounded_by_its_byte_span(self):
        tensors = [{'dtype': 'U8', 'shape': [2 ** 63] * 64, 'data_offsets': [0, 1]},
                   {'dtype': 'F16', 'shape': [2, 3], 'data_offsets': [0, 10]}]
        for index, tensor in enumerate(tensors):
            with self.subTest(index=index):
                name = f'vae/product-limit-{index}.safetensors'
                write_raw(self.paths.models / name, json.dumps({'x': tensor}).encode(),
                          tensor['data_offsets'][1])
                self.assertEqual(self.item(name)['role'], 'invalid')

    def test_inventory_reads_only_length_and_json_never_tensor_bytes(self):
        path = self.model('checkpoints/real.safetensors', 'sd15')
        with path.open('rb') as stream:
            header_size = struct.unpack('<Q', stream.read(8))[0]
        real_open = Path.open
        observed = []

        class HeaderOnly(io.BufferedReader):
            def read(self, size=-1):
                if self.tell() + size > 8 + header_size or size < 0:
                    raise AssertionError('Tensor bytes were requested')
                observed.append(size)
                return super().read(size)

        def limited_open(current, *args, **kwargs):
            if current == path:
                return HeaderOnly(io.FileIO(current, 'r'))
            return real_open(current, *args, **kwargs)

        with patch.object(Path, 'open', limited_open):
            self.assertEqual(len(self.library.choices('checkpoint')), 1)
        self.assertEqual(observed, [8, header_size])

    def test_resolve_accepts_only_literal_catalogued_ids_and_correct_role(self):
        name = 'checkpoints/good.safetensors'
        self.model(name, 'sd15')
        self.assertEqual(self.library.resolve(name, 'checkpoint')['id'], name)
        invalid = ['../checkpoints/good.safetensors', name.replace('/', '\\'),
                   str(self.paths.models / name), '/checkpoints/good.safetensors',
                   'checkpoints/./good.safetensors', 'checkpoints//good.safetensors',
                   'checkpoints/good.safetensors:stream', 'elsewhere/good.safetensors',
                   None, 1, {'id': name}]
        for model_id in invalid:
            with self.subTest(model_id=model_id), self.assertRaises(UiError):
                self.library.resolve(model_id, 'checkpoint')
        with self.assertRaises(UiError):
            self.library.resolve(name, 'kontext')
        with self.assertRaises(UiError):
            self.library.choices('unsupported-user-role')

    def test_resolve_reinspects_file_deleted_after_inventory(self):
        name = 'checkpoints/good.safetensors'
        path = self.model(name, 'sd15')
        self.library.inventory()
        path.unlink()
        with self.assertRaises(UiError):
            self.library.resolve(name, 'checkpoint')

    def test_resolve_rejects_family_replacement_and_corruption_after_inventory(self):
        name = 'checkpoints/good.safetensors'
        path = self.model(name, 'sd15')
        self.library.inventory()
        write_model(path, 'qwen_model')
        with self.assertRaises(UiError):
            self.library.resolve(name, 'checkpoint')
        path.write_bytes(b'not safetensors')
        with self.assertRaises(UiError):
            self.library.resolve(name, 'checkpoint')

    def test_resolve_rejects_same_family_file_replacement_after_inventory(self):
        name = 'checkpoints/good.safetensors'
        path = self.model(name, 'sd15')
        self.library.inventory()
        replacement = self.model('checkpoints/replacement.safetensors', 'sd15')
        replacement.replace(path)
        with self.assertRaises(UiError):
            self.library.resolve(name, 'checkpoint')

    def test_external_model_directory_junction_is_not_followed(self):
        if os.name != 'nt':
            self.skipTest('Windows junction characterization')
        import _winapi
        target = Path(self.temp.name) / 'outside'
        write_model(target / 'escaped.safetensors', 'sd15')
        self.paths.models.mkdir(parents=True, exist_ok=True)
        _winapi.CreateJunction(str(target), str(self.paths.models / 'checkpoints'))
        self.assertEqual(self.library.inventory(), [])
        with self.assertRaises(UiError):
            self.library.resolve('checkpoints/escaped.safetensors', 'checkpoint')

    def test_internal_model_directory_junction_is_not_followed(self):
        if os.name != 'nt':
            self.skipTest('Windows junction characterization')
        import _winapi
        target = self.root / 'inside-models'
        write_model(target / 'aliased.safetensors', 'sd15')
        checkpoints = self.paths.models / 'checkpoints'
        checkpoints.mkdir(parents=True)
        _winapi.CreateJunction(str(target), str(checkpoints / 'alias'))
        self.assertEqual(self.library.inventory(), [])

    def test_symlink_file_is_not_followed(self):
        target = self.model('vae/real.safetensors', 'sd15')
        link = self.paths.models / 'checkpoints/linked.safetensors'
        link.parent.mkdir(parents=True)
        try:
            os.symlink(target, link)
        except OSError as error:
            self.skipTest(f'File symlinks unavailable: {error}')
        self.assertEqual([item['id'] for item in self.library.inventory()], ['vae/real.safetensors'])
        with self.assertRaises(UiError):
            self.library.resolve('checkpoints/linked.safetensors', 'checkpoint')

    def test_model_root_replaced_with_junction_is_rejected(self):
        if os.name != 'nt':
            self.skipTest('Windows junction characterization')
        import _winapi
        target = Path(self.temp.name) / 'outside'
        write_model(target / 'checkpoints/escaped.safetensors', 'sd15')
        self.paths.models.parent.mkdir(parents=True, exist_ok=True)
        _winapi.CreateJunction(str(target), str(self.paths.models))
        self.assertEqual(self.library.inventory(), [])


if __name__ == '__main__':
    unittest.main()
