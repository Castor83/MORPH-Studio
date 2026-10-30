# Werkzeugvorschläge: Auftrag, Bildprompt und sichtbarer Vorschlag

Stand: 20.10.2026, Europe/Berlin. Arbeitsbereich `E:\MORPH-Studio`, Branch `main`, Ausgangscommit `7c8732cf2e816dfdcdd7279cb61776cba93607f3`, kein Remote/Push. Hauptchat `01a15b11-d208-7001-a074-c5ad56de4aa7`. Fortsetzung des ausdrücklich autorisierten Entwicklungsauftrags aus `CHAT-UEBERGABE-01a15a96.md`; keine Pause und kein neues Komprimierungsereignis dieses Chats.

## Nutzerbefunde und Ursache

„Der Vorschlag verwendet den Bildprompt und ignoriert meinen Text in ‚Dein Auftrag‘.“ Später: „ich sehe auch nicht das ein promt generiert wird nur mein selbst geschriebbener befehl“.

Der Datenfluss im Frontend friert beide Felder bereits getrennt ein. Ein automatisches Überschreiben des Auftrags wurde nicht gefunden. Im Backend standen bisheriger Bild- und Negativtext jedoch in der höher gewichteten Systemnachricht. Der neue Auftrag kam als separate Nutzernachricht. Dieser Rollenfehler ist mit dem bereits vor Übergabe roten Test für beide aktiven Provider belegt. Seine genaue Auswirkung auf den früheren konkreten Modelltext ist daraus nicht rückwirkend bewiesen.

Zweite belegte Lücke: Der zurückgelieferte `step.prompt` wurde nur im allgemeinen Vorher/Nachher-Vergleich dargestellt. Bei Gleichheit mit dem eingefrorenen Formularwert verschwand er vollständig. Davor wurden Auftrag und ursprünglicher Formularstand angezeigt. Der live gelesene Nutzertab enthielt zu diesem Zeitpunkt keinen fertigen Vorschlag; er beweist deshalb keine konkrete frühere Modellantwort.

## Umsetzung

- `ui\morph_ui\tool_planning.py`: validierten Auftrag unverändert speichern; gemeinsamer Nachrichtenaufbau `system,user,user`. System enthält Regeln, Katalog, Profil und übrige Einstellungen. Vollständige alte Freitexte stehen genau einmal im gekennzeichneten Nutzerkontext. Letzte Nachricht ist exakt der ursprüngliche neue Auftrag, einschließlich Leerraum.
- Explizite Vorrangregel für den neuen Auftrag. Das Sprachmodell soll einen präzisen Prompt aus Auftrag und Werkzeugprofil formulieren und widersprüchliche Negativangaben entfernen. Alte Berechnungseinstellungen bleiben die Basis. `self.current`, Schema, Parsing und WAN-Kopplung bleiben erhalten.
- `ui\morph_ui\providers\ollama.py` und `lmstudio.py` verwenden dieselbe Nachrichtenmethode. Gesamtlimit unverändert 8.192 serialisierte Bytes einschließlich Antwortschema, Rollen und Katalog; Prüfung vor Provider-I/O. Kein Abschneiden, keine automatische Wiederholung. Kontext 4.096, Ausgabe 1.024, Temperatur 0,2; Ollama `think=false`, `keep_alive=5m` unverändert.
- `ui\frontend\proposals.js`: eigener Abschnitt **Vorgeschlagener Bild-/Videoprompt** in jeder passenden Schrittkarte, auch bei unverändertem Text. Eine wortgleiche Rückgabe des Auftrags wird ausdrücklich benannt. Bestehender Vergleich bleibt erhalten; Textausgabe über `textContent`.
- Beide Eingabefelder bleiben unabhängig. Übernahme und Bildstart bleiben getrennte bewusste Aktionen. Der ältere Einzelvorschlagspfad `propose()` wurde bewusst nicht erweitert.
- Dokumentiert in `ui\README.md`; gezielte Regressionen in `ui\tests\test_tool_proposals.py`, `test_prompt_profiles.py`, `tool_proposals.test.mjs` angepasst/ergänzt.

## Gezielte Offlineprüfung

Embedded Python: `E:\MORPH-Studio\ComfyUI_windows_portable\python_embeded\python.exe -B`; Testmodule `test_tool_proposals`, `test_prompt_profiles`, `test_ollama_provider`, `test_provider` mit explizitem Testpfad in `sys.path`. JavaScript: `node --test ui/tests/tool_proposals.test.mjs ui/tests/app.test.mjs`.

| Prüfung | Ergebnis | Beleg im selben Berichtsordner |
| --- | --- | --- |
| Ursprünglicher Vorrangtest vor Übergabe | RED, 1 Test, 2 Providerfehler | `prompt-priority-red.log` |
| Erster angrenzender Lauf | 55 Tests, 4 WAN-Budgetfehler | `prompt-priority-first-run.log` |
| Zweiter angrenzender Lauf | 55 Tests, 1 WAN-LMStudio-Budgetfehler | `prompt-priority-second-run.log` |
| Nach kompakteren Regeln | 55/55 PASS, Exit 0, 17,969 s | `prompt-priority-before-live-green.log` |
| Sichtbarkeit zuerst | RED, fehlender separater Promptabschnitt | `prompt-visibility-red.log` |
| Sichtbarkeit und Controller | 69/69 PASS, Exit 0 | `prompt-visibility-green.log` |
| Zusätzliche Negativtext-Regel zuerst | RED, 1 Test, 2 Providerfehler | `prompt-negative-rule-red.log` |
| Finaler Backendstand | 55/55 PASS, Exit 0, 17,678 s | `prompt-priority-green.log` |

Die anfänglichen Größenfehler wurden durch kompaktere Begleitregeln behoben, ohne Katalogtexte, Nutzereingaben oder Schema abzuschneiden und ohne das Budget zu erhöhen. Exakte 8.192-Byte-Grenze, Ablehnung vor jeglichem I/O, alle Standardwerkzeuge, vollständige alte Texte, unveränderter letzter Auftrag, ein Chatcall und bestehende WAN-Validierung sind abgedeckt. Keine Wiederholung der abgeschlossenen Phase-9-/Notfall-/Bildläufe.

Unabhängiger UI-Lesecheck bestätigte die Darstellungslücke. Ein anderer frischer Reviewer las den vollständigen finalen Quelldiff und danach den kleinen Negativregel-Zusatz: keine P1–P3-Befunde. Die Reviewer führten weder Tests noch HTTP-/Modellaktionen aus. Keine neue dynamische Browserabnahme der Vorschlagskarte behauptet. `git diff --check` für Quell-/Test-/Dokumentationsdateien erfolgreich. Der gesamte staged Diff meldet erwartete nachgestellte Leerzeichen in drei unveränderten rohen RED-/Zwischenlogs; diese Belege wurden nicht nachträglich normalisiert. Zusätzlich meldet Git bestehende LF/CRLF-Konvertierungshinweise. Finale Dateihashes: `prompt-fix-tested-hashes.json`; nach den Tests nur erklärender Codekommentar und README ergänzt.

## Genau eine echte Sprachprobe und ihre negative Evidenz

Eigene untätige Oberfläche kontrolliert mit `start-morph-ui.ps1 -NoBrowser -Restart` aktualisiert: UI 142056 → 144180. Comfy blieb gestoppt, Port 8188 frei. Geladen war `gpt-oss-20b-32k:latest`; die gespeicherte UI-Auswahl `huihui_ai/qwen3.5-abliterated:9b` war nicht geladen. Für die angekündigte einzelne Probe wurde ausschließlich das bereits geladene GPT-OSS-Modell über den vorhandenen `/api/tool-proposals`-Pfad verwendet. Keine Modellauswahl-, Lade-/Entladeaktion, kein Bildstart, kein automatischer Retry.

Synthetischer Auftrag: „Erstelle einen präzisen Bildprompt: eine blaue Keramiktasse auf einem Tisch, ohne Auto.“ Alter Bildtext: rotes Auto auf einer Straße; alter Negativtext: „Keine blauen Gegenstände.“ Keine Nutzerbilder oder tatsächlichen privaten Aufträge wurden für diese Probe verwendet.

Antwort am 20.10.2026 gegen 22:56 Berlin, 17,355 s: `sdxl`, Prompt **„Eine blaue Keramiktasse auf einem Tisch, ohne Auto.“** Der neue positive Bildwunsch wurde damit berücksichtigt und das alte Motiv verworfen. Der Prompt ist kurz; dies beweist keine allgemeine Ausarbeitungsqualität. Das Modell ließ gleichzeitig den widersprüchlichen alten Negativtext unverändert. **Gesamte semantische Konfliktauflösung deshalb PARTIAL, keine vollständige Modellabnahme.**

Die anschließend ergänzte explizite Regel `negative: Auftragswidersprüche entfernen` ist im finalen Payload für beide Provider offline geprüft. Ihre tatsächliche Befolgung ist **UNVERIFIED**. Es wurde bewusst keine zweite Modellanfrage gestartet. Der gezielte Softwarefix ist implementiert; zuverlässige semantische Negativtextkorrektur wird nicht garantiert.

Exakte Anfrage/Antwort: `prompt-live-request.json`, `prompt-live-response.json`; API-Zustände `prompt-live-before.json`, `prompt-live-after.json`. Die zusätzliche ursprüngliche Vor-Neustart-Arbeitskopie mit privaten letzten Aufträgen bleibt außerhalb des Commits.

## Daten, Aktivierung und verbleibende Grenze

Read-only-DB-Vergleich vor/nach Sprachprobe: sämtliche Tabelleninhalte per vollständigem geordnetem Zeilenhash gleich, Integrität `ok`, keine Fremdschlüsselfehler. 44 Jobs, 87 Medien, 2 Bildprojekte, 5 Versionen, keine persistierte offene Sprachmutation. Diese höheren Werte gegenüber der historischen Übergabe sind bereits vor der aktuellen Probe vorhanden gewesen. Belege `prompt-live-db-before.json`, `prompt-live-db-after.json`. Öffentlich ausgelesene Verbindungseinstellungen ebenfalls gleich. Keine DB-/Schema-/Bildmigration.

Nach finalem Negativregel-Zusatz eigener untätiger Dienst erneut gezielt aktualisiert: 144180 → 146872, Starter Exit 0, Health bestätigt `E:\MORPH-Studio`, Sprachzustand `busy=false`, `uncertain_instances=[]`, Comfy weiter gestoppt/8188 frei. `prompt-fix-final-restart.log`, `prompt-fix-final-runtime.json`. Kein zusätzlicher Modellaufruf. Keine neue Automation. Fremdänderungen und frühere Löschungen bleiben unangetastet/unstaged; keine Runtime-DB, Modelle, Bilder, Originale oder mutable Übergabestatusdateien im Commit.

Zum Nutzen der neuen Browserdarstellung die Seite neu laden und einen neuen Vorschlag erstellen. Der vorhandene Nutzertab wurde nicht neu geladen; offene Eingaben wurden nicht verändert. Im neuen Abschnitt steht genau der zurückgelieferte Prompt. Wortgleiche Rückgabe wird kenntlich gemacht, nicht als besondere Ausarbeitung ausgegeben. Bildqualität und allgemeine Modellbefolgung bleiben außerhalb der isolierten Tests; die beobachtete Negativtextschwäche ist ausdrücklich erhalten.

## Beleg-Hashes

- `prompt-priority-green.log`: SHA256 `626EA20290DBC04392ED10E7A8A9D235A2CE9B253350D2EDEE2FC1C2A78B31CB`.
- `prompt-visibility-green.log`: SHA256 `2179DE483FDB7EED6D95C4680D402B210A4633C0A82A6E33648FF99C08E1CF97`.
- `prompt-live-request.json`: SHA256 `41FA3B868BBB7174F37D6FA2487E3D973393B50D6CCD350D2D69AE9002DE6BDC`.
- `prompt-live-response.json`: SHA256 `BDBCC0A46A89668D00FDDA4FE856ADFFFF51958045CF25027F430B2959A82F2D`.
