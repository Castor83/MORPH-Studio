import json
import sys
import unittest
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from support import Sandbox
from model_fixtures import write_model
from test_jobs import Compute
from test_provider import Wire
from morph_ui.providers.lmstudio import LMStudioProvider
from morph_ui.settings import SettingsStore


class ModelSelectionTests(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.paths = ProjectPaths(self.box.root)
        self.catalog = Catalog(self.paths)
        write_model(self.paths.models / 'checkpoints/sd15.safetensors', 'sd15')
        write_model(self.paths.models / 'checkpoints/not-a-base.safetensors', 'lora')

    def test_checkpoint_choice_replaces_only_loader_and_keeps_user_size(self):
        fields = self.catalog.controls('sdxl')
        self.assertIn('image_model', fields, 'Bildmodell-Auswahl fehlt')
        self.assertIn('checkpoints/sd15.safetensors', [x['id'] for x in fields['image_model']['options']])
        original = self.catalog.graph('sdxl')
        graph = self.catalog.build('sdxl', {'image_model':'checkpoints/sd15.safetensors', 'width':768}, {})
        self.assertEqual(graph['1']['inputs']['ckpt_name'], 'sd15.safetensors')
        self.assertEqual(graph['4']['inputs']['width'], 768)
        self.assertEqual(graph['4']['inputs']['height'], original['4']['inputs']['height'])
        self.assertEqual(self.catalog.graph('sdxl'), original)

    def test_missing_default_does_not_block_existing_alternative(self):
        self.assertIn('image_model', self.catalog.controls('sdxl'))
        (self.paths.models / 'checkpoints/sd_xl_base_1.0.safetensors').unlink()
        self.assertEqual(self.catalog.readiness('sdxl', {'image_model':'checkpoints/sd15.safetensors'}), [])
        self.assertEqual(self.catalog.build('sdxl', {'image_model':'checkpoints/sd15.safetensors'}, {})['1']['inputs']['ckpt_name'], 'sd15.safetensors')

    def test_wrong_role_traversal_and_disappeared_selection_are_rejected(self):
        self.assertIn('image_model', self.catalog.controls('sdxl'))
        for name in ['checkpoints/not-a-base.safetensors', '../sd15.safetensors', str(self.paths.models / 'checkpoints/sd15.safetensors')]:
            with self.subTest(name=name), self.assertRaises(UiError):
                self.catalog.build('sdxl', {'image_model':name}, {})
        (self.paths.models / 'checkpoints/sd15.safetensors').unlink()
        with self.assertRaises(UiError):
            self.catalog.build('sdxl', {'image_model':'checkpoints/sd15.safetensors'}, {})

    def test_wan_profile_changes_both_declared_noise_phases(self):
        self.assertIn('image_model', self.catalog.controls('wan'))
        write_model(self.paths.models / 'diffusion_models/MyWan_high_lighting.safetensors', 'wan')
        write_model(self.paths.models / 'diffusion_models/MyWan_low_lighting.safetensors', 'wan')
        image = self.paths.input / 'own.png'
        image.write_bytes(b'own image path fixture')
        graph = self.catalog.build('wan', {'image_model':'diffusion_models/MyWan_high_lighting.safetensors'}, {'image':'own.png'})
        self.assertEqual(graph['135']['inputs']['unet_name'], 'MyWan_high_lighting.safetensors')
        self.assertEqual(graph['136']['inputs']['unet_name'], 'MyWan_low_lighting.safetensors')
        (self.paths.models / 'diffusion_models/MyWan_low_lighting.safetensors').unlink()
        with self.assertRaises(UiError):
            self.catalog.build('wan', {'image_model':'diffusion_models/MyWan_high_lighting.safetensors'}, {'image':'own.png'})

    def test_qwen_has_own_encoder_vae_and_native_text_node(self):
        self.assertIn('qwen21', [x['id'] for x in self.catalog.list_entries()], 'Qwen-Workflow fehlt')
        files = {'diffusion_models/morph-ui-qwen21/noctQUncensoredRealismBuiltOn_v40Base_fp16.safetensors':'qwen_model', 'text_encoders/morph-ui-qwen21/qwenImage21TextEncoderOriginal_v10_3241887.safetensors':'qwen_encoder', 'vae/morph-ui-qwen21/qwenImage21VAEOriginalBf16_v10.safetensors':'qwen_vae'}
        for relative, family in files.items():
            write_model(self.paths.models / relative, family)
        graph = self.catalog.build('qwen21', {'width':512, 'height':512}, {})
        self.assertEqual(graph['1']['class_type'], 'UNETLoader')
        self.assertEqual(graph['2']['inputs']['type'], 'qwen_image')
        self.assertEqual(graph['3']['class_type'], 'VAELoader')
        self.assertEqual(graph['6']['class_type'], 'TextEncodeQwenImage21')
        self.assertEqual(graph['5']['inputs']['positive'], ['6',0])
        self.assertEqual(graph['5']['inputs']['negative'], ['6',1])
        self.assertEqual(graph['4']['inputs']['width'], 512)

    def test_wan_pair_preserves_parent_directory_named_high(self):
        parent = 'diffusion_models/high-quality/'
        write_model(self.paths.models / (parent + 'MyWan_high_lighting.safetensors'), 'wan')
        write_model(self.paths.models / (parent + 'MyWan_low_lighting.safetensors'), 'wan')
        low = self.catalog.wan_low(parent + 'MyWan_high_lighting.safetensors')
        self.assertEqual(low['id'], parent + 'MyWan_low_lighting.safetensors')


class ModelSelectionJobTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.box = Sandbox(self)
        self.paths = ProjectPaths(self.box.root)
        self.catalog = Catalog(self.paths)
        self.files = FileStore(self.paths)
        self.addCleanup(self.files.close)
        self.compute = Compute(self.paths)
        self.jobs = JobService(self.paths, self.catalog, self.files, self.compute)
        self.addCleanup(self.jobs.close)
        write_model(self.paths.models / 'checkpoints/sd15.safetensors', 'sd15')

    async def test_job_records_actual_selected_model_before_submit(self):
        self.assertIn('image_model', self.catalog.controls('sdxl'))
        job = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {'image_model':'checkpoints/sd15.safetensors'}, {})
        self.assertEqual(job['state'], 'queued', job.get('error'))
        self.assertEqual(job['controls']['image_model'], 'checkpoints/sd15.safetensors')
        self.assertEqual(job['graph']['1']['inputs']['ckpt_name'], 'sd15.safetensors')

    async def test_bad_model_prevents_service_start_and_submission(self):
        self.assertIn('image_model', self.catalog.controls('sdxl'))
        job = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {'image_model':'vae/ae.safetensors'}, {})
        self.assertEqual(job['state'], 'error')
        self.assertEqual(self.compute.started, 0)
        self.assertEqual(self.compute.submissions, [])

    async def test_language_proposal_cannot_change_user_image_model(self):
        self.assertIn('image_model', self.catalog.controls('sdxl'))
        wire = Wire()
        provider = LMStudioProvider(SettingsStore(self.paths), self.catalog, wire)
        wire.content = json.dumps({'assistant_text':'Modell wechseln', 'prompt':'A red mug.', 'controls':{'image_model':'checkpoints/sd15.safetensors'}})
        with self.assertRaises(UiError):
            await provider.propose('chosen-instance', 'sdxl', 'Eine Tasse', self.catalog.controls('sdxl'))
        props = wire.calls[-1][2]['response_format']['json_schema']['schema']['properties']['controls']['properties']
        self.assertNotIn('image_model', props)


if __name__ == '__main__':
    unittest.main()
