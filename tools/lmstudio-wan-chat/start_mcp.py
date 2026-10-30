"""Start the existing local MORPH service once, then serve the existing MCP."""

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import msvcrt
import ntpath
import os
from pathlib import Path
import runpy
import site
import subprocess
import sys
import time
import urllib.request


ROOT = Path(r"E:\MORPH-Studio")
PYTHON = ROOT / "ComfyUI_windows_portable/python_embeded/python.exe"
MCP_RUNTIME = ROOT / "tools/comfyui-mcp-runtime"
MCP_SERVER = ROOT / "tools/comfyui-mcp-server/server.py"
START_SCRIPT = ROOT / "start-morph.ps1"
REPORT_DIR = ROOT / "reports/wan-lmstudio"
POWERSHELL = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe")
COMFY_URL = "http://127.0.0.1:8188"


class StartupError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def log(message):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / "mcp-comfy-start.log").open("a", encoding="utf-8") as output:
        output.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def save_state(state):
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    target = REPORT_DIR / "mcp-comfy-start.json"
    temporary = target.with_suffix(f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(target)


def save_owned_receipt(receipt):
    target = REPORT_DIR / "mcp-comfy-owned.json"
    temporary = target.with_suffix(f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    temporary.replace(target)


def process_kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    time_pointer = ctypes.POINTER(wintypes.FILETIME)
    signatures = {
        "GetProcessTimes": ([wintypes.HANDLE, time_pointer, time_pointer, time_pointer, time_pointer], wintypes.BOOL),
        "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "QueryFullProcessImageNameW": ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        "TerminateProcess": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = arguments, result
    return kernel


def process_creation_filetime(handle):
    times = [wintypes.FILETIME() for unused in range(4)]
    if not process_kernel().GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
        raise StartupError("Die Erstellungszeit des Prozesshandles ist nicht lesbar.")
    return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)


def process_executable(handle):
    buffer = ctypes.create_unicode_buffer(32768)
    length = wintypes.DWORD(len(buffer))
    if not process_kernel().QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
        raise StartupError("Der Programmpfad des Prozesshandles ist nicht lesbar.")
    return buffer.value


def open_process_for_stop(pid):
    # Query identity, terminate that same process object, and wait for its exit.
    handle = process_kernel().OpenProcess(0x1000 | 0x0001 | 0x100000, False, pid)
    if not handle:
        raise StartupError("Der quittierte Prozess ist beendet oder sein Handle ist nicht zugänglich. Kein Prozess beendet.")
    return handle


def open_process_for_query(pid):
    # Resource controls inspect the process object without terminate access.
    handle = process_kernel().OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        raise StartupError("Die quittierte Prozessidentität ist nicht lesbar.")
    return handle


def terminate_process_handle(handle):
    kernel = process_kernel()
    if kernel.WaitForSingleObject(handle, 0) != 258:
        raise StartupError("Der quittierte Prozess läuft nicht mehr oder sein Zustand ist unklar. Kein Prozess beendet.")
    if not kernel.TerminateProcess(handle, 0):
        raise StartupError("Der bestätigte eigene Prozess konnte nicht beendet werden.")
    if kernel.WaitForSingleObject(handle, 10000) != 0:
        raise StartupError("Das Ende des eigenen Prozesses wurde nicht bestätigt. Es wird kein weiterer Prozess beendet.")


def close_process_handle(handle):
    process_kernel().CloseHandle(handle)


class StartLock:
    def __init__(self, timeout=180):
        self.timeout = timeout

    def __enter__(self):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        self.file = (REPORT_DIR / "mcp-comfy-start.lock").open("a+b")
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b"\0")
            self.file.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            self.file.seek(0)
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.file.close()
                    raise StartupError("Timed out waiting for the MORPH start lock.")
                time.sleep(0.1)

    def __exit__(self, *unused):
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.file.close()


def windows_arguments(command):
    count = ctypes.c_int()
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    pointer = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not pointer:
        raise StartupError("Cannot parse the Windows process command line.")
    try:
        return [pointer[index] for index in range(count.value)]
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(ctypes.cast(pointer, ctypes.c_void_p))


def same_path(first, second):
    return ntpath.normcase(ntpath.normpath(str(first))) == ntpath.normcase(ntpath.normpath(str(second)))


def option_value(arguments, name):
    occurrences = [index for index, arg in enumerate(arguments) if arg == name or arg.startswith(name + "=")]
    if not occurrences:
        return None, f"Startoption {name} fehlt."
    if len(occurrences) != 1:
        return None, f"Startoption {name} ist mehrfach angegeben."
    index = occurrences[0]
    if arguments[index] != name:
        value = arguments[index].split("=", 1)[1]
    elif index + 1 < len(arguments) and not arguments[index + 1].startswith("--"):
        value = arguments[index + 1]
    else:
        value = ""
    return (value, None) if value else (None, f"Startoption {name} hat keinen Wert.")


def option_is(arguments, name, expected, path=False):
    value, error = option_value(arguments, name)
    return not error and (same_path(value, expected) if path else value == expected)


def classify_listener_details(records):
    if not records:
        return {"ownership": "free", "pid": None, "message": "Port 8188 ist frei."}
    pids = set()
    for record in records:
        def foreign(message):
            return {"ownership": "foreign", "pid": record.get("pid"), "message": message}

        if record.get("address") != "127.0.0.1":
            return foreign("Der Listener ist nicht ausschließlich an 127.0.0.1 gebunden.")
        if not record.get("exe") or not record.get("cmd"):
            return foreign("Python-Pfad oder Prozessargumente sind nicht lesbar.")
        if not same_path(record["exe"], PYTHON):
            return foreign("Der Python-Pfad gehört nicht zur MORPH-Laufzeit.")
        try:
            arguments = windows_arguments(record["cmd"])
        except StartupError:
            return foreign("Die Prozessargumente sind nicht lesbar.")
        script_index = 2 if len(arguments) > 1 and arguments[1] == "-s" else 1
        valid_script = (len(arguments) > script_index and same_path(arguments[0], PYTHON)
                        and (same_path(arguments[script_index], r"ComfyUI\main.py")
                             or same_path(arguments[script_index], ROOT / "ComfyUI_windows_portable/ComfyUI/main.py")))
        options = [("--listen", "127.0.0.1", False), ("--port", "8188", False),
                   ("--input-directory", ROOT / "input", True), ("--output-directory", ROOT / "output", True),
                   ("--temp-directory", ROOT / "temp/comfyui", True), ("--user-directory", ROOT / "user", True)]
        if not valid_script:
            return foreign("Der Skriptaufruf entspricht nicht dem MORPH-ComfyUI-Start.")
        for name, expected, is_path in options:
            value, error = option_value(arguments, name)
            if error:
                return foreign(error)
            if not (same_path(value, expected) if is_path else value == expected):
                return foreign(f"Startoption {name} entspricht nicht dem MORPH-Projekt.")
        for flag in ("--offline", "--disable-auto-launch"):
            if flag not in arguments:
                return foreign(f"Startoption {flag} fehlt.")
        pids.add(record["pid"])
    if len(pids) != 1:
        return {"ownership": "foreign", "pid": None, "message": "Mehrere Prozesse belegen Port 8188."}
    return {"ownership": "owned", "pid": pids.pop(), "message": "Der Prozess entspricht dem MORPH-Startprofil."}


def classify_listeners(records):
    details = classify_listener_details(records)
    return details["ownership"], details["pid"]


def powershell_json(command):
    prefix = "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); $ErrorActionPreference='Stop'; "
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", prefix + command],
                            capture_output=True, text=True, encoding="utf-8", timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise StartupError("Cannot verify the process owning localhost:8188: " + result.stderr.strip()[:1000])
    try:
        return json.loads(result.stdout)
    except ValueError as error:
        raise StartupError("Invalid process-inspection response.") from error


def inspect_listener_details():
    records = powershell_json("$rows=@(Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 8188 | ForEach-Object { "
                              "$p=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$_.OwningProcess); "
                              "[pscustomobject]@{pid=$_.OwningProcess;address=$_.LocalAddress;exe=$p.ExecutablePath;cmd=$p.CommandLine} }); "
                              "ConvertTo-Json -InputObject @($rows) -Depth 3 -Compress")
    return classify_listener_details(records)


def inspect_listener():
    details = inspect_listener_details()
    return details["ownership"], details["pid"]


def own_launcher_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    record = powershell_json(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
                             "if($null -eq $p){'null'}else{[pscustomobject]@{exe=$p.ExecutablePath;cmd=$p.CommandLine}|ConvertTo-Json -Compress}")
    if not record:
        return False
    if same_path(record.get("exe") or "", PYTHON):
        kind, unused_pid = classify_listeners([dict(record, pid=pid, address="127.0.0.1")])
        return kind == "owned"
    if not same_path(record.get("exe") or "", POWERSHELL):
        return False
    return option_is(windows_arguments(record.get("cmd") or ""), "-File", START_SCRIPT, path=True)


def service_ready():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        values = []
        for endpoint in ("/system_stats", "/queue", "/object_info/LoadImage", "/object_info/SaveImage"):
            with opener.open(COMFY_URL + endpoint, timeout=2) as response:
                if response.status != 200:
                    return False
                data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    return False
                values.append(json.loads(data))
        stats, queue, load, save = values
        if not (isinstance(stats, dict) and isinstance(stats.get("system"), dict)
                and bool(stats["system"].get("comfyui_version")) and isinstance(queue, dict)
                and isinstance(queue.get("queue_running"), list) and isinstance(queue.get("queue_pending"), list)):
            return False
        for schema, node, slot in ((load, "LoadImage", "image"), (save, "SaveImage", "images")):
            if not isinstance(schema, dict) or not isinstance(schema.get(node), dict):
                return False
            inputs = schema[node].get("input")
            if not isinstance(inputs, dict) or not isinstance(inputs.get("required"), dict) or slot not in inputs["required"]:
                return False
        return True
    except (OSError, ValueError):
        return False


def start_comfy(state):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    stdout = REPORT_DIR / f"mcp-comfy-{stamp}.stdout.log"
    stderr = REPORT_DIR / f"mcp-comfy-{stamp}.stderr.log"
    command = [str(PYTHON), "-s", r"ComfyUI\main.py", "--windows-standalone-build",
               "--listen", "127.0.0.1", "--port", "8188", "--offline",
               "--input-directory", str(ROOT / "input"), "--output-directory", str(ROOT / "output"),
               "--temp-directory", str(ROOT / "temp/comfyui"), "--user-directory", str(ROOT / "user"),
               "--disable-auto-launch"]
    log("starting ComfyUI directly: " + subprocess.list2cmdline(command))
    with stdout.open("ab") as output, stderr.open("ab") as errors:
        child = subprocess.Popen(command, cwd=str(ROOT / "ComfyUI_windows_portable"),
                                 stdin=subprocess.DEVNULL, stdout=output, stderr=errors, env=project_environment(),
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    state.update(launcher_pid=child.pid, managed=False, stdout_log=str(stdout), stderr_log=str(stderr), state="starting")
    try:
        creation = process_creation_filetime(child._handle)
        if not creation.isdecimal() or not 0 < int(creation) < 2**64:
            raise StartupError("Ungültige Erstellungszeit des eigenen Prozesses.")
        save_owned_receipt({"schema_version": 1, "managed": True, "state": "running", "pid": child.pid,
                            "creation_filetime": creation, "project_root": str(ROOT), "python": str(PYTHON),
                            "script": str(ROOT / "ComfyUI_windows_portable/ComfyUI/main.py"),
                            "created_at": datetime.now(timezone.utc).isoformat()})
        state["managed"] = True
    except (OSError, StartupError, AttributeError, TypeError, ValueError) as error:
        state["management_message"] = f"Keine sichere eigene Startquittung: {error}. Der Dienst wird nicht automatisch beendet."
        log(state["management_message"])
    save_state(state)
    log(f"started launcher PID {child.pid}; logs {stdout.name}, {stderr.name}")
    return child


def ensure_comfy(startup_timeout=180):
    with StartLock():
        state = {"state": "checking", "wrapper_pid": os.getpid(), "launcher_pid": None, "managed": False}
        child = None

        def inspect(api_ready):
            try:
                return inspect_listener_details()
            except Exception as error:
                if not api_ready:
                    raise StartupError("Die lokale ComfyUI-API ist nicht erreichbar oder inkompatibel; "
                                       f"Port 8188 lässt sich nicht sicher prüfen: {error}. Kein Dienst gestartet.") from error
                return {"ownership": "unknown", "pid": None, "message": f"Prozessdaten nicht verfügbar: {error}"}

        def ready(details):
            pid = details["pid"]
            state.update(state="ready", comfy_pid=pid, ownership=details["ownership"], message=details["message"],
                         managed=state.get("managed") is True and child is not None and pid == child.pid)
            save_state(state)
            log(f"ready; {'started' if state['managed'] else 'adopted'} compatible ComfyUI API; PID {pid}; {details['message']}")
            return pid

        def reject_occupied(details):
            raise StartupError(f"Port 8188 ist belegt (PID {details['pid']}); die ComfyUI-API ist nicht erreichbar "
                               f"oder inkompatibel. {details['message']} Kein Dienst gestartet oder beendet.")

        try:
            api_ready = service_ready()
            details = inspect(api_ready)
            if api_ready:
                return ready(details)
            if details["ownership"] == "foreign":
                reject_occupied(details)
            if details["ownership"] == "free":
                previous_file = REPORT_DIR / "mcp-comfy-start.json"
                previous = json.loads(previous_file.read_text(encoding="utf-8")) if previous_file.exists() else {}
                if own_launcher_alive(previous.get("launcher_pid")):
                    state.update(launcher_pid=previous["launcher_pid"], state="starting")
                    log(f"waiting for existing launcher PID {state['launcher_pid']}")
                else:
                    # The second inspection also catches non-wrapper starts since the initial check.
                    api_ready = service_ready()
                    details = inspect(api_ready)
                    if api_ready:
                        return ready(details)
                    if details["ownership"] == "foreign":
                        reject_occupied(details)
                    if details["ownership"] == "free":
                        child = start_comfy(state)
            deadline = time.monotonic() + startup_timeout
            while True:
                api_ready = service_ready()
                details = inspect(api_ready)
                if api_ready:
                    return ready(details)
                if details["ownership"] == "foreign":
                    reject_occupied(details)
                if child is not None and child.poll() is not None:
                    raise StartupError(f"MORPH launcher exited with code {child.returncode}; see its logs.")
                if time.monotonic() >= deadline:
                    raise StartupError("MORPH did not become ready before the startup deadline; see its logs.")
                time.sleep(1)
        except Exception as error:
            state.update(state="error", error=str(error))
            save_state(state)
            log("error: " + str(error))
            raise StartupError(str(error)) from error


def read_managed_receipt():
    path = REPORT_DIR / "mcp-comfy-owned.json"
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StartupError("Keine lesbare eigene Startquittung vorhanden. Ältere oder übernommene Dienste werden nicht beendet.") from error
    expected_script = ROOT / "ComfyUI_windows_portable/ComfyUI/main.py"
    if not (isinstance(receipt, dict) and type(receipt.get("schema_version")) is int and receipt["schema_version"] == 1
            and receipt.get("managed") is True and receipt.get("state") == "running"
            and type(receipt.get("pid")) is int and receipt["pid"] > 0
            and isinstance(receipt.get("creation_filetime"), str) and receipt["creation_filetime"].isdecimal()
            and 0 < int(receipt["creation_filetime"]) < 2**64
            and same_path(receipt.get("project_root") or "", ROOT)
            and same_path(receipt.get("python") or "", PYTHON)
            and same_path(receipt.get("script") or "", expected_script)):
        raise StartupError("Die eigene Startquittung ist unvollständig, veraltet oder gehört nicht zu diesem Projekt. Kein Prozess beendet.")
    return receipt


def verify_managed_handle(receipt, handle):
    if process_kernel().WaitForSingleObject(handle, 0) != 258:
        raise StartupError("Der quittierte Prozess läuft nicht mehr oder sein Zustand ist unklar.")
    if process_creation_filetime(handle) != receipt['creation_filetime']:
        raise StartupError("Die Prozess-Erstellungszeit stimmt nicht mit der eigenen Startquittung überein.")
    if not same_path(process_executable(handle), PYTHON):
        raise StartupError("Der quittierte Prozess verwendet eine andere Laufzeit.")


def verify_managed_listener(receipt, handle):
    verify_managed_handle(receipt, handle)
    details = inspect_listener_details()
    if details.get('ownership') != 'owned' or details.get('pid') != receipt['pid']:
        raise StartupError("Der aktuelle Listener gehört nicht zur quittierten eigenen Instanz.")
    verify_managed_handle(receipt, handle)


def open_managed_listener():
    receipt = read_managed_receipt()
    handle = open_process_for_query(receipt['pid'])
    try:
        verify_managed_listener(receipt, handle)
        return receipt, handle
    except BaseException:
        close_process_handle(handle)
        raise


def open_managed_stop_listener():
    """Open terminate rights only for the exact receipted live listener."""
    receipt = read_managed_receipt()
    handle = open_process_for_stop(receipt['pid'])
    try:
        verify_managed_listener(receipt, handle)
        return receipt, handle
    except BaseException:
        close_process_handle(handle)
        raise


def stop_verified_managed_listener(receipt, handle):
    """Caller holds StartLock; never reopen by PID after the final verification."""
    verify_managed_listener(receipt, handle)
    terminate_process_handle(handle)  # Waits for this same process object's confirmed exit.
    receipt.update(state='stopped', managed=False, stopped_at=datetime.now(timezone.utc).isoformat())
    save_owned_receipt(receipt)
    log(f"emergency stopped own ComfyUI PID {receipt['pid']}; creation FILETIME {receipt['creation_filetime']}")


def inspect_managed_listener():
    receipt, handle = open_managed_listener()
    try:
        return {'managed':True, 'pid':receipt['pid']}
    finally:
        close_process_handle(handle)


def stop_managed():
    with StartLock():
        receipt = read_managed_receipt()
        pid = receipt["pid"]
        handle = open_process_for_stop(pid)
        try:
            if process_creation_filetime(handle) != receipt["creation_filetime"]:
                raise StartupError(f"PID {pid} hat eine andere Erstellungszeit. Kein Prozess beendet.")
            if not same_path(process_executable(handle), PYTHON):
                raise StartupError(f"PID {pid} verwendet eine andere Laufzeit. Kein Prozess beendet.")
            record = powershell_json(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
                                     "if($null -eq $p){'null'}else{[pscustomobject]@{pid=$p.ProcessId;exe=$p.ExecutablePath;cmd=$p.CommandLine}|ConvertTo-Json -Compress}")
            if not isinstance(record, dict) or record.get("pid") != pid:
                raise StartupError("Die quittierte Prozessidentität ist nicht lesbar. Kein Prozess beendet.")
            details = classify_listener_details([dict(record, address="127.0.0.1")])
            if details["ownership"] != "owned":
                raise StartupError(f"PID {pid}: {details['message']} Kein Prozess beendet.")
            terminate_process_handle(handle)
            receipt.update(state="stopped", managed=False, stopped_at=datetime.now(timezone.utc).isoformat())
            save_owned_receipt(receipt)
            log(f"stopped own ComfyUI PID {pid}; creation FILETIME {receipt['creation_filetime']}")
            return {"stopped": True, "pid": pid, "message": "Der quittierte eigene MORPH-Rechendienst wurde beendet."}
        finally:
            close_process_handle(handle)


def project_directories():
    return {"TEMP": ROOT / "temp", "TMP": ROOT / "temp", "HF_HOME": ROOT / "cache/huggingface",
                   "HF_HUB_CACHE": ROOT / "cache/huggingface/hub", "TORCH_HOME": ROOT / "cache/torch",
                   "PIP_CACHE_DIR": ROOT / "cache/pip", "XDG_CACHE_HOME": ROOT / "cache",
                   "PYTHONPYCACHEPREFIX": ROOT / "cache/pycache", "CUDA_CACHE_PATH": ROOT / "cache/cuda",
                   "TRITON_CACHE_DIR": ROOT / "cache/triton", "YOLO_CONFIG_DIR": ROOT / "cache/ultralytics"}


def project_environment():
    return {**os.environ, **{key: str(path) for key, path in project_directories().items()},
            "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "DO_NOT_TRACK": "1",
            "YOLO_OFFLINE": "1", "NO_ALBUMENTATIONS_UPDATE": "1"}


def configure_environment():
    for directory in project_directories().values():
        directory.mkdir(parents=True, exist_ok=True)
    os.environ.update(project_environment())
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main():
    try:
        if not same_path(sys.executable, PYTHON):
            raise StartupError(f"Run this wrapper with the existing MORPH Python: {PYTHON}")
        configure_environment()
        modes = [argument for argument in sys.argv[1:] if argument in ("--start-only", "--stop-managed", "--no-autostart")]
        if len(modes) > 1:
            raise StartupError("Bitte genau einen Dienst- oder MCP-Modus aufrufen.")
        if "--stop-managed" in modes:
            print(json.dumps(stop_managed(), ensure_ascii=False))
            return 0
        if "--start-only" in modes:
            pid = ensure_comfy()
            print(f"MORPH-Rechendienst bereit: {COMFY_URL} (PID {pid if pid is not None else 'nicht verfügbar'})")
            return 0
        metadata_only = "--no-autostart" in sys.argv[1:]
        pid = None if metadata_only else ensure_comfy()
        sys.path.insert(0, str(MCP_RUNTIME))
        site.addsitedir(str(MCP_RUNTIME))
        sys.path.insert(0, str(MCP_SERVER.parent))
        sys.argv = [str(MCP_SERVER), "--comfyui-url", COMFY_URL, "--comfyui-output-dir", str(ROOT / "output")]
        if metadata_only:
            log(f"serving MCP metadata in wrapper PID {os.getpid()}; ComfyUI startup deferred")
        else:
            log(f"serving MCP in wrapper PID {os.getpid()}; ComfyUI PID {pid}")
        with (REPORT_DIR / f"mcp-server-{os.getpid()}.stderr.log").open("a", encoding="utf-8") as errors:
            original_stderr = sys.stderr
            try:
                sys.stderr = errors
                runpy.run_path(str(MCP_SERVER), run_name="__main__")
            finally:
                sys.stderr = original_stderr
        return 0
    except Exception as error:
        log("error: " + str(error))
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
