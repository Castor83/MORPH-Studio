import importlib
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths, UiError
from support import Sandbox
from model_fixtures import write_model
try:
    register = importlib.import_module('register_qwen_paths').register
except ModuleNotFoundError:
    register = None

FILES = [('noctQUncensoredRealismBuiltOn_v40Base_fp16.safetensors','diffusion_models','qwen_model'), ('qwenImage21TextEncoderOriginal_v10_3241887.safetensors','text_encoders','qwen_encoder'), ('qwenImage21VAEOriginalBf16_v10.safetensors','vae','qwen_vae')]

class ModelLinkTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(register,'Sichere Qwen-Dateizuordnung fehlt')
        self.box = Sandbox(self)
        self.paths = ProjectPaths(self.box.root)
        for name,directory,role in FILES:
            write_model(self.paths.models / 'checkpoints' / name, role)

    def test_links_share_existing_weights_and_register_is_idempotent(self):
        result = register(self.paths)
        self.assertEqual(len(result),3)
        for name,directory,role in FILES:
            source = self.paths.models / 'checkpoints' / name
            target = self.paths.models / directory / 'morph-ui-qwen21' / name
            self.assertTrue(os.path.samefile(source,target))
        again = register(self.paths)
        self.assertTrue(all(not item['created'] for item in again))

    def test_foreign_destination_prevents_all_link_changes(self):
        name,directory,_ = FILES[1]
        target = self.paths.models / directory / 'morph-ui-qwen21' / name
        target.parent.mkdir()
        target.write_bytes(b'preserve this existing file')
        with self.assertRaises(UiError):
            register(self.paths)
        self.assertEqual(target.read_bytes(),b'preserve this existing file')
        self.assertFalse((self.paths.models / FILES[0][1] / 'morph-ui-qwen21' / FILES[0][0]).exists())
