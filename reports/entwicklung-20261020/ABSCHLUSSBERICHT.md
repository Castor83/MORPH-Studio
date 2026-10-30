# MORPH Studio – Entwicklungsabschluss und reale Abnahme

Abschlussstand20.10.2026,20:56 Europe/Berlin. **Entwicklung und vereinbarte gezielte Funktionsprüfung abgeschlossen, mit den unten genannten Bildqualitätsgrenzen.** Keine allgemeine Stabilitäts-, Qualitäts- oder Identitätsgarantie. Verbindlicher vollständiger Auftrag: `E:\MORPH-Studio\reports\entwicklung-20261020\Nutzerauftrag.md`; Arbeitsgeschichte: `CHAT-UEBERGABE-01a15a42.md`. Aktiver Hauptchat `01a15a96-e928-75b1-a7ff-a14b938129a0`.

## Ergebnis der Entwicklung

Phasen1–8 sind implementiert und isoliert geprüft. Vorher konnte die Dienstanbindung einen erreichbaren ComfyUI-Prozess anhand der Prozessargumente ablehnen. Jetzt entscheidet zuerst die kompatible lokale API; Prozessdaten bestimmen anschließend Verwaltungsrechte. Synchronisierte Starts verhindern Doppelstarts. Fremddienste werden nachvollziehbar abgewiesen; Übernahme einer kompatiblen Instanz erteilt keine Stop-/Freigaberechte. Die genaue historische Parameterabweichung ist nicht belegt.

Die deutsche Oberfläche bietet einfachen Modus, Expertenmodus, gemeinsame Datei-/Drag-and-drop-Verarbeitung und Eingabegenerationsbindung gegen verspätete Uploadantworten. Ollama bleibt optional. Vorschläge bewahren den Originalauftrag, zeigen Unterschiede und benötigen getrennte Übernahme und Bildstart.

Die Bildhistorie speichert Original und unabhängige Zwischenstände samt Parent, Prompt, Parametern und Modellkomponenten persistent. Weiterbearbeiten, Variantenwahl und Originalwahl sind bewusste Eingabeaktionen; Öffnen und Vergleichen starten nichts. Atomare Veröffentlichungen und gesonderte Recovery erhalten fertige Bilder bei Versionsspeicherfehlern ohne erneute Berechnung.

Beliebige Versionen sind mit gemeinsamem Zoom/Pan vergleichbar und unabhängig exportierbar. KREA/Kontext unterstützen genau an Quelle und Parent gebundene Masken. Die native Endkomposition erhält unmaskierte Pixel; das Modell sieht weiterhin das ganze Bild. Dies ist kein Nachweis nativen semantischen Inpaintings und keine allgemeine Identitätsgarantie.

Ressourcenanzeigen zeigen Messungen und lassen unbekannte Werte unbekannt. Bewusste Freigabe benötigt eigene Prozessquittung, leere Queue und genaue Instanzbindung. Gemeinsame Sprach-/Bildsperren verhindern konkurrierende MORPH-Aktionen; unbestätigte eigene Sprachmutationen bleiben nach Neustart gesperrt, bis eine gezielte bestätigte Wiederherstellung erfolgt. Direkte fremde Clients liegen außerhalb dieses Prozesslocks.

Fortschritt ist an Prompt-/Client-ID und tatsächliche Graphknoten gebunden. Prozentwerte gelten pro Knoten. Wiederverbindung und History-/Queue-Abgleich verwenden bestehende IDs und reichen keine neuen Aufträge ein.

## Quellstand und Prüfgrenzen

Repository `E:\MORPH-Studio`, Branch main, kein Remote/Push. Fremdänderungen werden weder gestaged noch zurückgesetzt. Basiscommits: dfaf115 Dienst/UI/Historie; d647745 Historien-Recovery; 316f570 Vergleich/Masken; ad4551d Sprachhilfe; 1ad7201 Ressourcen; 24b02f9 Fortschritt; 5b2c00d GPU-Koordination. Vorbereitung b630d1b und 96a1c5b. Reiner früherer Übergabecommit a95f7ac.

5b2c00d: Backend285/285, Frontend107/107, Starter38/38 PASS, Exit0; Originalbelege `phase9-final-backend.log`, `phase9-final-frontend.log`, `phase9-final-starter.log`. Das sind isolierte Regressionen, keine reale Bildabnahme. Für den späteren eng begrenzten Health-Fix b83042d: neuer RED404 und 10/10 passende Server-/Neustartfälle PASS, unabhängiger Gegencheck und echter NoBrowser-Start. Kein behaupteter erneuter Gesamtlauf nach diesem Zusatz.

Weitere Modi: WAN High-/Low-Paarung und steps/split-Kopplung, Qwen Text-zu-Bild, ReActor Gesichtsnummern/Sourceerhalt/Target-Versionsbindung sind isoliert geprüft (`ui\tests\test_model_dependencies.py`, `test_tool_proposals.py`, `test_ollama_provider.py`, `test_versions.py`). Historische echte Ergebnisse bleiben historische Belege. Keine aktuelle Qwen-/WAN-Qualitätsbehauptung und kein neuer Modellmarathon. Frühere FakeCompute-Browserbilder sind keine echten Modellresultate.

## Reale Phase9 – bisher belegt

- DB-Migration PASS: ursprüngliche38 Jobs/71 Medien vollständig und zeilenweise unverändert. Vorhandenes konsistentes Backup und automatisches additives Migrationsbackup sind SHA256-identisch, Integrität ok; `phase9-live-migration.json`.
- UI-Start: ursprünglicher falscher Timeout echt gefunden und in b83042d korrigiert. Reine Healthantwort0.036s, eigener UI-Prozess103344; `phase9-ui-health-fix.md`.
- Sprachhilfe PASS für einen engen deutschen KREA-Wunsch, kein Bildsubmit/keine Übernahme. Eigenes Modell separat bestätigt entladen, ebd89d2; `phase9-language-live.md`.
- Eigenes Abnahmeprojekt `3b6e96c43ad05e18a44513494cfa3d21`, Originalversion `8acb1ac88e6252e186b32e1efbbb57d5`. Synthetisches1024²-Porträt erhalten, eigene Uploadkopie und deckende L-PNG-Maske mit261825 weißen Pixeln vorbereitet. Regel y>640/R>1.6G/R>1.4B/R>35; Beleg unter phase9-live/prepare-20261020T184154588458Z.json.
- Erster eigener Comfy-Kaltstart PID107180 für einen KREA-Auftrag, ungefähr80s bis zur Jobquittung. Folgende Aufträge und ein erneuter NoBrowser-Starter nutzten dieselbe UI-/Comfy-PID ohne Doppelstart.

## Ergebnisse und Grenzen der gezielten Abnahme

| Bereich | Ergebnis | Beleg / Bedeutung |
| --- | --- | --- |
| UI-/Comfy-Start | PASS echt | Neuer Healthcheck, Kaltstart, Wiederverwendung derselben PIDs; keine fremden Stopps |
| Deutsche optionale Sprachhilfe | PASS eng | Ein echter Vorschlag, keine Übernahme/Bildberechnung; eigenes Modell getrennt entladen |
| Versionierung | PASS echt | Original→Blau→Grün und Blau→Violett, vier unabhängige persistent gespeicherte Versionen mit richtigen Eltern und Metadaten |
| Export | PASS echt | Vier einzelne Attachmentdownloads; SHA256 jeweils identisch zur Versionsmetadatenbindung |
| Maskenschutz | PASS echt | Bei allen drei Jobs außerhalb der Binärmaske0 geänderte Pixel/Delta0 gegenüber dem jeweiligen Parent |
| Kleidungsfarbe | PASS eng | Blau, Grün und Violett sichtbar; innen261822/261815/261781 geänderte Pixel |
| Identischer Schnitt/Textur | PARTIAL | Kragen und Stoffstruktur verändern sich innerhalb der Maske; feine Randnähte sichtbar. Kein perfektes reines Umfärben |
| Vergleich/Zoom/Pan | PASS echt | Nach Browserreload Projekt bewusst erneut geöffnet; beliebiges Grün/Violett-Paar bei200%, beide exakt translate(-5%,-5%) scale(2); Original/Parent/Swap/Reset geprüft |
| Fortschritt/VRAM | PASS eng | Tatsächliche promptgebundene Knoten-/Stepsnapshots und Messwerte; keine vollständige unabhängige Roh-WS-Aufzeichnung/keine kontinuierliche Spitzenmessung |
| Gezielter Cancel | PASS echt | Ein eigener kurzer Job terminal cancelled, ohne Ergebnisversion, keine globale Unterbrechung/kein Retry |
| Bewusste Freigabe | PASS eng | Eigene freie Instanz/leere Queue; accepted ist asynchron. Danach gemessener VRAM von15.18 auf1.45GB gesunken; vollständige Modellresidenz bleibt unbekannt |
| ReActor | PASS technisch / PARTIAL Qualität | Ein1024²-Ergebnis nach Source-/Targetanalyse und Swap; deutlicher Gesichtsdetailverlust beim vorhandenen128er-Modell ohne Restore |
| Verschiedene ReActor-Identitäten | UNVERIFIED | Synthetisches Paar zeigt ähnliche Varianten derselben Figur; keine Ausweitung auf neue Bilder/Modelle |
| Fremdport, Unterbrechung, Ollama-Ausfall, fehlendes Modell, Neustart-Recovery | PASS in Fixtures | Vorhandene gezielte automatisierte Grenzen; fremde reale Dienste nicht dafür unterbrochen |
| Weitere Bild-/Videomodi | Vorhandene Regressionen/historische Läufe | Keine neue aktuelle Qwen-/WAN-Qualitätsabnahme und kein Modellmarathon |

Kein weiterer Modelllauf zur Kaschierung eingeschränkter Qualität. Andere Motive, extreme Eingaben, kontinuierliche Spitzenlast und fremde direkte GPU-Clients wurden nicht abgenommen. Die vorhandenen Prozesssperren sind keine allgemeine VRAM-Fit-Garantie.

Alle aktuellen fachlichen Ergebnisse sind in `phase9-krea-live.md`, `phase9-cancel-free-live.md` und `phase9-reactor-live.md` mit IDs/Hashes dokumentiert. Rohbelege liegen unter `E:\MORPH-Studio\reports\entwicklung-20261020\phase9-live`. Strukturierte Übersicht `phase9-live-action-summary.json`. Höchster **beobachteter** GPU-Speicherwert15.380.046.324Bytes (rund14.32GiB), kein garantierter Spitzenwert. Keine zusätzlichen Testbilder nur für Messungen berechnet.

## Schlusszustand und lokale Sicherung

`phase9-final-real-state.json` wurde am20.10.2026,18:56:13UTC gelesen: DB43 Jobs/85 Medien (32 completed/6 cancelled/5 historische error), alle ursprünglichen38 Aufträge/71 Medien zeilenweise unverändert, Integrität ok und keine Fremdschlüsselfehler. Ein Projekt/vier Versionen. Kein ungelöster Auftrag. Historische Fehler wurden weder gelöscht noch als neu aufgetreten ausgegeben.

UI PID103344, Comfy PID107180 und vorhandenes Ollama bleiben bewusst verfügbar; keine pauschalen Stopps. Comfyqueue leer, Ollama api/ps leer, language_state busy=false/uncertain_instances=[]. NVIDIA-Momentaufnahme4076MiB genutzt/11973MiB frei nach ReActor; dessen Ressourcen wurden nicht automatisch entladen. Keine neue Automation. Eigene Aktionsclients und Prüfprozesse sind beendet. Keine globale Hook-/Handoffautomatik behauptet.

Das Pausepaar bleibt hashgleich. Settingshash hat sich durch reguläres Entladen geändert: die zuvor gespeicherte Instanzkennung wurde geleert. Rekonstruktion ausschließlich dieses einen Wertes ergibt exakt den ursprünglichen Datei-SHA256; keine manuelle Endpoint-/Modellauswahländerung. Ein unabhängiger begrenzter Evidenzcheck bestätigte Sprach-/KREA-/Cancel-/Free-Berichte; ReActor wurde danach vom Hauptagenten anhand tatsächlicher Ausgabe/Logs geprüft, kein zweiter unabhängiger ReActor-Livereview behauptet.

Neue lokale Blöcke:96a1c5b ReActor-Offlineabschluss; b83042d Startfix; ebd89d2 Sprachtest; e006aab Blau/Maskenschutz; c3a0a4e Grün;1031c22 Zweig/Browservergleich; c6e0f2a Cancel; dcb46c3 Freigabe; a5ea8b5 ReActor. Abschließender Dokumentationscommit folgt separat. Vollständige Produktdateiliste mit absoluten Pfaden `changed-product-files.txt`, Commitliste `development-commits.txt`. Die bereits vorhandenen Fremdänderungen/alten Löschungen bleiben unstaged erhalten; Modelle, DB, Originale, Bilder, Pause- und mutable Zustandsdateien wurden nicht als Quelländerungen committed. Kein Remote und kein Push.

Innerhalb der vereinbarten begrenzten Realabnahme ist keine weitere Ausführung offen. Die ausdrücklich genannten Qualitäts-/Übertragbarkeitsgrenzen bleiben erhalten; eine strengere Qualitätsabnahme wäre ein eigener konkret begrenzter Folgeauftrag.

## Start und Nutzung

`E:\MORPH-Studio\MORPH-Oberflaeche.cmd` oder `E:\MORPH-Studio\start-morph-ui.ps1 -NoBrowser`, Oberfläche `http://127.0.0.1:8765`. Der UI-Start allein lädt kein Modell. ComfyUI startet erst für eine bewusst gestartete Bildaktion. Sprachmodellladen und -entladen erfolgen separat.

Bildprojekt öffnen, gewünschte Version mit Weiterbearbeiten/Variante/Original verwenden wählen, Auftrag bearbeiten und separat Berechnung starten. Vergleichen öffnet zwei frei wählbare Versionen, gemeinsamer Zoom und Verschiebung gelten für beide. Jede Versionskarte besitzt Speichern/Exportieren.

## Sicherung und Wiederherstellung

Konsistente Sicherung: `E:\MORPH-Studio\reports\entwicklung-20261020\jobs-before-live-20261020T170319Z-09af2bbe.sqlite3`, SHA256514c64ea5527f147176398a844d06d6676102d9b4371fb780c3a0776f12631e1. Automatische Sicherung: `E:\MORPH-Studio\user\morph-ui\backups\before-image-versions-20261020T183532755294Z-d296b8e77e91429aae8de4a7cd26c94b.sqlite3`.

Wiederherstellung wurde nicht ausgeführt. Vor Ersatz der aktiven DB die eigene Oberfläche bei bestätigtem Leerlauf kontrolliert beenden, aktuellen DB-/WAL-Stand konsistent separat sichern und Sicherung zunächst in einer isolierten Kopie prüfen. Ein Rücksetzen auf die Vor-Migrations-DB entfernt darin spätere Metadaten; spätere Bilder/Versionen bleiben separat zu erhalten. Keine aktive DB überschreiben oder WAL-Dateien pauschal löschen. Ausführung erfordert konkreten Wiederherstellungsauftrag.

Maßgebliche Produktdateien: `E:\MORPH-Studio\tools\lmstudio-wan-chat\start_mcp.py`, `E:\MORPH-Studio\start-morph-ui.ps1`; unter `E:\MORPH-Studio\ui\morph_ui\`: comfy.py, jobs.py, versions.py, files.py, edit_region.py, catalog.py, model_library.py, resources.py, progress.py, tool_planning.py, providers\ollama.py; unter `E:\MORPH-Studio\ui\frontend\`: app.js, results.js, comparison.js, regions.js, resources.js. Die vollständige Produktdateiliste steht in `E:\MORPH-Studio\reports\entwicklung-20261020\changed-product-files.txt`.
