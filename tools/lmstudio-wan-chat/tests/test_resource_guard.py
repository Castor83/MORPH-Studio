from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'start_mcp.py'
spec = importlib.util.spec_from_file_location('resource_guard_fixture', SOURCE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ResourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='resource-guard-', dir=SOURCE.parents[2] / 'temp')
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name)
        self.receipt = {'schema_version':1, 'managed':True, 'state':'running', 'pid':123,
            'creation_filetime':'134055000000000123', 'project_root':str(guard.ROOT),
            'python':str(guard.PYTHON), 'script':str(guard.ROOT / 'ComfyUI_windows_portable/ComfyUI/main.py')}
        self.receipt_path = self.report / 'mcp-comfy-owned.json'
        self.handle = object()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(guard, 'REPORT_DIR', self.report))
        self.open = self.stack.enter_context(patch.object(guard, 'open_process_for_query', return_value=self.handle, create=True))
        self.close = self.stack.enter_context(patch.object(guard, 'close_process_handle', create=True))
        self.kernel = SimpleNamespace(WaitForSingleObject=Mock(return_value=258))
        self.stack.enter_context(patch.object(guard, 'process_kernel', return_value=self.kernel))
        self.creation = self.stack.enter_context(patch.object(guard, 'process_creation_filetime', return_value=self.receipt['creation_filetime']))
        self.exe = self.stack.enter_context(patch.object(guard, 'process_executable', return_value=str(guard.PYTHON)))
        self.listener = self.stack.enter_context(patch.object(guard, 'inspect_listener_details', return_value={'ownership':'owned','pid':123}))
        self.stop = self.stack.enter_context(patch.object(guard, 'terminate_process_handle', side_effect=AssertionError('no termination')))
        self.stack.enter_context(patch.object(guard, 'save_owned_receipt', side_effect=AssertionError('read only')))
        self.stack.enter_context(patch.object(guard, 'ensure_comfy', side_effect=AssertionError('no startup')))

    def inspect(self):
        method = getattr(guard, 'inspect_managed_listener', None)
        self.assertTrue(callable(method), 'Lesender Nachweis der eigenen verwalteten Instanz fehlt')
        return method()

    def test_valid_receipt_checks_current_listener_and_same_handle_without_writes(self):
        self.receipt_path.write_text(json.dumps(self.receipt), encoding='utf-8')
        original = self.receipt_path.read_bytes()
        self.assertEqual(self.inspect(), {'managed':True, 'pid':123})
        self.open.assert_called_once_with(123)
        self.close.assert_called_once_with(self.handle)
        self.assertTrue(all(call.args == (self.handle,) for call in self.creation.call_args_list))
        self.stop.assert_not_called()
        self.assertEqual(self.receipt_path.read_bytes(), original)

    def test_missing_adopted_old_and_wrong_project_receipts_never_open_handle(self):
        self.assertTrue(callable(getattr(guard, 'inspect_managed_listener', None)), 'Lesender Nachweis fehlt')
        with self.assertRaises(guard.StartupError):
            self.inspect()
        for changed in [{'schema_version':True}, {'schema_version':2}, {'managed':False}, {'state':'stopped'},
                        {'pid':True}, {'creation_filetime':'0'}, {'creation_filetime':str(2**64)},
                        {'project_root':'D:/other'}, {'python':'D:/other/python.exe'}, {'script':'D:/other/main.py'}]:
            with self.subTest(changed=changed):
                self.receipt_path.write_text(json.dumps(dict(self.receipt, **changed)), encoding='utf-8')
                with self.assertRaises(guard.StartupError):
                    self.inspect()
        self.open.assert_not_called()

    def test_dead_reused_or_changed_process_and_listener_are_rejected_and_closed(self):
        self.receipt_path.write_text(json.dumps(self.receipt), encoding='utf-8')
        self.assertTrue(callable(getattr(guard, 'inspect_managed_listener', None)), 'Lesender Nachweis fehlt')
        changes = [(self.creation, '134055000000000122'), (self.exe, 'D:/other/python.exe'),
                   (self.listener, {'ownership':'compatible','pid':123}),
                   (self.listener, {'ownership':'owned','pid':456}),
                   (self.kernel.WaitForSingleObject, 0)]
        for function, value in changes:
            old = function.return_value
            function.return_value = value
            self.close.reset_mock()
            with self.subTest(value=value), self.assertRaises(guard.StartupError):
                self.inspect()
            self.close.assert_called_once_with(self.handle)
            function.return_value = old
        self.stop.assert_not_called()

    def test_query_handle_requests_no_terminate_access(self):
        # Undo only the fixture replacement to inspect the actual native access mask.
        self.open.side_effect = None
        self.stack.close()
        method = getattr(guard, 'open_process_for_query', None)
        self.assertTrue(callable(method), 'Lesender Prozesshandle fehlt')
        kernel = SimpleNamespace(OpenProcess=Mock(return_value=self.handle))
        with patch.object(guard, 'process_kernel', return_value=kernel):
            handle = guard.open_process_for_query(123)
        self.assertIs(handle, self.handle)
        kernel.OpenProcess.assert_called_once_with(0x1000 | 0x100000, False, 123)


if __name__ == '__main__':
    unittest.main()
