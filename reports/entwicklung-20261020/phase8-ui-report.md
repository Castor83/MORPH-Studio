# Phase 8 – Frontend: beobachteter Knotenfortschritt

Stand 20.10.2026. Ausgangs-HEAD `1ad7201c2ad619960aa35d96f5226ef0597dbaef`. Freigegebener Auftrag des Hauptchats: Fortschrittsoberfläche im bestehenden Checkout implementieren; kein eigener Dienst-, Browser-, GPU- oder Modellaufruf, keine Gitmutation. Ausschließlich die fünf unten benannten Frontend-/Testdateien wurden geändert. Vorhandene Fremdänderungen und Pausendateien bleiben erhalten.

## Verhalten

- `ui/frontend/results.js`: echte `job.phase`-Werte `connecting`, `checking`, `uploading`, `submitting` erklären Vorbereitung und Übergabe auf Deutsch. Bestehende Statusabzeichen, Fehlerdetails, Ergebnisse und gerichtete Abbruchbedienung bleiben bestehen.
- `job.progress` enthält beobachtete Angaben aus dem Backend. Ausschließlich ein `progress`-Ereignis mit Knoten-ID und endlichen numerischen Werten `0 <= value <= max`, `max > 0`, erzeugt einen nativen Fortschrittsbalken. Beschriftung ausdrücklich „Knotenfortschritt“ und „Schritt … im aktuellen Knoten“. Prozent werden aus `value/max` berechnet; kein Gesamtfortschritt, keine Restzeit und kein automatisches Hochzählen.
- Knotenklasse und ID erscheinen über `textContent`. Modellknoten werden nur anhand benannter Modellloader-Familien gekennzeichnet; ein `ImageLoader` bleibt ein gewöhnlicher Knoten. Das Ausführen eines Modellknotens wird nicht als vollständig geladenes Modell dargestellt.
- `executing`, Knotenwechsel und Cachemeldungen übernehmen keine alten Prozentwerte. Cachemeldungen nennen nur die Anzahl der gemeldeten Knoten. Vorbereitete, übergebene oder wartende Aufträge erhalten keine Prozentanzeige.
- `reconnecting`, `unavailable` und `closed` markieren Werte als „Letzte Fortschrittsmeldung“ mit „Liveverbindung unterbrochen. Status wird geprüft.“ Knotenmeldungen werden dabei in die Vergangenheit gesetzt. WS-Erfolg/Fehler/Unterbrechung bleiben Hinweise zur anschließenden Statusprüfung. Nur `job.state` bestimmt den Endstatus; Endstatusbelege entfernen alte Fortschrittsanzeigen.
- `ui/frontend/app.js`: die Auftragsliste wird vor wartenden Detailabfragen gerendert, damit Vorbereitung bereits sichtbar und die Oberfläche bedienbar ist. Nutzerwechsel der Ergebnisansicht bleiben bei später eintreffenden Detailantworten erhalten. Ein wiedergefundener Startbeleg erhält ohne bestehende bewusste Auswahl den ursprünglichen Auswahlvorrang. Startschutz und erneute Versionsmetadatenprüfung bleiben erhalten.
- `ui/frontend/styles.css`: ein begrenzter Fortschrittsbereich innerhalb der bestehenden Ergebnisansicht.

## Prüfungen und Belege

- Dateikopien und SHA-256 vor Änderungen: `phase8-ui-baseline/manifest.json`, fünf Kopien unter `phase8-ui-baseline/ui/`.
- RED: `node --test tests/results.test.mjs tests/app.test.mjs`, 56 Fälle, 47 grün und 9 erwartete Fehler aufgrund fehlender Fortschritts-/Vorbereitungsanzeige. Beleg `phase8-ui-red.log`.
- Zwei gezielte Randfälle zusätzlich rot nachgewiesen: gewöhnlicher Bildloader versus Modellloader sowie wiedergefundener Startbeleg vor älteren abgeschlossenen Aufträgen. 58 Fälle, 56 grün und 2 erwartete Fehler. Beleg `phase8-ui-edges-red.log`.
- GREEN fokussiert: gleicher Node-Befehl, 58/58 bestanden, 0 Fehler/Abbrüche/übersprungene Fälle. Beleg `phase8-ui-green.log`.
- Gesamte Node-Suite genau einmal nach den Änderungen: `npm test` unter `E:\MORPH-Studio\ui`, 90/90 bestanden, 0 Fehler/Abbrüche/übersprungene Fälle. Beleg `phase8-ui-node-all.log`. Damit sind auch bestehende Ressourcen-, Ollama-, Masken-, Versions- und Formularfälle enthalten.
- `git diff --check -- ui/frontend/results.js ui/frontend/app.js ui/frontend/styles.css ui/tests/results.test.mjs ui/tests/app.test.mjs`: Exit 0. Git meldet ausschließlich die bestehende Windows-LF/CRLF-Konvertierungsregel.
- Tatsächliche Endhashes der fünf Dateien: `phase8-ui-final-hashes.json`.

Diese Nachweise sind synthetische Controller-/Renderprüfungen mit echtem Produktions-Renderer und kleinem Fake-DOM. Sie belegen keinen echten Comfy-WebSocket, Browserlayout, GPU-Lauf oder Bildqualität. Es wurden keine Dienste oder Modelle gestartet oder verändert. Kein Commit oder Staging durch diesen Agenten.

## Nächster Schritt

Dateien und aufgeführte Belege unverändert unabhängig prüfen. Danach übernimmt ausschließlich der Hauptchat die gebundene Phase-8-Integration, den freigegebenen Commit und die angekündigte Phase-9-Abnahme. Dieser Agent beendet die Änderungen bis zu einem konkreten Reviewbefund.
