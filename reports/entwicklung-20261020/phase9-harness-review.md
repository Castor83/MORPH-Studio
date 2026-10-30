# Phase9-Abnahmeprogramm: unabhängiger Offline-Review

Stand: 20.10.2026, ausschließlich Offline-Arbeit. Repository bei Beginn aktuell gelesen: `E:\MORPH-Studio`, Branch `main`, HEAD `18522b6255befb633f5b193159f84326d521dbb5`. Bestehende fremde Änderungen wurden gelesen und nicht verändert. Kein Commit durch diesen Reviewagenten.

## Umfang und Entscheidung

**PASS im gezielten Offline-Umfang:** Der Harness ist für separat angekündigte Einzelaktionen vorbereitet. Reale API-, Dienst-, Sprachmodell-, Bild-, Cancel- und Freigabeabnahme bleibt **UNVERIFIED**. Vor Liveaufruf müssen der neue GPU-Gate-Backendstand und die zugehörige UI separat geprüft und committed sein; insbesondere muss `GET /api/status` `language_state={busy, uncertain_instances}` liefern.

Gelesen: `C:\Users\USER\.codex\AGENTS.md`, `E:\MORPH-Studio\AGENTS.md`, README/PROJECT_STATE und historische Pausedateien, vollständige Phase9-/Restarbeitsabschnitte in `E:\MORPH-Studio\reports\entwicklung-20261020\CHAT-UEBERGABE-01a15a06.md` und vollständige `Phase9-Echte-Abnahme-Anweisung.md`. Keine neue Pause und kein Handoff durch diesen Subagenten. Memory diente ausschließlich dem historischen Routing; aktuelle Arbeitsfakten wurden direkt aus Dateien bestätigt.

Gegen die reale API und lokalen Code abgeglichen: `E:\MORPH-Studio\ui\morph_ui\server.py`, `jobs.py`, `versions.py`, `files.py`, `edit_region.py`, `catalog.py`, `providers\ollama.py`, `resources.py`. Der laufende Backendprozess wurde nicht angesprochen.

## Gefundene und behobene Fehler

1. **FAIL vor Korrektur:** `language` entlud im `finally` selbst nach unbestätigter Vorschlagsantwort oder CancelledError; das konnte eine aktive/unbekannte Backendmutation treffen und den ursprünglichen Fehler überdecken. **PASS danach:** keinerlei automatische Entladung. Die neue separate `--action language-unload` ist eine bewusste Aktion und erhält den ursprünglichen Beleg. Bestätigte eigene Ladung ist Voraussetzung; nach einem unbestätigten Ladeversuch sind alternativ exakt gespeicherte eigene Instanz, zuvor leeres Inventar und dieselbe serverseitige Unknown-Instanz nötig. Fremde Unklarinstanz/busy/geänderter Provider oder Modell werden abgelehnt. Eine leere Modellliste ersetzt keinen Unknown-Abschluss: explizite Entladequittung, frische Abwesenheit und geklärter `language_state` entscheiden.
2. **FAIL vor Korrektur:** Cancel konnte schon vor vollständigem Kontextabgleich erfolgen; Requestquittung prüfte nur die Request-ID. **PASS danach:** Job-ID, Request-/Prompt-ID, Workflow, Projekt, Parent, Controls, Quellbild, Masken-ID und Quellen-/Maskenbindung müssen vor Cancel und jedem Poll übereinstimmen. Im Journal vorhandene Quellen-/Masken-SHA-256 müssen ebenfalls mit dem vom Backend bestätigten Bereich übereinstimmen. Die Uploadmaske wird vor jedem Submit erneut byteweise per SHA-256 geprüft.
3. **FAIL vor Korrektur:** Beliebige nichtleere Versionsliste galt als Erfolg. **PASS danach:** genau eine abgeschlossene Ergebnisversion mit passendem Projekt, Parent und Workflow ist erforderlich. Ungültige Versionen erhalten keinen autorisierenden `terminal_state=completed`/Versionsbeleg für Folgeaktionen.
4. **FAIL vor Korrektur:** Nicht alle HTTP-Mutationen hatten eine vor Transport gespeicherte Versuchskennung; API-Fehlerdetails wurden ungekürzt geloggt. **PASS danach:** jeder einzelne Transportversuch erhält atomar vorab eine lokale UUID. Für Projekt und Bildauftrag bleiben die gesonderten serverseitigen Request-UUIDs maßgeblich. API-Fehlerhüllen werden über ihren Fehlercode erfasst, ohne rohe Message/Details zu übernehmen. Die lokale `attempt_id` behauptet keine serverseitige Idempotenz für Upload, Modellaktion, Cancel oder Free.
5. **FAIL im Root-Re-Review und offline reproduziert:** einmaliges `StreamReader.read(n)` lieferte bei Teilpaketen abgeschnittene JSON-/PNG-Daten. **PASS danach:** beide Lesewege sammeln `iter_chunked(64 KiB)` bis EOF und prüfen vor jeder Übernahme die Gesamtgrenze (API 8 MiB, Bild 64 MiB). Zwei gezielte Offline-Chunked-Transportfälle prüfen vollständiges JSON und vollständige PNG-Bytes.

Beibehalten und gelesen: genau eine erforderliche `--action`, kein Default-Compute, keine Gesamtschleife, kein Submit-Retry, GET-Recovery über gespeicherte Request-ID, einmalige Reservierungen mit exklusivem Aktionslock, `trust_env=False`, feste Loopbackadresse, Origin/X-MORPH, keine Redirects, app/root/positive PID und dieselbe PID vor Mutationen, maximal 900 Sekunden. Clientende wird ausdrücklich als `CLIENT_STOPPED_REMOTE_STATE_UNCONFIRMED` protokolliert; kein Backendstopp/Interrupt wird behauptet oder gesendet.

## Prüfungen und Belege

- `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-harness-red.log`: **5 erwartete FAIL**, bestehende Mängel vor Korrektur reproduziert.
- `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-harness-unknown-red.log`: **2 erwartete FAIL** bei 9 Fällen vor exakter Unknown-Recovery-/Masken-Hashkorrektur.
- `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-harness-green.log`: **9/9 PASS**, 2.657 Sekunden. Tests benutzen echte Harnessfunktionen, atomare temporäre Journale und Transportdoubles; keinerlei HTTP-/Modell-/Dienstaktion.
- `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-harness-chunked-red.log`: **2 erwartete FAIL** bei 11 Fällen, Teilbytes vor EOF in API- und Bildpfad reproduziert.
- `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-harness-chunked-green.log`: **final 11/11 PASS**, 3.189 Sekunden, nach begrenztem vollständigem Einlesen beider Antworttypen. Keine Socket-, Transport- oder Ressourcenwarnungen.
- `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-harness-help.log`: **PASS**, Exit 0; Aktion und Deadline dokumentiert. Keine Verbindung.

Getesteter Befehl: `& 'E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe' -B 'E:\MORPH-Studio\reports\entwicklung-20261020\test_phase9_real_acceptance.py'`.

Nicht ausgeführt: Gesamtregression des Produkts (Root koordiniert nach finalem Backend-/Frontendstand), reale Vorschlagsqualität, reale Grafik, WS-/VRAM-Belege, Cancel, ReActor, Free. Keine Installation, Downloads, Bilderzeugung, Prozesssteuerung, DB-/Settingsänderung oder Git-Operation mit Mutation. Es wurden ausschließlich Harness, zugehörige Offline-Tests, README und dieser Bericht sowie Testlogs bearbeitet.

## Konkrete sichere Bedienung

Vorbereitung im Rootchat: produktiven Quellstand/Backup/Ankündigung prüfen, ggf. UI über bestehenden Startweg bereitstellen. Die folgenden Zeilen sind einzeln zu wählen und einzeln auszuwerten; keine Schleife darüberlegen:

```powershell
$phase9Python = 'E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe'
$phase9Script = 'E:\MORPH-Studio\reports\entwicklung-20261020\phase9_real_acceptance.py'
& $phase9Python -B $phase9Script --action resources
```

Nach konkreter Sprachmodellankündigung separat `& $phase9Python -B $phase9Script --action language`. Danach Ergebnis/Fehler prüfen; keinen zweiten Vorschlag senden. Die bewusste Freigabe ist ein neuer Einzelaufruf: `& $phase9Python -B $phase9Script --action language-unload`. Erst frische Zustandsbelege erlauben den nächsten Bildschritt.

Vorbereitung ohne Berechnung separat: `& $phase9Python -B $phase9Script --action prepare`. Danach Maske/Original-/Projektquittung prüfen. Der erste angekündigte GPU-Einzelaufruf ist `& $phase9Python -B $phase9Script --action edit1`. Nur bei unklarer Antwort: `& $phase9Python -B $phase9Script --action observe --target-action edit1`; niemals erneut edit1 oder eine neue UUID verwenden. edit2/branch/cancel/free sind spätere, ausdrücklich angekündigte einzelne Aktionen nach Ergebnisprüfung.

Geänderte Hauptdateien: `E:\MORPH-Studio\reports\entwicklung-20261020\phase9_real_acceptance.py`, `phase9-harness-README.md`, `test_phase9_real_acceptance.py`. Der Harness erzeugt reale Belege erst unter `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-live`; dieser Review hat dort keinen echten Aktionszustand angelegt. Historische private ReActor-Quelldaten sind keine freigegebenen Abnahmedaten; die Suche nach einem synthetischen Paar bleibt eine separate lesende Folgeaufgabe.
