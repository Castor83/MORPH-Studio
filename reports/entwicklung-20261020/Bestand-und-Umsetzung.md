# MORPH Studio: Bestandsaufnahme und Umsetzung, 20.10.2026

## Verbindlicher Auftrag
Quelle: Nutzerauftrag.md im selben Verzeichnis. Bestehende lokale Architektur weiterverwenden: eigenstaendige MORPH-Oberflaeche, ComfyUI als Bildbackend, Ollama optional. Routineaenderungen innerhalb dieses Auftrags sind freigegeben. Keine Datenloeschung, inkompatible Migration, grossen Modelldownloads oder grundlegende Architekturabweichung ohne Zustimmung.

## Phase 1: aktuell gepruefter Bestand
- Arbeitsverzeichnis E:\MORPH-Studio. Git main, HEAD a1a4127; zahlreiche bestehende uncommittete und unversionierte Dateien sowie bereits fehlende Berichtsdateien. Kein Remote. Nichts zurueckgesetzt oder geloescht.
- MORPH-Oberflaeche.cmd -> start-morph-ui.ps1 -> ComfyUI_windows_portable\python_embeded\python.exe -B ui\morph_ui\__main__.py. HTTP 127.0.0.1:8765, Python aiohttp, Browseroberflaeche aus HTML/CSS/JavaScript ohne Build-/Cloudpflicht.
- MORPH-Start.cmd -> start-morph.ps1. ComfyUI Portable und Python sind vorhanden. comfy.py laedt tools\lmstudio-wan-chat\start_mcp.py dynamisch. Eine Klasse ComfyStarter existiert hier nicht; ensure_comfy ist eine Modulfunktion.
- 20.10.2026 16:51: keine Listener auf 8188/8765 sichtbar; GET system_stats, queue und UI status mit Connection refused. Dies ist eine Momentaufnahme. Ollama noch nicht aktuell als geladen/ausgefuehrt bestaetigt.
- ui\morph_ui\catalog.py: sechs vorhandene Werkzeuge SDXL/SD1.5 T2I, FLUX Kontext Edit, ReActor Gesichtstausch, Wan I2V, Qwen Image2.1/NoctQ T2I, KREA2 GGUF Edit. Modellrollen, Header-/Tensorpruefung und Komponentenabhaengigkeiten in model_library.py/catalog.py. Keine generische Freigabe beliebiger Workflows.
- ui\morph_ui\files.py: gepruefte PNG/JPEG/WebP Uploads, lokale Medienbelege, Input/Output/Temp-Grenzen; noch keine Ausgabe als neue Eingabe, keine Bildprojekte/Versionierung.
- user\morph-ui\jobs.sqlite3 nur lesend geprueft: Tabellen media (71 Eintraege) und jobs (38 Eintraege). jobs: 28 completed, 5 cancelled, 5 error; vier comfy_start und ein request_not_received. Keine aktiven/verwaisten Jobs in dieser Momentaufnahme. Kein Anlass fuer Loeschungen.
- jobs.py: eindeutige Request-/Prompt-IDs, dauerhaft gespeicherte Auftraege, kein automatischer Submit-Retry, Serialisierung, Queue-Sperre, gerichteter Abbruch, Neustartsperre, Wiederaufnahme ungeklärter Belege. Noch keine Versionsbeziehungen.
- frontend: Bildauswahl/Vorschau, sechs Werkzeuge, Parameter und Ergebnisse/letzte Auftraege, Modellkatalog, optionale Ollama-Schrittvorschlaege mit einzelner Uebernahme. Kein Einfach/Experte-Schalter, Drag&Drop, versionierter Baum, Weiterbearbeiten oder synchroner Vergleich.
- providers\ollama.py und tool_planning.py: lokale API, Kontext4096, begrenzte strukturierte Werkzeugvorschlaege; Vorschlaege und Berechnung getrennt. Reparaturbericht vom18.10 beachten; alte P2-Pausenpunkte nicht als aktuell offen darstellen.
- comfy.py: bisherige Dienstidentifikation verlangt exakte Prozessargumente; compatible API allein wird nicht uebernommen. Ausgabepfade werden lokal vorausgesetzt. Polling von queue/history; noch kein Schrittfortschritt.
- Bestaetigte Diagnose: vier gespeicherte Ablehnungen vorhandener Listener. Letzte: 19.10 15:15:18 UTC PID15608; genauer abweichender Parameter unbekannt. UiError ist korrekt definiert/importiert. Frontend blendet error_code/details aus und zeigt jeden nicht bereiten Zustand als startet bei Berechnung. Gleichwertiges --port=8188 wird abgelehnt.
- Zusatzbefunde: AnimateDiff-Evolved enthaelt nur models, __init__.py fehlt; optionales PatchTritonVAE konnte am18.10 wegen fehlendem triton nicht importiert werden. Derselbe Log bestaetigt erfolgreichen ComfyUI-Serverstart danach. Keine Neuinstallation daraus ableiten.
- Native Masken/Inpainting-Knoten vorhanden, noch keine Integration ins MORPH-Bedienkonzept. Modell-/VRAMstatus und weitere Parameter nur anbieten, wenn lokal/API belegt.

## Sicherungen und Grenzen
Erste Reparaturbaseline: reports\dienstdiagnose-reparatur-20261020\baseline und baseline-manifest.json. Produktionsdaten vor Migration mit SQLite backup sichern. Neue Tabellen additiv, bestehende jobs/media erhalten. Modelle/Originale/Workflows nicht ueberschreiben. Tests verwenden temporaere Projektkopien und simulierte Dienste. Ein echter GPU-Lauf ist getrennt anzukuendigen und zu dokumentieren.

## Umsetzung und Abnahmefolge
1. Bestand (dieser Bericht, anschliessender Inventarzusatz).
2. ComfyUI API-kompatibel verbinden, Fremddienst/Portkonflikt unterscheiden, keine fremden Prozesse steuern, Diagnose verbessern. Externe Medien ueber API in eigenen Bereich kopieren. Auftragsbelege erhalten.
3. Einfach/Experte und klare deutsche Hilfen, Drag&Drop, bedienbare Ergebnis-/Fehleranzeige.
4. Additive Bildprojekte und unveraenderliche Versionen mit Eltern-ID, Medienbeleg und tatsaechlichen Berechnungsmetadaten. Explizite Aktion zur Auswahl fuer Weiterbearbeiten/Variante. Original bleibt erhalten.
5. Vergleich beliebiger Versionen mit synchronem Zoom/Verschieben und optionaler Differenz; Masken-/Inpainting-Eignung umsetzen ohne neue Modelle. Keine Garantie generativer Pixelidentitaet.
6. Vorhandene Ollama-Vorschlaege erhalten, optional, Originalauftrag/Vorschlag getrennt, Uebernahme startet keine Berechnung.
7. Vorhandene Modell-/Komponentenzuordnung erhalten; nur nachweisbare Lade-/VRAMdaten zeigen und Entladen gezielt anbieten. Keine Downloads.
8. Auftraege/Fortschritt mit echten API-Daten, gerichteter Abbruch, wiederherstellbarer Fehler statt pauschalem Loeschen.
9. Automatisierte Regressionspruefungen und gezielte echte Abnahme getrennt protokollieren. Endbericht mit geaenderten Dateien, Start-/Versions-/Wiederherstellungsanleitung.

## Entwurf fuer die neue Bildhistorie
Bestehendes aiohttp/SQLite-System erweitern. Neue Tabellen image_projects/image_versions in derselben Datenbank; bestehende Tabellen unveraendert. Versionen speichern Projekt, Elternversion, eindeutige Medien-ID, Zeitpunkt, Status, Prompt, Workflow, Modellkomponenten, Seed/Parameter und Auftrags-ID. Unveraenderliche Bildkopien unter output\MORPH-UI\versions; Originale nicht ueberschreiben. Erfolgreiche Jobs erzeugen idempotent Versionen, fehlerhafte Jobs keine beschaedigten Vorgänger. Weiterbearbeiten kopiert das ausdruecklich gewaehlte Bild in den freigegebenen Eingabebereich. Projekt/Elternversion werden beim Submit validiert und im Jobbeleg gebunden. Wiederholung derselben Request-ID bleibt idempotent. Beliebige Dateien/Projektgrenzen werden nicht freigegeben.

## Arbeitsnachweis Phase 2 (laufend)
- Root hat comfy.py, catalog.py, jobs.py und gezielte Tests erweitert. Vorhandene Dateien sind in reports\dienstdiagnose-reparatur-20261020\baseline gesichert.
- Status verwendet API-Erreichbarkeit auch ohne Prozessmetadaten. Kompatible Instanzen werden als compatible kenntlich, PID erteilt keine Prozesssteuerungsrechte.
- Backend-Uploads werden nicht mehr faelschlich als lokal vorhandene Eingabedateien vorausgesetzt. Nur vom Backend bestaetigte sichere Namen/Ordner werden eingesetzt.
- Ergebnisse werden ueber GET /view in den eigenen Outputbereich importiert, ohne Fremdpfade zu lesen. Maximal512MiB, keine Redirects, keine leeren/unsicheren Ausgaben. Teiluebertragungen werden nicht als fertige Datei veroeffentlicht.
- Ergebnisabruf kann nach Verbindungsfehler wieder aufgenommen werden, ohne erneute Berechnung. Teilimporte werden pro Backendreferenz gespeichert und bei Wiederholung wiederverwendet.
- Nachweis: comfy-api-red.log -> green, comfy-job-red.log -> green, output-recovery-red.log -> green, partial-output-red.log -> green. Letzter kombinierter Lauf:10 Tests OK. Angrenzende Job-/Server-/Modell-/Katalogregression:39 Tests OK (vor dem spaeter ergaenzten Teilimportfix; diesen nicht als Gesamtstandnachweis verwenden).
- Unabhaengige Pruefung fand P2-Mehrfachkopie bei Teilimport; Root hat Regression und Fix umgesetzt, Pruefer hat den Fix am Code nachgeprueft.
- Konsistente SQLite-Sicherung vor Versionierung: jobs-vor-versionierung.sqlite3 im Entwicklungsreport; integrity_check=ok,38jobs/71media. Produktionsdatenbank bisher nicht migriert und keine Auftraege geloescht.
- Noch laufend: Guard-API-Uebernahme/diagnostische Erkennung (Agent launcher_audit) und UI-Fehler-/Dienstanzeige (Agent ui_error_trace). Keine echte ComfyUI-/Modellberechnung.

## Gepruefte Primaerquellen
- https://docs.comfy.org/development/comfyui-server/comms_routes : /view, /upload/image, /object_info, /system_stats und /ws.
- https://docs.comfy.org/development/comfyui-server/comms_messages : Fortschrittsereignisse gelten fuer meldende Nodes; keine pauschalen Gesamtprozente erfinden.
- https://docs.comfy.org/tutorials/basic/inpaint : Masken/Inpainting-Eignung.
- Lokal ComfyUI\server.py:952-995 bestaetigt atomaren Prompt-ID-Abbruch; kein globaler /interrupt-Fallback vorgesehen.

## Inventarzusatz Phase1
Alle30 im Reparaturinventar18.10. katalogisierten Modellpfade wurden am20.10 auf Existenz und positive Dateigroesse geprueft; keine Gewichte geladen/erneut gehasht. LoRA-Dateien existieren, aber keine der sechs aktiven Vorlagen verwendet einen LoRA-Loader. Keine pauschale Adapterauswahl fuer inkompatible Familien hinzufuegen. Historische P2-Vorschlagsfehler vom15.10 sind laut Bericht18.10 bereits korrigiert.

## Phase4: festgelegte additive Schnittstellen
VersionStore(paths,files): create_project(request_id,original_media_id,name=''), list_projects(), get_project(project_id), get_version(version_id), prepare_input(version_id), validate_job_context(project_id,parent_version_id,workflow_id,images), record_job_outputs(job). Kein Modell-/Dienststart.
API: GET/POST /api/image-projects; GET /api/image-projects/{id}; GET /api/image-versions/{id}; POST /api/image-versions/{id}/input. POST /api/jobs erhaelt optionale gemeinsame project_id/parent_version_id, bestehende Clients bleiben gueltig.
Zwei neue Tabellen, FK-/Projektgrenzen, genau ein Original, eindeutige job_id+source_media_id. Statische Bildversionen (PNG/JPEG/WebP), Video/GIF bleiben im vorhandenen Ergebnisverlauf. Bei vorhandenen Ergebnisdateien erst unveraenderliche Kopie, dann Medienbeleg, dann kurzer Versionstransaktionsblock. Deterministische IDs/Namen und Hashvergleich erlauben Wiederaufnahme ohne Ueberschreiben fremder Dateien. Keine behauptete gemeinsame Transaktion ueber die getrennten SQLite-Verbindungen von FileStore/JobService.
prepare_input kopiert nur nach Benutzeraktion die gewaehlte Version in Input; validate_job_context prueft Projekt, Elternversion und Inhalt der primaeren Eingaberolle (Kontext/KREA/WAN image, ReActor target). Fehlerhafte Jobs erzeugen keine neue Version. Abgeschlossene Jobs duerfen fehlende Versionsbelege nachholen, ohne Berechnung zu wiederholen; versioning_error separat zeigen.

## Phase2: automatisierte Paketabnahme
- Starter22/22, bestehende Tool-Node18/18, Frontend33/33 bestanden. Backend Job/API/Server29/29 bestanden; danach gezielte korrigierte Ergebnis-Wiederherstellung2/2 bestanden.
- Unabhaengige Codepruefung: Teilimportbefund behoben, keine weiteren belastbaren Befunde. urllib-Redirects im Guard gesperrt und gezielt rot/gruen nachgewiesen.
- Live-read-only Status vom20.10: ownership=free,pid=null,ready=false,Port8188frei. Keine Dienste oder Modelle gestartet.
- Echte Bildberechnung/Browserabnahme noch offen und fuer Phase9 vorzusehen. Der automatische Test beweist Schnittstellenverhalten, keine allgemeine Bildqualitaet.
- Vor Phase3 UI-Quellenstand separat unter phase2-ui-baseline gesichert. Phase3 ist Einfach/Experte+DragDrop+kontextbezogene Anzeigen; Versionierung folgt danach.

## Phase3: UI-Abnahme
- Einfach/Experte, Drag&Drop und lokale Uploadfehler umgesetzt; Bericht phase3-ui-bericht.md. Ganze Frontendsuite41/41 bestanden.
- Isolierter Browserdienst auf8767, temporaere DB und winzige synthetische Modell-/Bildfixtures. Keine echten Dienste/Modelle. Eingabetext beim Wechsel Einfach -> Experte -> Einfach erhalten; technische Felder nur in Experte sichtbar. Sichtbarer Screenshot phase3-einfach.jpg.
- Testdienst nach Pruefung ueber seinen eigenen Stopendpunkt beendet; submissions=0. Browser-/GPU-Abnahme der spaeteren Versionshistorie noch offen.

## Phase4: Integration (laufend)
- JobService optional versions= erweitert; projekt/parent werden vor Berechnung validiert. Tatsaechliche Modellkomponenten und Graph bleiben im Jobbeleg. Abgeschlossene Bilder bekommen Versionsbelege; Metadatenfehler erhalten completed und versioning_error statt neu zu berechnen.
- Neue lokale GET/POST Schnittstellen image-projects und image-versions/input im bestehenden aiohttp-Server mit denselben Origin-/Aktionsschutzregeln. Keine Loeschroute.
- Gezielte Integrationstests: phase4-jobs-red/green (2), phase4-routes-red/green (2). VersionStore und Frontend sind noch in Implementierung; noch kein vollstaendiger Phase4-Nachweis.
- Eigenstaendiger Dienstverwaltungsnachtrag: alter Stopper hatte keine sichere Eigentuemerquittung. Agent launcher_audit ergaenzt separates PID+CreationFILETIME-Receipt und denselben Handle fuer Identitaetspruefung/Stop. Nur synthetische Tests, keine tatsaechlichen Dienste gestoppt.

## Zwischencommit und Phase4-Abnahme (teilweise)
- Ausdruecklicher Nutzerauftrag commiten: lokaler WIP-Commit dfaf115e90256b0d0a91d21ba3133e21350ce6fa,48Quelldateien; keinPush, keine Modelle/Benutzerdaten/altenBerichtsloeschungen aufgenommen. Erforderliche vorherige UI-/Ollama-/KREA-Quelldateien als Abhaengigkeiten gemeinsam gesichert.
- Vollstaendige Backend-Suite zum Zwischencommit206TestsOK. Starter34/34OK. Frontend zu diesem WIP43/47 mitvieroffenenPhase4Tests; danach Anbindungvollstaendig, Frontend52/52OK.
- Neue echte Schichtenintegration mit simuliertemCompute:2TestsOK (Original/2Edits/Zweig/Neuladen; Speicherfehler und GET-Reparatur bei1Submit).
- Browser: Original geladen, erste und zweite Bearbeitung einzeln gestartet; Seite neu geladen, Projekt erneut geoeffnet, Variante ausVersion1 ausgewaehlt und separat gestartet. VierVersionskarten mit korrektemOriginal/Version1/Version2/Version3 und zweiKindernvonVersion1 sichtbar. Kein Browserfehler. Testdienststopbestaetigung3synthetischeSubmissions. Belege phase4-browser-proof.json und phase4-vier-versionen.jpg. KeineechteBildqualitaetsabnahme.
- UnabhaengigerReview fand fehlendenCompleted-MetadataRetry im UI (behoben) sowie Raw-Datei-Abhaengigkeit bestehenderSnapshots und nichtidempotenteEingabekopiebeiLinkcrash (Versionsautor behebt, Tests laufen). Phase4 erstnachdiesenFixesfertig.
