import importlib.util
import io
import json
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from email.message import Message
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.response import addinfourl


SOURCE = Path(__file__).resolve().parents[1] / "start_mcp.py"
if SOURCE.is_file():
    spec = importlib.util.spec_from_file_location("wan_start_mcp", SOURCE)
    starter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = starter
    spec.loader.exec_module(starter)
else:
    starter = None


class ChildProcess:
    pid = 12345
    _handle = object()

    def poll(self):
        return None


class StartMcpTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(starter, "Der Hintergrundstarter fehlt noch.")
        self.temp = tempfile.TemporaryDirectory(prefix="start-mcp-test-", dir=SOURCE.parents[2] / "reports/wan-lmstudio")
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name)
        self.paths = patch.object(starter, "REPORT_DIR", self.report)
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.creation = patch.object(starter, 'process_creation_filetime', return_value='134055000000000123')
        self.creation.start()
        self.addCleanup(self.creation.stop)

    def own_record(self, **changed):
        record = {
            "pid": 156064, "address": "127.0.0.1",
            "exe": r"E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe",
            "cmd": ('"E:\\MORPH-Studio\\ComfyUI_windows_portable\\python_embeded\\python.exe" '
                    '-s ComfyUI\\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 '
                    '--offline --input-directory E:\\MORPH-Studio\\input '
                    '--output-directory E:\\MORPH-Studio\\output '
                    '--temp-directory E:\\MORPH-Studio\\temp\\comfyui '
                    '--user-directory E:\\MORPH-Studio\\user --disable-auto-launch')}
        return dict(record, **changed)

    def inspect_details(self, records):
        inspect = getattr(starter, "inspect_listener_details", None)
        self.assertTrue(callable(inspect), "Die Prozessdiagnose muss konkrete Erkennungsgründe liefern.")
        with patch.object(starter, "powershell_json", return_value=records):
            return inspect()

    def test_equals_option_syntax_recognizes_own_service(self):
        record = self.own_record()
        for name, value in [('--listen', '127.0.0.1'), ('--port', '8188'),
                            ('--input-directory', r'E:\MORPH-Studio\input'),
                            ('--output-directory', r'E:\MORPH-Studio\output'),
                            ('--temp-directory', r'E:\MORPH-Studio\temp\comfyui'),
                            ('--user-directory', r'E:\MORPH-Studio\user')]:
            with self.subTest(option=name):
                changed = dict(record, cmd=record['cmd'].replace(name + ' ' + value, name + '=' + value))
                self.assertEqual(starter.classify_listeners([changed]), ('owned', 156064))

    def test_duplicate_option_syntax_never_grants_ownership(self):
        record = self.own_record()
        for extra in [' --port=8188', ' --port 8188', ' --listen=127.0.0.1',
                      r' --output-directory=E:\MORPH-Studio\output']:
            with self.subTest(extra=extra):
                self.assertEqual(starter.classify_listeners([dict(record, cmd=record['cmd'] + extra)]),
                                 ('foreign', 156064))

    def test_listener_diagnostics_identify_rejected_option(self):
        record = self.own_record()
        for command, reason in [(record['cmd'].replace('--port 8188', '--port 9191'), '--port'),
                                (record['cmd'].replace('--offline ', ''), '--offline'),
                                (record['cmd'] + ' --port=8188', 'mehrfach')]:
            with self.subTest(reason=reason):
                details = self.inspect_details([dict(record, cmd=command)])
                self.assertEqual((details['ownership'], details['pid']), ('foreign', 156064))
                self.assertIn(reason, details['message'])

    def test_listener_diagnostics_distinguish_unreadable_metadata(self):
        details = self.inspect_details([self.own_record(exe=None, cmd=None)])
        self.assertEqual((details['ownership'], details['pid']), ('foreign', 156064))
        self.assertIn('lesbar', details['message'])

    def test_listener_diagnostics_preserve_tuple_api(self):
        for records, expected in [([], ('free', None)), ([self.own_record()], ('owned', 156064)),
                                  ([self.own_record(address='0.0.0.0')], ('foreign', 156064))]:
            with self.subTest(expected=expected):
                details = self.inspect_details(records)
                self.assertEqual((details['ownership'], details['pid']), expected)
                with patch.object(starter, 'powershell_json', return_value=records):
                    self.assertEqual(starter.inspect_listener(), expected)

    def test_compatible_foreign_api_is_reused_without_process_management(self):
        record = self.own_record(exe=r'C:\external\python.exe')
        with patch.object(starter, 'powershell_json', return_value=[record]), \
             patch.object(starter, 'service_ready', return_value=True), \
             patch.object(starter.subprocess, 'Popen', side_effect=AssertionError('Kein weiterer Prozess')):
            self.assertEqual(starter.ensure_comfy(), 156064)
        state = json.loads((self.report / 'mcp-comfy-start.json').read_text())
        self.assertEqual(state['state'], 'ready')
        self.assertFalse(state['managed'])
        self.assertIsNone(state['launcher_pid'])

    def test_compatible_api_is_reused_when_process_metadata_is_unavailable(self):
        with patch.object(starter, 'powershell_json', side_effect=starter.StartupError('Prozessdaten fehlen')), \
             patch.object(starter, 'service_ready', return_value=True), \
             patch.object(starter.subprocess, 'Popen', side_effect=AssertionError('Kein weiterer Prozess')):
            self.assertIsNone(starter.ensure_comfy())
        state = json.loads((self.report / 'mcp-comfy-start.json').read_text())
        self.assertEqual(state['state'], 'ready')
        self.assertFalse(state['managed'])
        self.assertIn('Prozessdaten fehlen', state['message'])

    def test_incompatible_occupied_port_reports_reason_without_starting(self):
        record = self.own_record(exe=r'C:\external\python.exe')
        with patch.object(starter, 'powershell_json', return_value=[record]), \
             patch.object(starter, 'service_ready', return_value=False), \
             patch.object(starter.subprocess, 'Popen', side_effect=AssertionError('Belegter Port')):
            with self.assertRaises(starter.StartupError) as raised:
                starter.ensure_comfy(startup_timeout=0)
        self.assertIn('156064', str(raised.exception))
        self.assertIn('API', str(raised.exception))
        self.assertIn('Python', str(raised.exception))
        state = json.loads((self.report / 'mcp-comfy-start.json').read_text())
        self.assertEqual(state['state'], 'error')
        self.assertIn(str(raised.exception), (self.report / 'mcp-comfy-start.log').read_text(encoding='utf-8'))

    def test_unavailable_api_and_unreadable_listener_never_start_blindly(self):
        with patch.object(starter, 'powershell_json', side_effect=starter.StartupError('Prozessdaten fehlen')), \
             patch.object(starter, 'service_ready', return_value=False), \
             patch.object(starter.subprocess, 'Popen', side_effect=AssertionError('Unbekannter Portzustand')):
            with self.assertRaises(starter.StartupError) as raised:
                starter.ensure_comfy(startup_timeout=0)
        self.assertIn('Prozessdaten fehlen', str(raised.exception))
        self.assertIn('API', str(raised.exception))

    def test_service_readiness_requires_core_image_api_schemas(self):
        payloads = {
            '/system_stats': {'system': {'comfyui_version': '0.39.0'}},
            '/queue': {'queue_running': [], 'queue_pending': []},
            '/object_info/LoadImage': {'LoadImage': {'input': {'required': {'image': [['input.png']]}}}},
            '/object_info/SaveImage': {'SaveImage': {'input': {'required': {'images': ['IMAGE']}}}},
        }

        class Response(io.BytesIO):
            status = 200

        class Opener:
            def open(self, url, timeout):
                return Response(json.dumps(payloads[url.removeprefix('http://127.0.0.1:8188')]).encode())

        with patch.object(starter.urllib.request, 'build_opener', return_value=Opener()):
            self.assertTrue(starter.service_ready())
            payloads['/object_info/SaveImage'] = {'OtherNode': {}}
            self.assertFalse(starter.service_ready(), 'Ein beliebiger JSON-Dienst ist keine Bild-API.')

    def test_service_readiness_never_follows_redirect_to_another_service(self):
        visited = []
        responses = {
            '/system_stats': {'system': {'comfyui_version': '0.39.0'}},
            '/queue': {'queue_running': [], 'queue_pending': []},
            '/object_info/LoadImage': {'LoadImage': {'input': {'required': {'image': [['input.png']]}}}},
            '/object_info/SaveImage': {'SaveImage': {'input': {'required': {'images': ['IMAGE']}}}},
        }

        class SimulatedNetwork(starter.urllib.request.HTTPHandler):
            def http_open(self, request):
                visited.append(request.full_url)
                headers = Message()
                status = 200
                if request.full_url == 'http://127.0.0.1:8188/system_stats':
                    headers['Location'] = 'http://remote.invalid/system_stats'
                    status = 302
                body = json.dumps(responses[request.selector]).encode()
                response = addinfourl(io.BytesIO(body), headers, request.full_url, status)
                response.msg = 'Found' if status == 302 else 'OK'
                return response

        build_opener = starter.urllib.request.build_opener

        def simulated_opener(*handlers):
            return build_opener(*handlers, SimulatedNetwork())

        with patch.object(starter.urllib.request, 'build_opener', side_effect=simulated_opener):
            self.assertFalse(starter.service_ready(), 'Eine Umleitung bestätigt keine lokale ComfyUI-API.')
        self.assertEqual(visited, ['http://127.0.0.1:8188/system_stats'])

    def test_starts_the_application_when_the_shell_launcher_cannot_start_it(self):
        portable = self.report / "ComfyUI_windows_portable"
        app = portable / "ComfyUI"
        app.mkdir(parents=True)
        marker = self.report / "application-started.json"
        (app / "main.py").write_text(
            "import json, os, sys\nfrom pathlib import Path\n"
            "Path(" + repr(str(marker)) + ").write_text(json.dumps({"
            "'cwd': os.getcwd(), 'args': sys.argv[1:], "
            "'offline': os.environ.get('HF_HUB_OFFLINE'), "
            "'yolo': os.environ.get('YOLO_CONFIG_DIR')}))\n",
            encoding="utf-8")
        broken_shell = self.report / "legacy-start.ps1"
        broken_shell.write_text("exit 0\n", encoding="utf-8")
        with patch.object(starter, "ROOT", self.report), \
             patch.object(starter, "PYTHON", Path(sys.executable)), \
             patch.object(starter, "START_SCRIPT", broken_shell):
            child = starter.start_comfy({})
            self.addCleanup(lambda: child.kill() if child.poll() is None else None)
            self.assertEqual(child.wait(timeout=15), 0)
        self.assertTrue(marker.is_file(), "The ComfyUI application must run, even when the old shell exits without starting it")
        observed = json.loads(marker.read_text())
        self.assertEqual(Path(observed["cwd"]), portable)
        self.assertEqual(observed["args"], [
            "--windows-standalone-build", "--listen", "127.0.0.1", "--port", "8188", "--offline",
            "--input-directory", str(self.report / "input"),
            "--output-directory", str(self.report / "output"),
            "--temp-directory", str(self.report / "temp/comfyui"),
            "--user-directory", str(self.report / "user"), "--disable-auto-launch"])
        self.assertEqual(observed["offline"], "1")
        self.assertEqual(observed["yolo"], str(self.report / "cache/ultralytics"))

    def test_recognizes_own_python_before_it_binds_the_port(self):
        command = ('"E:\\MORPH-Studio\\ComfyUI_windows_portable\\python_embeded\\python.exe" '
                   '-s ComfyUI\\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 '
                   '--offline --input-directory E:\\MORPH-Studio\\input '
                   '--output-directory E:\\MORPH-Studio\\output '
                   '--temp-directory E:\\MORPH-Studio\\temp\\comfyui '
                   '--user-directory E:\\MORPH-Studio\\user --disable-auto-launch')
        record = {"exe": str(starter.PYTHON), "cmd": command}
        with patch.object(starter, "powershell_json", return_value=record):
            self.assertTrue(starter.own_launcher_alive(12345), "An own ComfyUI still booting must not be started twice")
        for wrong in [dict(record, exe=r"C:\other\python.exe"),
                      dict(record, cmd=command.replace("127.0.0.1", "0.0.0.0")),
                      dict(record, cmd=command.replace(r"E:\MORPH-Studio\input", r"D:\other\input"))]:
            with patch.object(starter, "powershell_json", return_value=wrong):
                self.assertFalse(starter.own_launcher_alive(12345))

    def test_reuses_own_ready_service_without_launching(self):
        with patch.object(starter, "inspect_listener_details", return_value={"ownership": "owned", "pid": 156064, "message": "Eigenes Startprofil"}), \
             patch.object(starter, "service_ready", return_value=True), \
             patch.object(starter.subprocess, "Popen") as launch:
            self.assertEqual(starter.ensure_comfy(), 156064)
        launch.assert_not_called()
        self.assertEqual(json.loads((self.report / "mcp-comfy-start.json").read_text())["comfy_pid"], 156064)

    def test_free_port_launches_once_hidden_and_waits_for_readiness(self):
        with patch.object(starter, "inspect_listener_details", side_effect=[
                {"ownership": "free", "pid": None, "message": "Port frei"},
                {"ownership": "free", "pid": None, "message": "Port frei"},
                {"ownership": "owned", "pid": 12345, "message": "Eigenes Startprofil"}]), \
             patch.object(starter, "service_ready", side_effect=[False, False, True]), \
             patch.object(starter.subprocess, "Popen", return_value=ChildProcess()) as launch:
            self.assertEqual(starter.ensure_comfy(), 12345)
        self.assertEqual(launch.call_count, 1)
        args, options = launch.call_args
        self.assertEqual(args[0][:3], [str(starter.PYTHON), "-s", r"ComfyUI\main.py"])
        self.assertEqual(options["cwd"], r"E:\MORPH-Studio\ComfyUI_windows_portable")
        self.assertTrue(options["creationflags"] & starter.subprocess.CREATE_NO_WINDOW)
        state = json.loads((self.report / "mcp-comfy-start.json").read_text())
        self.assertEqual(state["launcher_pid"], 12345)
        self.assertTrue(state['managed'])

    def test_incompatible_foreign_listener_is_rejected_without_launch(self):
        with patch.object(starter, "inspect_listener_details", return_value={"ownership": "foreign", "pid": 999, "message": "Anderer Python-Pfad"}), \
             patch.object(starter, "service_ready", return_value=False), \
             patch.object(starter.subprocess, "Popen") as launch:
            with self.assertRaises(starter.StartupError):
                starter.ensure_comfy()
        launch.assert_not_called()
        self.assertIn("error", (self.report / "mcp-comfy-start.log").read_text())

    def test_launch_failure_is_logged_and_never_retried(self):
        with patch.object(starter, "inspect_listener_details", return_value={"ownership": "free", "pid": None, "message": "Port frei"}), \
             patch.object(starter, "service_ready", return_value=False), \
             patch.object(starter.subprocess, "Popen", side_effect=OSError("launch denied")) as launch:
            with self.assertRaises(starter.StartupError):
                starter.ensure_comfy()
        self.assertEqual(launch.call_count, 1)
        self.assertIn("launch denied", (self.report / "mcp-comfy-start.log").read_text())

    def test_readiness_timeout_retains_launcher_pid_without_retry(self):
        with patch.object(starter, "inspect_listener_details", return_value={"ownership": "free", "pid": None, "message": "Port frei"}), \
             patch.object(starter, "service_ready", return_value=False), \
             patch.object(starter.subprocess, "Popen", return_value=ChildProcess()) as launch:
            with self.assertRaises(starter.StartupError):
                starter.ensure_comfy(startup_timeout=0)
        self.assertEqual(launch.call_count, 1)
        state = json.loads((self.report / "mcp-comfy-start.json").read_text())
        self.assertEqual(state["launcher_pid"], 12345)
        self.assertEqual(state["state"], "error")

    def test_two_simultaneous_callers_start_only_one_service(self):
        running = threading.Event()
        results, failures = [], []

        def inspect():
            return {"ownership": "owned", "pid": 12345, "message": "Eigenes Startprofil"} if running.is_set() else {
                "ownership": "free", "pid": None, "message": "Port frei"}

        def launch(*args, **kwargs):
            time.sleep(0.05)
            running.set()
            return ChildProcess()

        def call():
            try:
                results.append(starter.ensure_comfy())
            except Exception as error:
                failures.append(error)

        with patch.object(starter, "inspect_listener_details", side_effect=inspect), \
             patch.object(starter, "service_ready", side_effect=running.is_set), \
             patch.object(starter.subprocess, "Popen", side_effect=launch) as spawn:
            threads = [threading.Thread(target=call) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(3)
            self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        self.assertEqual(sorted(results), [12345, 12345])
        self.assertEqual(spawn.call_count, 1)

    def test_own_identity_requires_exact_paths_and_local_binding(self):
        command = ('"E:\\MORPH-Studio\\ComfyUI_windows_portable\\python_embeded\\python.exe" '
                   '-s ComfyUI\\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 '
                   '--offline --input-directory E:\\MORPH-Studio\\input '
                   '--output-directory E:\\MORPH-Studio\\output '
                   '--temp-directory E:\\MORPH-Studio\\temp\\comfyui '
                   '--user-directory E:\\MORPH-Studio\\user --disable-auto-launch')
        record = {"pid": 156064, "address": "127.0.0.1", "exe": r"E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe", "cmd": command}
        self.assertEqual(starter.classify_listeners([record]), ("owned", 156064))
        for changed in [dict(record, address="0.0.0.0"), dict(record, exe=r"C:\other\python.exe"),
                        dict(record, cmd=command.replace(r"E:\MORPH-Studio\output", r"D:\other\output")),
                        dict(record, cmd=command + r" --output-directory=D:\other\output"),
                        dict(record, cmd=command + " --listen=0.0.0.0"),
                        dict(record, cmd=command.replace(r"-s ComfyUI\main.py", r"other.py --config ComfyUI\main.py")),
                        dict(record, cmd=command.replace(r"-s ComfyUI\main.py", r"-c print(1) ComfyUI\main.py"))]:
            with self.subTest(command=changed["cmd"], exe=changed["exe"], address=changed["address"]):
                self.assertEqual(starter.classify_listeners([changed])[0], "foreign")

    def test_existing_live_launcher_is_waited_for_without_duplicate_start(self):
        (self.report / "mcp-comfy-start.json").write_text(json.dumps({"launcher_pid": 12345, "state": "starting"}))
        with patch.object(starter, "inspect_listener_details", side_effect=[
                {"ownership": "free", "pid": None, "message": "Port frei"},
                {"ownership": "owned", "pid": 9876, "message": "Eigenes Startprofil"}]), \
             patch.object(starter, "own_launcher_alive", return_value=True), \
             patch.object(starter, "service_ready", side_effect=[False, True]), \
             patch.object(starter.subprocess, "Popen") as launch:
            self.assertEqual(starter.ensure_comfy(), 9876)
        launch.assert_not_called()

    def test_schema_discovery_serves_mcp_when_comfy_start_is_unavailable(self):
        marker = self.report / "schema-served.json"
        server = self.report / "schema_server.py"
        server.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('{\"served\": true}')\n",
                          encoding="utf-8")
        with patch.object(starter.sys, "argv", [str(SOURCE), "--no-autostart"]), \
             patch.object(starter, "MCP_SERVER", server), \
             patch.object(starter, "ensure_comfy", side_effect=starter.StartupError("slow unavailable service")):
            result = starter.main()
        self.assertEqual(result, 0, "Schema discovery must not await the slow image service")
        self.assertEqual(json.loads(marker.read_text()), {"served": True})


class ManagedProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='managed-stop-test-', dir=SOURCE.parents[2] / 'reports/wan-lmstudio')
        self.addCleanup(self.temp.cleanup)
        self.report = Path(self.temp.name)
        self.report_patch = patch.object(starter, 'REPORT_DIR', self.report)
        self.report_patch.start()
        self.addCleanup(self.report_patch.stop)
        self.record = StartMcpTests.own_record(self, pid=12345)
        self.receipt = {'schema_version': 1, 'managed': True, 'state': 'running', 'pid': 12345,
                        'creation_filetime': '134055000000000123', 'project_root': r'E:\MORPH-Studio',
                        'python': r'E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe',
                        'script': r'E:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\main.py'}
        self.receipt_path = self.report / 'mcp-comfy-owned.json'
        self.handle = object()
        self.events = []

    def call_stop(self):
        stop = getattr(starter, 'stop_managed', None)
        self.assertTrue(callable(stop), 'Stop benötigt eine eigene Startquittung und dieselbe Prozessidentität.')
        with ExitStack() as stack:
            stack.enter_context(patch.object(starter, 'open_process_for_stop', return_value=self.handle, create=True))
            stack.enter_context(patch.object(starter, 'process_creation_filetime', return_value='134055000000000123', create=True))
            stack.enter_context(patch.object(starter, 'process_executable', return_value=self.receipt['python'], create=True))
            stack.enter_context(patch.object(starter, 'powershell_json', return_value=self.record))
            stack.enter_context(patch.object(starter, 'terminate_process_handle',
                                             side_effect=lambda handle: self.events.append(('stop', handle)), create=True))
            stack.enter_context(patch.object(starter, 'close_process_handle',
                                             side_effect=lambda handle: self.events.append(('close', handle)), create=True))
            stack.enter_context(patch.object(starter, 'service_ready', side_effect=AssertionError('Stop prüft keine API')))
            return stop()

    def test_stop_without_own_receipt_never_uses_a_listener_as_authority(self):
        with self.assertRaises(starter.StartupError):
            self.call_stop()
        self.assertEqual(self.events, [])

    def test_old_adopted_and_mismatched_receipts_never_stop(self):
        cases = [dict(self.receipt, managed=False), dict(self.receipt, state='stopped'),
                 dict(self.receipt, project_root=r'D:\other'), dict(self.receipt, pid=True),
                 dict(self.receipt, creation_filetime=''), dict(self.receipt, schema_version=99),
                 dict(self.receipt, python=r'C:\other\python.exe'),
                 dict(self.receipt, script=r'C:\other\main.py')]
        legacy = dict(self.receipt)
        legacy.pop('creation_filetime')
        cases.append(legacy)
        for receipt in cases:
            with self.subTest(receipt=receipt):
                self.receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
                with self.assertRaises(starter.StartupError):
                    self.call_stop()
                self.assertEqual(self.events, [])

    def test_reused_pid_with_different_creation_filetime_is_rejected(self):
        self.receipt_path.write_text(json.dumps(dict(self.receipt, creation_filetime='134055000000000122')), encoding='utf-8')
        with self.assertRaises(starter.StartupError):
            self.call_stop()
        self.assertEqual(self.events, [('close', self.handle)])

    def test_matching_own_receipt_stops_only_the_verified_handle(self):
        self.receipt_path.write_text(json.dumps(self.receipt), encoding='utf-8')
        result = self.call_stop()
        self.assertTrue(result['stopped'])
        self.assertEqual(result['pid'], 12345)
        self.assertEqual(self.events, [('stop', self.handle), ('close', self.handle)])
        saved = json.loads(self.receipt_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['state'], 'stopped')
        self.assertFalse(saved['managed'])

    def test_changed_process_profile_cannot_be_stopped_even_with_matching_birth_time(self):
        self.receipt_path.write_text(json.dumps(self.receipt), encoding='utf-8')
        self.record['cmd'] = self.record['cmd'].replace('--port 8188', '--port 9999')
        with self.assertRaises(starter.StartupError):
            self.call_stop()
        self.assertEqual(self.events, [('close', self.handle)])

    def test_start_records_creation_filetime_from_original_popen_handle(self):
        child = ChildProcess()
        handles = []
        with patch.object(starter.subprocess, 'Popen', return_value=child), \
             patch.object(starter, 'process_creation_filetime', side_effect=lambda handle: handles.append(handle) or
                          '134055000000000123', create=True):
            starter.start_comfy({})
        self.assertTrue(self.receipt_path.is_file(), 'Eigener Start braucht eine separate Managementquittung.')
        receipt = json.loads(self.receipt_path.read_text(encoding='utf-8'))
        self.assertEqual(receipt['pid'], 12345)
        self.assertEqual(receipt['creation_filetime'], '134055000000000123')
        self.assertTrue(receipt['managed'])
        self.assertEqual(handles, [child._handle])

    def test_api_adoption_preserves_existing_management_receipt(self):
        original = json.dumps(self.receipt).encode()
        self.receipt_path.write_bytes(original)
        with patch.object(starter, 'service_ready', return_value=True), \
             patch.object(starter, 'inspect_listener_details', return_value={
                 'ownership': 'foreign', 'pid': 7777, 'message': 'Anderer Starter'}):
            self.assertEqual(starter.ensure_comfy(), 7777)
        self.assertEqual(self.receipt_path.read_bytes(), original)

    def test_failed_creation_time_capture_does_not_grant_management(self):
        state = {}
        with patch.object(starter.subprocess, 'Popen', return_value=ChildProcess()), \
             patch.object(starter, 'process_creation_filetime', side_effect=OSError('Handle unlesbar'), create=True):
            starter.start_comfy(state)
        self.assertFalse(state.get('managed', True))
        self.assertFalse(self.receipt_path.exists())
        self.assertEqual(state['launcher_pid'], 12345)

    def test_start_only_command_never_runs_mcp(self):
        with patch.object(starter.sys, 'argv', [str(SOURCE), '--start-only']), \
             patch.object(starter, 'configure_environment'), \
             patch.object(starter, 'ensure_comfy', return_value=12345), \
             patch.object(starter.runpy, 'run_path', side_effect=AssertionError('Kein MCP beim Dienststart')), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(starter.main(), 0)

    def test_stop_command_never_starts_comfy_or_mcp(self):
        with patch.object(starter.sys, 'argv', [str(SOURCE), '--stop-managed']), \
             patch.object(starter, 'configure_environment'), \
             patch.object(starter, 'stop_managed', return_value={'stopped': True, 'pid': 12345}, create=True), \
             patch.object(starter, 'ensure_comfy', side_effect=AssertionError('Stop startet nichts')), \
             patch.object(starter.runpy, 'run_path', side_effect=AssertionError('Kein MCP beim Stop')), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(starter.main(), 0)

    def test_failed_birth_capture_cannot_be_promoted_to_managed_after_readiness(self):
        with patch.object(starter, 'inspect_listener_details', side_effect=[
                {'ownership': 'free', 'pid': None, 'message': 'Port frei'},
                {'ownership': 'free', 'pid': None, 'message': 'Port frei'},
                {'ownership': 'owned', 'pid': 12345, 'message': 'Eigenes Startprofil'}]), \
             patch.object(starter, 'service_ready', side_effect=[False, False, True]), \
             patch.object(starter.subprocess, 'Popen', return_value=ChildProcess()), \
             patch.object(starter, 'process_creation_filetime', side_effect=OSError('Handle unlesbar')):
            self.assertEqual(starter.ensure_comfy(), 12345)
        state = json.loads((self.report / 'mcp-comfy-start.json').read_text(encoding='utf-8'))
        self.assertFalse(state['managed'])
        self.assertFalse(self.receipt_path.exists())


class ShellWrapperTests(unittest.TestCase):
    def test_start_and_stop_forward_only_their_explicit_guard_mode(self):
        root = SOURCE.parents[2]
        for script, function, mode in [('start-morph.ps1', 'Invoke-MorphStart', '--start-only'),
                                        ('stop-morph.ps1', 'Invoke-MorphStop', '--stop-managed')]:
            with self.subTest(script=script):
                source = str(root / script).replace("'", "''")
                command = (
                    "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false); $ErrorActionPreference='Stop'; "
                    "$tokens=$null; $errors=$null; "
                    f"$ast=[System.Management.Automation.Language.Parser]::ParseFile('{source}',[ref]$tokens,[ref]$errors); "
                    "if($errors.Count){throw 'PowerShell-Quellfehler'}; "
                    "$ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]},$true) | "
                    "ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }; "
                    "function Invoke-MorphGuardProcess { param($PythonPath,$GuardPath,$Mode) "
                    "[pscustomobject]@{python=$PythonPath;guard=$GuardPath;mode=$Mode}|ConvertTo-Json -Compress }; "
                    f"{function} -ProjectRoot 'E:\\Synthetic-MORPH'")
                result = starter.subprocess.run([starter.POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                                                capture_output=True, text=True, encoding='utf-8', timeout=15,
                                                creationflags=starter.subprocess.CREATE_NO_WINDOW)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload, {
                    'python': r'E:\Synthetic-MORPH\ComfyUI_windows_portable\python_embeded\python.exe',
                    'guard': r'E:\Synthetic-MORPH\tools\lmstudio-wan-chat\start_mcp.py', 'mode': mode})


if __name__ == "__main__":
    unittest.main()
