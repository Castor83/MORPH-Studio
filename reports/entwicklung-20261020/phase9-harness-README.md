# Phase 9: getrennte echte Einzelaktionen

**Offline geprüft; reale Abnahme nicht ausgeführt.** Dieser Helfer startet keine Dienste und installiert oder lädt keine Dateien herunter. Die übergeordnete Phase-9-Anweisung, die vorherige Sicherung/Bestandsaufnahme, die fertigen Phase-8-/GPU-Gate-Commits und die jeweilige Ankündigung bleiben Voraussetzung. Der produktive API-Stand muss insbesondere `GET /api/status → language_state` enthalten. `--help` öffnet keine Verbindung. Nur die vorhandene Projekt-Python-Laufzeit mit aiohttp/Pillow verwenden.

```powershell
$phase9Python = 'E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe'
$phase9Script = 'E:\MORPH-Studio\reports\entwicklung-20261020\phase9_real_acceptance.py'
& $phase9Python $phase9Script --help
```

Jeweils **nur eine** der folgenden Aktionen gezielt ausführen und ihren Beleg prüfen. Keine Schleife oder Gesamtausführung darüber legen.

| Aktion | Wirkung / Voraussetzung |
| --- | --- |
| `--action resources` | Ausschließlich lesende Status-/Ressourcenabfrage; keine Berechnung. |
| `--action prepare` | Vorhandenes 1024²-Erwachsenenporträt hochladen, eigene deckende L-PNG-Maske (`y>640`, `R>1.6G`, `R>1.4B`, `R>35`) erstellen/hochladen, eigenes `LIVEABNAHME20Oct`-Projekt erzeugen. Original bleibt erhalten. Keine Berechnung. |
| `--action edit1` | Original ausdrücklich über `/api/image-versions/{id}/input` auswählen; ein maskierter KREA-Auftrag: Hemd dunkelblau. |
| `--action edit2` | Bestätigte einzige Ergebnisversion von edit1 auswählen; ein Auftrag: Hemd dunkelgrün. |
| `--action branch` | Ebenfalls edit1 als Elternversion auswählen; ein eigener Zweig: Hemd violett. |
| `--action cancel` | Ebenfalls edit1 wählen; einen zusätzlichen KREA-Auftrag mit acht Schritten senden und nach Erhalt der Quittung gezielt `/api/jobs/{id}/cancel` aufrufen. Fertigrennen wird als solches erhalten, ohne Wiederholung/globalen Interrupt. |
| `--action language` | Nur bei aktuell exakt ausgewähltem `huihui_ai/qwen3.5-abliterated:9b`: Ladezustand über MORPH bestätigen, bei Bedarf einmal laden; genau einen kurzen deutschen KREA-Werkzeugvorschlag mit vollständigen aktuellen Controls anfordern. Keine Übernahme/Bildberechnung oder automatische Entladung. Bereits geladene fremde Modelle blockieren einen neuen Ladevorgang. |
| `--action language-unload` | Separat ausdrücklich aufrufen: ausschließlich die bestätigt selbst geladene Instanz entladen. Ein unbestätigter eigener Ladeversuch ist nur mit exakt gespeicherter Instanz, vorher leerem Inventar und derselben serverseitigen `uncertain_instances`-Kennung zulässig. Bei `busy`, fremder Unklarinstanz oder geändertem Provider/Modell stoppen. Auch ein aktuell leeres Inventar schließt einen unklaren Ladeversuch nicht: die explizite Entladequittung plus frische Abwesenheit und geklärter `language_state` entscheiden. Keine Einstellungsänderung, kein zweiter Vorschlag. |
| `--action free` | Nur bei serverseitigem `unload.allowed=true` und keinen aktiven/unklaren eigenen Aufträgen einmal `POST {}` an `/api/resources/free`; asynchrone Quittung und spätere Ressourcenlesung speichern, keinen Entladeabschluss behaupten. |
| `--action observe --target-action edit1` | Gespeicherte Request-ID von edit1 lesend nachschlagen und den vorhandenen Auftrag weiter beobachten. Auch edit2, branch oder cancel zulässig. Kein erneuter Submit/Cancel. |

Beispiel für **eine** ausdrücklich gewählte Bildaktion:

```powershell
& $phase9Python $phase9Script --action edit1
```

Bildaktionen erhalten alle KREA-Defaults einschließlich bestehender Modellkomponenten aus `GET /api/workflows`; geändert werden Auftrag, 768×768, acht Schritte, Referenzstärke 1 und dokumentierte unterschiedliche Seeds. Die Maske wird an die konkret ausgewählte Quell-/Eltern-ID gebunden; ihre gespeicherte SHA-256 wird vor dem Submit erneut mit den API-Bildbytes verglichen. Jede Jobquittung muss Request-/Prompt-ID, Workflow, Projekt, Parent, Controls, Eingabebild und Maskenzuordnung bestätigen, bevor Cancel oder weiteres Polling zulässig ist. Eine angenommene Ergebnisversion muss genau einmal vorliegen und Projekt, Parent, Workflow sowie Status bestätigen. Die finalen Kompositbilder behalten Quellmaße; deshalb bleiben Maske und Seitenverhältnis deckungsgleich.

Jeder Lauf prüft `app=morph-ui`, den aufgelösten Projektpfad `E:\MORPH-Studio` und dieselbe UI-PID vor Mutationen. Alle HTTP-Aufrufe bleiben bei `127.0.0.1:8765`, ignorieren Proxy-Umgebungsvariablen, erlauben keine Weiterleitungen und haben Zeitgrenzen. Aktionslimit: standardmäßig/maximal 900 Sekunden, `--deadline 30..900`; Pollintervall standardmäßig drei Sekunden. Während langer Antworten erscheinen alle zehn Sekunden Wartehinweise.

Belege: `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-live\<action>-<UTC>.json`; eigener Zustand: `acceptance-state.json`. IDs/Quittungen/Controls, tatsächliche promptgebundene Job-WS-Felder, Knotenschritte, UTC-Zeiten und Ressourcen-/VRAM-Snapshots werden fortlaufend atomar gespeichert. `100 %` ist kein Abschlussbeweis: der terminale Job-History-Zustand und gespeicherte Versionen entscheiden. Visuelle Qualität, Deutscheignung und Pixelabweichungen außerhalb der Binärmaske müssen separat beurteilt werden. UI-Vergleich/Zoom/Pan, ReActor, DB-Sicherung und Gesamtregression gehören zum Hauptauftrag; der Helfer ersetzt diese Schritte nicht.

**Unklare Antwort / Zeitlimit:** Die einmalige API-Request-UUID samt Nutzlast wird vor Projekt-/Bildsubmit gespeichert. Zusätzlich erhält jeder einzelne HTTP-Versuch vor dem Transport eine dauerhaft gespeicherte lokale `attempt_id`; bei Upload/Modell/Free/Cancel ist das lediglich eine Belegkennung, keine serverseitige Idempotenzgarantie. Danach ausschließlich bestehende Quittung abfragen; kein automatischer POST-Retry, keine neue Request-ID, kein Löschen. Eine bereits reservierte Mutation bleibt bei erneutem Aufruf gesperrt. Für Bildaufträge `observe` verwenden; fehlgeschlagene Vorbereitung/Modellaktionen anhand des Belegs manuell einordnen. Nach einem Sprachfehler/Timeout niemals einen zweiten Vorschlag ausführen; die bewusste separate `language-unload`-Aktion hält den ursprünglichen Fehlerbeleg erhalten. Eine nach hartem Prozessabbruch verbleibende `acceptance-action.lock` erst nach Prüfung von PID und Zustand manuell behandeln. Clientabbruch stoppt keine entfernte Berechnung. API-Fehler werden nur über ihren Fehlercode gespeichert; rohe Einstellungsdateien werden nicht gespeichert.

Offline-Regressionsbeleg: `E:\MORPH-Studio\reports\entwicklung-20261020\test_phase9_real_acceptance.py`, `phase9-harness-red.log` (5 erwartete Fehler vor Korrektur), `phase9-harness-unknown-red.log` (2 erwartete Fehler vor Unklarzustand-/Masken-Hashkorrektur), `phase9-harness-green.log` (zunächst 9/9 PASS), `phase9-harness-chunked-red.log` (2 erwartete Fehler für Teilbytes vor EOF), `phase9-harness-chunked-green.log` (final 11/11 PASS). API- und Bildantworten werden bis EOF in begrenzten Blöcken gelesen; die Gesamtgröße bleibt auf 8 MiB beziehungsweise 64 MiB beschränkt. Die Tests benutzen ausschließlich lokale temporäre Journale und Transportdoubles; keine HTTP-Verbindungen, Dienststarts oder Modellaufrufe. Vollständiger Review: `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-harness-review.md`.
