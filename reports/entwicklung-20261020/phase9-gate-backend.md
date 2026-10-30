# Phase 9: gemeinsames Sprach-/Bild-Gate, Backend

Arbeitsbasis: `E:\MORPH-Studio`, bestehender autorisierter Branch `main`, HEAD `18522b6255befb633f5b193159f84326d521dbb5`. Kein Remote ausgegeben. Kein Commit durch diesen Agenten. Bestehende Fremdänderungen wurden gelesen und erhalten; Frontend und Abnahme-Harness bearbeiten andere Agenten parallel.

## Ursache und Änderung

Die vier mutierenden Sprachrouten riefen den Provider ohne `JobService.lock` auf. Ein Bildstart wartete auf diesen Lock, kannte aber weder eine laufende Sprachaktion noch frische native Ollama-GPU-Belegung. `/api/ps` wurde bisher nur auf geladene Namen reduziert. Ein bloßer gemeinsamer Lock hätte einen nachlaufenden Bildsubmit und die weiterbestehende GPU-Residenz nicht ausreichend behandelt.

`JobService.language_action` ist jetzt die gemeinsame Hülle für load, unload, propose und propose_tools. Alle ungelösten gespeicherten Jobs einschließlich älterer, unbekannter oder defekter Datensätze sperren die Provideraktion. Eine bereits laufende Bild-/Speicheraktion führt zur unmittelbaren Ablehnung. `language_busy` wird innerhalb des Locks vor dem ersten await gesetzt. Bildcreate und globale bewusste Ressourcenfreigabe prüfen dieses Flag vor dem Lock und lehnen sofort ab. Bekannte Anforderungskennungen liefern weiter ihre bestehende Quittung, auch während Sprachbusy; daraus entsteht kein zweiter Submit.

Vor dem Bildstart wird ausschließlich lesend frisches Ollama `/api/ps` abgefragt. Positiv bestätigte `size_vram > 0` sperrt mit den Modellnamen und dem Hinweis auf bewusste Freigabe. Null oder eine leere Liste sperrt nicht. Ungültige/unvollständige Antworten und Nichterreichbarkeit erzeugen `job.warnings: string[]`; die optionale Sprachhilfe wird damit keine Pflicht für Bildarbeit. Keine Ableitung aus Dateigrößen oder Einstellungen, kein automatisches Entladen.

Vor Laden oder Vorschlag werden ComfyUI-Queue und `/system_stats` geprüft. Positive `torch_vram_total` eines Nicht-CPU-Geräts sperrt mit Hinweis auf die vorhandene bewusste Bildmodellfreigabe. CPU-RAM wird ausgenommen. Nicht laufendes ComfyUI mit frisch bestätigtem freiem Port erlaubt die Sprachhilfe. Eine erreichbare/unprüfbare Instanz sperrt sie. Die bestehende Besitzprüfung und `/free`-Sicherung wurden nicht aufgeweicht; es wird kein zusätzlicher `/free`-Aufruf erzeugt.

## Begonnene unbestätigte Ollama-Aktion

Unmittelbar vor einem mutierenden Providertransportaufruf zu `/api/generate` oder `/api/chat`, nach der lokalen und Metadatenvalidierung, schreibt der Observer eine additive Singleton-Quittung in die neue Tabelle `language_operation`. Sie enthält nur Modellname, Aktion, Zeitpunkt und den normalisierten öffentlichen Endpunkt. Keine Prompts, Payloads oder Tokens. Dies ist eine konservative Begonnen-Markierung am Providertransport; ein HTTP-Aufruf beweist nicht, dass ein Server ihn empfangen hat.

Eine bestätigte `done: true`-Antwort muss ausdrücklich genau dasselbe Modell nennen. Bei normalem Laden/Vorschlag schließt das den mutierenden Lauf ab; ungültiger Vorschlagsinhalt bleibt ein inhaltlicher Fehler, führt aber nicht zu einem erfundenen noch laufenden Request. Bei Timeout, Abbruch oder fehlender Bestätigung bleibt die Quittung dauerhaft erhalten, auch nach einer neuen JobService-Instanz. Ein später leeres oder ausgefallenes `/api/ps` beseitigt diese eigene Unsicherheit nicht.

Nur bewusstes unload derselben gespeicherten Instanz am selben Endpunkt darf diesen Unknown-Fence passieren. Der eng begrenzte Reconcile-Pfad erlaubt diese ausdrückliche Freigabe auch dann, wenn die Instanz nach einem load/unload-Timeout momentan nicht in `/api/ps` erscheint. Freigegeben wird erst nach bestätigter POST-Antwort des exakten Modells und frischem Abwesenheitsbeleg. Bildjobs und echte laufende Sprachaktionen sperren weiterhin auch unload. Kein automatischer Wiederholungsversuch.

`GET /api/status` enthält `data.language_state = {busy: boolean, uncertain_instances: string[]}` mit maximal einem gespeicherten Ziel. Damit kann die UI nach einem load-Timeout ohne bestätigte `settings.instance_id` die konkrete bewusste Freigabe anbieten. Einstellungen dürfen während Sprachbusy, bestehender Unknown-Quittung oder gehaltenem Joblock nicht geändert werden. Bei externer Endpunktänderung verweigert Reconcile den falschen Zielserver; die ursprüngliche Verbindung muss bewusst wiederhergestellt werden.

Die Tabelle wird beim nächsten normalen UI-Start additiv angelegt. Root übernimmt vor diesem Start die beschlossene SQLite.backup-Sicherung. In dieser Agentenarbeit wurde keine produktive Datenbank geöffnet oder migriert.

## Dateien und Prüfung

Produktiv geändert: `ui/morph_ui/jobs.py`, `ui/morph_ui/providers/ollama.py`, `ui/morph_ui/server.py`. Neue gezielte Regressionen: `ui/tests/test_language_gate.py`. Bestehende Testfixtures `test_jobs.py` und `test_tool_proposals.py` wurden angepasst: realer JobService statt pauschalem Mock für die Vorschlagsroute; Fixture-Comfy meldet explizit leere GPU-Reservierung. Die Produktionsklasse enthält keine Test-Hilfsmethoden.

Portable Laufzeit: `E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe -B`. Nur isolierte Daten und lokale HTTP-Fixtures; keine echten Modell-/Dienstaktionen, keine echten Ollama-/Comfy-POSTs, kein Start/Stop/Free und keine Installationen.

- Rote Basis: `phase9-gate-backend-red.log`, 14 Tests, 39 fehlende Gate-/Residenz-Assertions; zusätzlich zwei Laufzeitfehler im noch ungeschützten Race/fehlenden Methodenpfad. Der frühe erste Versuch mit vielen einzelnen Fixture-Commits wurde als eigener Testprozess abgebrochen und durch den vollständigen protokollierten Lauf ersetzt. Der Race-Test wurde danach auf abgeschlossene Tasks vor Freigabe des simulierten Sprachrequests präzisiert.
- Separates sauberes Settings-RED: `phase9-gate-backend-settings-red.log`, 2 Assertion-Fails vor dem Settingsgate: HTTP200 erlaubte die Änderung während Sprachbusy/Unknown.
- Gate-GREEN: `phase9-gate-backend-green.log`, 19 Tests OK in 26.411 Sekunden. Alle vier Routen, sämtliche ungelösten/alten Zustände, defekter Beleg, beide Rennrichtungen, sofortige Free-Ablehnung, Duplikat-Idempotenz, native GPU-Residenz/CPU0/leere Liste/Offline, Comfy-GPU gegenüber CPU-RAM und Offline/unprüfbare Queue, load-Timeout und exaktes UI-Freigabeziel, persistenter chat-Timeout, GET-Ausfall ohne eigene Unsicherheit, ungültiger fertiger Vorschlag ohne Auto-Unload, Settingsrace und Endpunktbindung.
- Angrenzende Module: `test_jobs`, `test_server`, `test_resources`, `test_ollama_provider`, `test_ollama_http`, `test_ollama_integration`, `test_tool_proposals`, `test_ui_restart`; **79 Tests OK in 70.554 Sekunden**, Exitcode 0. Log: `phase9-gate-backend-adjacent.log`.

### Unabhängiger Review-Nachtrag: ungültiges frisches api/ps

Der unabhängige Review fand einen echten P2: `_loaded_names` übersprang ungültige Einträge in einer ansonsten listenförmigen `models`-Antwort. Nach einem expliziten Reconcile-Unload konnte deshalb `{'models':[{}]}` wie eine bestätigte Abwesenheit wirken und die persistente Unknown-Quittung löschen.

Enger Fix ausschließlich in `_loaded_names`: jeder Eintrag muss einen gültigen eindeutigen Namen liefern; vorhandene `name`-/`model`-Felder dürfen nicht widersprüchlich oder unbrauchbar sein. Ein echter leerer Array bleibt ein gültiger frischer Abwesenheitsbeleg. `gpu_residency` bleibt unverändert: unprüfbare optionale Belegung liefert weiterhin Unknown und eine Warnung beim Bildstart; daraus wird kein Abwesenheitsbeleg für eine eigene Mutation.

Vor dem Fix: `phase9-gate-backend-invalid-ps-red.log`, 3 Tests, 10 erwartete Assertion-Fails. Die End-to-End-Fixture erhielt fehlerhaft HTTP200/unloaded, nachdem ein korrekt bestätigter POST erst die folgende api/ps-Antwort ungültig machte. Weitere Fixtures decken fehlende/ungültige Namen und widersprüchliche name/model-Werte ab.

Nach dem Fix: **41 Tests OK in 28.260 Sekunden**, Exitcode 0; ausschließlich die nun 21 Gatefälle und 20 vorhandenen Ollama-Providerfälle. Log: `phase9-gate-backend-invalid-ps-green.log`. Der neue Reconcile-Test bestätigt außerdem: Unknown und Bildsperre bleiben nach der ungültigen frischen Antwort erhalten; erst ein weiterer bewusster, korrekt bestätigter unload mit echter leerer Liste schließt ab. Kein echter Dienst oder Modell wurde verwendet. Der obige 79er-Lauf liegt vor diesem eng begrenzten Adapter-Nachtrag und wurde gemäß Root-Auftrag nicht pauschal wiederholt. Finale Hashdatei wurde auf diesen Stand aktualisiert.

Die asyncio-Debugausgaben enthalten Laufzeit-/Slow-Task-Hinweise der isolierten Dateifixtures. Ein grüner Fixturelauf ist keine echte GPU-/Qualitätsabnahme. Root übernimmt nach finalem unabhängigen Review genau einen gemeinsamen Gesamtprüflauf, danach den gemeinsamen lokalen Commit. Finale Dateihashes: `phase9-gate-backend-tested-hashes.json`.

## Grenzen und Quellen

Der Lock schützt MORPH-Aktionen in dieser UI-Instanz. Direkte fremde Ollama-/Comfy-Clients liegen außerhalb und können zwischen lesender Prüfung und späterer GPU-Aktion eingreifen. Es gibt keine allgemeine VRAM-Fit-Garantie. Nach externer Settingsänderung bei vorhandenem Unknown ist die normale Settingsroute bewusst gesperrt; eine Wiederherstellung des ursprünglichen Endpunkts erfordert eine konkrete externe Korrektur. Korruptes internes Unknown ohne eindeutigen Modellnamen wird gesperrt und benötigt Diagnose.

Aktuell lesend geöffnete Primärquellen: [Ollama api/ps](https://docs.ollama.com/api/ps) für `size_vram`; [Ollama api/generate](https://docs.ollama.com/api/generate) für `keep_alive: 0`, `done` und Modellname. Comfy-Torch-Semantik war im übernommenen Hand-off konkret am lokalen `comfy/model_management.py` nachgewiesen; es wurde keine Laufzeit daraus gestartet.

Unmittelbar nächster Schritt: Unabhängiges Backend-/Frontend-Review durch Root und Frontendagent; nur konkrete Befunde korrigieren. Danach führt Root den bereits angekündigten gemeinsamen Gesamtprüflauf und den lokalen Commit aus. Keine weiteren Livebefugnisse daraus ableiten.
