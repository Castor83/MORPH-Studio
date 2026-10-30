"""Local pause capture/check; no model execution, downloads or service mutations."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import urllib.request

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "PAUSE_STATE.md"
SNAPSHOT = ROOT / "PAUSE_SNAPSHOT.json"
MAX_HASH_BYTES = 16 * 1024 * 1024


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def within_root(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Pfad liegt außerhalb des MORPH-Projekts.")
    return path


def run(args, timeout=10):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout.decode("utf-8-sig", "replace").rstrip("\r\n")


def git(*args):
    return run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                "-C", str(ROOT), *args])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    files = {}
    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for name in filter(None, names.split("\0")):
        if name.startswith("pause-history/") or name in {
            "PAUSE_STATE.md", "PAUSE_SNAPSHOT.json"
        }:
            continue
        try:
            path = within_root(ROOT / name)
            size = path.stat().st_size
            files[name] = {
                "bytes": size,
                "sha256": sha(path) if size <= MAX_HASH_BYTES else None
            }
        except (OSError, ValueError) as error:
            files[name] = {"error": str(error)}
    return files


def models():
    expected = {}
    manifest = ROOT / "reports/phase2-model-manifest.json"
    if manifest.exists():
        for item in read_json(manifest):
            path = within_root(item["destination"])
            expected[path.relative_to(ROOT).as_posix()] = item["bytes"]
    folder = ROOT / "ComfyUI_windows_portable/ComfyUI/models"
    found = {}
    for path in folder.rglob("*.safetensors"):
        path = within_root(path)
        stat = path.stat()
        name = path.relative_to(ROOT).as_posix()
        found[name] = {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                       "expected_bytes": expected.get(name)}
    for name, size in expected.items():
        found.setdefault(name, {"missing": True, "expected_bytes": size})
    return found


def service():
    # Resolve the listener before reading its local API.
    command = r"""
$morphOwners = @(Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        $morphProcess = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_)
        [pscustomobject]@{pid=$_; executable=$morphProcess.ExecutablePath; command=$morphProcess.CommandLine}
    })
ConvertTo-Json -InputObject $morphOwners -Compress
"""
    try:
        owners = json.loads(run(["powershell.exe", "-NoLogo", "-NoProfile",
                                 "-NonInteractive", "-Command", command]))
        if isinstance(owners, dict):
            owners = [owners]
        if not owners:
            return {"status": "stopped_or_not_visible", "owners": []}
        executable = str(ROOT / "ComfyUI_windows_portable/python_embeded/python.exe")
        own = all(
            str(item.get("executable") or "").casefold() == executable.casefold()
            and "comfyui\\main.py" in str(item.get("command") or "").casefold().replace("/", "\\")
            for item in owners
        )
        if not own:
            return {"status": "foreign_or_unverified_listener", "owners": owners}
        result = {"status": "own_listener", "owners": owners}
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for endpoint in ("system_stats", "queue"):
            try:
                with opener.open("http://127.0.0.1:8188/" + endpoint, timeout=3) as response:
                    body = response.read(2 * 1024 * 1024 + 1)
                if len(body) > 2 * 1024 * 1024:
                    raise ValueError("API-Antwort über Größenlimit.")
                data = json.loads(body)
                if endpoint == "queue":
                    result[endpoint] = {
                        key: [str(job[1]) for job in data.get(key, [])]
                        for key in ("queue_running", "queue_pending")
                    }
                else:
                    result[endpoint] = data
            except Exception as error:
                result[endpoint] = {"error": str(error)}
        return result
    except Exception as error:
        return {"status": "not_visible", "error": str(error)}


def capture():
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if root != ROOT:
        raise ValueError("Git-Repository gehört nicht zum MORPH-Projektordner.")
    return {
        "captured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "git": {"branch": git("branch", "--show-current"),
                "head": git("rev-parse", "HEAD"),
                "status": git("status", "--porcelain=v1", "-z").split("\0")},
        "source_files": source_files(),
        "models": models(),
        "disk_free_bytes": shutil.disk_usage(ROOT).free,
        "service": service(),
        "limits": ["Große Modelle nur anhand Größe/Zeitstempel geprüft, nicht erneut gehasht.",
                   "Momentaufnahme: laufende Aufgaben können nach dem Speichern weiterarbeiten."]
    }


def validate_context(context):
    required = ("work", "completed", "open", "decisions", "tests",
                "running_tasks", "next_step")
    if not isinstance(context, dict):
        raise ValueError("Arbeitskontext muss ein JSON-Objekt sein.")
    for key in required:
        if key not in context:
            raise ValueError("Arbeitskontext fehlt: " + key)
    for key in ("work", "next_step"):
        if not isinstance(context[key], str) or not context[key].strip():
            raise ValueError(key + " muss einen nichtleeren Text enthalten.")
    if "\n" in context["next_step"] or "\r" in context["next_step"]:
        raise ValueError("next_step enthält genau eine Handlung auf einer Zeile.")
    for key in ("completed", "open", "decisions", "tests", "running_tasks"):
        if not isinstance(context[key], list) or not all(
            isinstance(item, str) and item.strip() for item in context[key]
        ):
            raise ValueError(key + " muss eine Liste nichtleerer Texte sein.")
    if not context["completed"]:
        raise ValueError("Mindestens den letzten abgeschlossenen Schritt nennen.")


def render(snapshot):
    context = snapshot["context"]
    observed = snapshot["observed"]
    lines = ["# MORPH Studio: gespeicherte Pause",
             "", "Snapshot-ID: " + snapshot["id"],
             "Gespeichert: " + observed["captured_at"],
             "Quelle: ausdrückliche Nutzeranweisung „pause“; Live-Prüfung durch morph_pause.py.",
             "", "## Aktuelle Arbeit", "", context["work"]]
    for title, key in (("Erledigt", "completed"), ("Offen", "open"),
                       ("Entscheidungen", "decisions"), ("Tests und Grenzen", "tests"),
                       ("Laufende Aufgaben", "running_tasks")):
        lines += ["", "## " + title, ""]
        lines += ["- " + item for item in context[key]] or ["Keine dokumentiert."]
    lines += ["", "## Genau der nächste Schritt", "", context["next_step"],
              "", "## Beobachteter Zustand", "",
              "- Git: " + observed["git"]["branch"] + " / " + observed["git"]["head"],
              "- Git-Änderungen: " + json.dumps(
                  [x for x in observed["git"]["status"] if x], ensure_ascii=False),
              "- Freier Speicher: %.2f GiB (Momentaufnahme)." %
                  (observed["disk_free_bytes"] / 1024**3),
              "- Dienst: " + observed["service"]["status"],
              "- Warteschlange: " + json.dumps(
                  observed["service"].get("queue", "Nicht lesbar/kein eigener Listener."),
                  ensure_ascii=False),
              "", "## Wiederaufnahme", "",
              "MORPH-Fortsetzen-Check.cmd ausführen, Unterschiede einordnen und den oben "
              "genannten nächsten Schritt innerhalb des autorisierten Umfangs fortsetzen.",
              "Quellen: PROJECT_STATE.json und dort benannte Phasenberichte; vollständige "
              "Dateiprüfsummen und Modelldateigrößen stehen in PAUSE_SNAPSHOT.json.",
              "Vor dem Ersetzen dieses Paars wird der vorherige Stand unter pause-history "
              "erhalten. Die Dateien werden nicht automatisch committet.",
              "", "## Grenzen der Momentaufnahme", ""]
    lines += ["- " + item for item in observed["limits"]]
    return "\n".join(lines) + "\n"


def atomic_write(path, text):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if path.read_text(encoding="utf-8") != text:
            raise OSError("Nachprüfung fehlgeschlagen: " + str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def save(args):
    if not args.confirmed_pause:
        raise ValueError("save verlangt eine ausdrückliche Nutzerpause und --confirmed-pause.")
    context = read_json(within_root(args.context))
    validate_context(context)
    snapshot = {
        "schema_version": 1,
        "id": dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8],
        "context": context,
        "observed": capture()
    }
    markdown = render(snapshot)
    if args.dry_run:
        print("Trockenprüfung bestanden. Keine Pausendatei geschrieben.")
        print(markdown)
        return 0
    history = ROOT / "pause-history"
    history.mkdir(exist_ok=True)
    # Preserve even a manually edited or incomplete prior pair before replacement.
    for path in (STATE, SNAPSHOT):
        if path.exists():
            shutil.copy2(path, history / (snapshot["id"] + "-previous-" + path.name))
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    atomic_write(history / (snapshot["id"] + ".json"), payload)
    atomic_write(history / (snapshot["id"] + ".md"), markdown)
    atomic_write(SNAPSHOT, payload)
    atomic_write(STATE, markdown)
    if read_json(SNAPSHOT)["id"] != snapshot["id"] or "Snapshot-ID: " + snapshot["id"] not in STATE.read_text(encoding="utf-8"):
        raise OSError("Snapshot-Paar ist inkonsistent; Verlauf zur Wiederherstellung verwenden.")
    print("Pause gesichert: " + str(STATE))
    print("Nächster Schritt: " + context["next_step"])
    return 0


def check():
    current = capture()
    baseline = read_json(ROOT / "PROJECT_STATE.json")
    notes = []
    if STATE.exists() != SNAPSHOT.exists():
        raise ValueError("Pausenpaar unvollständig. Vor Fortsetzung PAUSE_STATE und pause-history prüfen.")
    if SNAPSHOT.exists():
        saved = read_json(SNAPSHOT)
        if ("Snapshot-ID: " + saved["id"]) not in STATE.read_text(encoding="utf-8-sig"):
            raise ValueError("Snapshot-Paar passt nicht zusammen. Texte und Verlauf prüfen.")
        if Path(saved["observed"]["root"]).resolve() != ROOT:
            raise ValueError("Gespeicherte Pause gehört zu einem anderen Projektordner.")
        previous = saved["observed"]
        print("Gespeicherte Pause: " + previous["captured_at"])
        print("Arbeit: " + saved["context"]["work"])
        if STATE.read_text(encoding="utf-8-sig") != render(saved):
            notes.append("Pausentext manuell geändert; vor Fortsetzung PAUSE_STATE.md und JSON abgleichen. Keine Nutzerkorrektur überschreiben.")
        print("Nächster Schritt laut Snapshot-JSON: " + saved["context"]["next_step"])
        if previous["git"] != current["git"]:
            notes.append("Git-Stand seit der Pause geändert; tatsächliche Änderungen lesen.")
        for name in sorted(set(previous["source_files"]) | set(current["source_files"])):
            if previous["source_files"].get(name) != current["source_files"].get(name):
                notes.append("Projektdatei geändert: " + name)
        if previous["models"] != current["models"]:
            notes.append("Modellbestand/Größe/Zeitstempel seit der Pause geändert; gezielt prüfen.")
    else:
        print("Noch keine ausdrücklich gespeicherte Pause; dokumentierter Ausgangsstand: " + baseline["updated_at"])
        print("Abgeschlossen: %s/%s Aufgaben." % (baseline["completed_tasks"], baseline["total_tasks"]))
        print("Nächster Schritt: " + baseline["next_step"])
        if current["git"]["head"] != baseline["baseline_commit"]:
            notes.append("Git-Commit weicht vom historischen Ausgangsstand ab; aktuelle Änderungen einordnen.")
    for name, item in current["models"].items():
        if item.get("missing") or (item.get("expected_bytes") is not None and item["bytes"] != item["expected_bytes"]):
            notes.append("Modell fehlt oder hat unerwartete Größe: " + name)
    print("Git: " + current["git"]["branch"] + " / " + current["git"]["head"])
    print("Aktuelle Git-Änderungen: " + json.dumps([x for x in current["git"]["status"] if x], ensure_ascii=False))
    print("Aktuell frei: %.2f GiB." % (current["disk_free_bytes"] / 1024**3))
    print("Dienst: " + current["service"]["status"])
    queue = current["service"].get("queue", {})
    print("Aktuelle Warteschlange: " + json.dumps(queue, ensure_ascii=False))
    if current["service"]["status"] in {"foreign_or_unverified_listener", "not_visible"}:
        notes.append("Mein Zugriff sieht die MORPH-Dienstzuordnung nicht sicher; vor Dienstaktionen klären.")
    if queue.get("queue_running") or queue.get("queue_pending"):
        notes.append("Aufträge laufen oder warten; vor neuen Modellläufen deren Ausgang prüfen.")
    for note in notes:
        print("Hinweis: " + note)
    print("Read-only Check beendet. Keine Dateien oder Dienste verändert; kein Modelllauf.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Vorhandenen Stand ausschließlich lesen.")
    saving = commands.add_parser("save", help="Nur nach ausdrücklicher Nutzerpause speichern.")
    saving.add_argument("--confirmed-pause", action="store_true")
    saving.add_argument("--context", required=True)
    saving.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return check() if args.command == "check" else save(args)
    except Exception as error:
        print("Pausenprotokoll: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
