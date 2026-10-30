# Phase 8 Backend: promptgebundener Knotenfortschritt

Stand: 20.10.2026. Ausgangscommit `1ad7201c2ad619960aa35d96f5226ef0597dbaef`.
Implementierung und gezielte synthetische Prüfung abgeschlossen; keine reale ComfyUI-/Modell-/GPU-Abnahme durchgeführt. Commit erfolgt durch den Hauptagenten nach Review.

## Verhalten

- Jeder neue Auftrag erhält vor der Übergabe eine dauerhaft gespeicherte UUID `client_id`. Die optionale Comfy-WebSocket-Verbindung verwendet dieselbe Kennung wie `/prompt`. Der erste Verbindungsversuch wird vor Submit abgewartet und ist auf 750 ms begrenzt; bei fehlendem Socket bleibt Submit/Queue-/History-Polling nutzbar.
- `progress.py` übernimmt ausschließlich Ereignisse mit exakt eigener `prompt_id`; Knotenkennungen müssen zum gespeicherten Graph gehören. Status, Binärvorschauen, promptlose Reconnect-Meldungen und fremde/ungültige Ereignisse werden ignoriert. Knotenschritte benötigen endliche echte Zahlen ohne Bool mit `max > 0` und `0 <= value <= max`.
- `job.progress` enthält `event`, `node_id`, `node_type`, `value`, `max`, `percent`, `cached_nodes`, `observed_at`, `connection`, `revision`. Prozent gehört ausschließlich zum aktuellen Knoten. Knotenwechsel löscht alte numerische Werte. Modellnamen oder globale Modellladezustände werden nicht abgeleitet.
- WebSocket-Success/Error/Interrupted sind Beobachtungen. Bestehendes Queue-/History-Polling bestimmt weiterhin den Auftragszustand und die Ausgabeübernahme; keine Runtime-Meldung schließt einen Auftrag ab.
- Auf Verbindungsabbruch folgen höchstens drei Wiederverbindungsversuche mit 100/200/400 ms Abstand, stets derselben Kennung und ohne Resubmit. Erschöpfte Retrybudgets werden nicht durch wiederholtes Lesen zurückgesetzt. Gespeicherte aktive Aufträge nehmen beim Lesen ihre Beobachtung wieder auf; Altaufträge ohne Kennung bleiben beim Polling.
- Fortschrittscallbacks ändern nur verschachtelte Fortschrittsdaten. Eine zentrale Revisionszusammenführung verhindert Verlust neuer Ereignisse während Submit/Poll/Cancel/Download-Awaits. Abbruchanforderungen bleiben erhalten. Terminale Jobs weisen späte Ereignisse ab und schließen ihren Tracker auch nach einer Pre-Submit-Ablehnung.
- Vor Submit wird die leere Queue nach dem WebSocket-Aufbau nochmals unmittelbar geprüft. `job.phase` zeigt tatsächliche Vorbereitungsschritte `connecting/checking/uploading/submitting`; `list_recent` bleibt während eines laufenden Dienststarts lesbar.
- `ComfyClient.close()` wartet auf das Schließen aller WebSockets/Tracker vor dem Schließen der HTTP-Session. Das vorhandene Server-Cleanup schließt danach bereits die Jobdatenbank. Ressourcenverwaltung, Bereichsmasken und gerichteter Cancel wurden nicht umgebaut.

## Geänderte Dateien und Sicherung

- `E:\MORPH-Studio\ui\morph_ui\comfy.py`
- `E:\MORPH-Studio\ui\morph_ui\jobs.py`
- `E:\MORPH-Studio\ui\morph_ui\progress.py` (neu)
- `E:\MORPH-Studio\ui\tests\test_progress.py` (neu)

Vorherige Dateien einschließlich unverändertem `server.py`, HEAD und SHA-256 liegen unter `phase8-backend-baseline`. Exakt getestete finale Dateihashes: `phase8-backend-tested-hashes.json` im selben Berichtverzeichnis.

## Prüfungen und negative Belege

Interpreter: `E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe`.
Tests verwenden ausschließlich synthetische Sandboxdaten und lokale aiohttp-Testserver; keine echten ComfyUI-/Ollama-Dienste oder Modelle wurden gestartet oder angesprochen.

- Erster RED: acht Tests scheiterten an fehlender Beobachtung/Kennung/Vorbereitungsphase (`phase8-backend-red.log`).
- Erster Grünlauf zeigte trotz grüner Assertions Windows-Transportwarnungen (`phase8-backend-green.log`). Ursache behoben durch geordneten WebSocket-Close vor Abbruch des Readers. Warnungsfreier Zwischenlauf: `phase8-backend-cleanup.log`. Finale Tests erfassen Eventloop-Ausnahmen und prüfen zurückbleibende Tracker ausdrücklich.
- Unabhängiger Review fand einen zu kurzen zweiten Wartezeitpunkt: bei gesundem 400-ms-Handshake erfolgte Submit vor Socket-Verbindung. Gezielter RED-Beleg `phase8-handshake-red.log`, Fix und GREEN `phase8-handshake-green.log`.
- Unabhängiger Review fand den letzten Queuecheck vor der neuen Socket-Wartezeit. Synthetisch während des Handshakes belegte fremde Queue führte zunächst zum Submit (RED `phase8-queue-after-watch-red.log`). Letzten Queuecheck hinter Socket-Aufbau verlegt; GREEN `phase8-queue-after-watch-green.log`.
- Finale Fortschrittssuite: **12/12 PASS**, 19,783 s, `phase8-backend-final.log`. Darunter echter lokaler WS-/HTTP-Protokolltest mit JobService/ComfyClient, persistierte Kennungsbindung vor Submit, fremde Ereignisse/Nodes/Zahlen/Binärpakete, Cache, Reconnect ohne Resubmit, History-Autorität, Altjob, Wiederaufnahme, Submit-/Poll-/Cancel-/Download-Races und Socket-Close nach Queueablehnung ohne weiteres Runtime-Ereignis.
- Angrenzende Regressionen: Jobs **14/14**, Comfy-Service **8/8**, Ressourcen **15/15**, versionierte Jobs **2/2**, Bereichsbearbeitung **17/17**; insgesamt **56/56 PASS**. Logs `phase8-adjacent-test_*.log`.
- Im finalen Fortschrittslauf keine ResourceWarning, ConnectionResetError, ungefangene Eventloop-Ausnahme oder offenen Socket-/Transportwarnungen. `git diff --check` für die geänderten bereits versionierten Backenddateien ohne Whitespace-Befund; Git weist lediglich auf die bekannte spätere LF/CRLF-Konvertierung hin.

## Offene Abnahme

Echte Start-/Adopt-/GPU-Berechnung, sichtbarer Fortschritt des tatsächlich installierten ComfyUI und gerichteter Live-Abbruch bleiben Phase 9. Die lokalen WS-/HTTP-Fixtures prüfen Protokoll und Nebenläufigkeit; sie belegen weder reale Modellausführung noch Bildqualität. Keine neuen Abhängigkeiten, keine globale Konfiguration, kein Push und keine Prozesssteuerung durch diesen Arbeitsblock.
