# MORPH Studio Phase 5 bis 9 – Umsetzung

Stand: 20.10.2026. Nachfolgechat 01a15a06-bd67-7d83-a3cc-6eaa8f6b203d. Verbindliche Spezifikation: Nutzerauftrag.md und CHAT-UEBERGABE-01a159c9.md im selben Verzeichnis. Bestehender Routineauftrag autorisiert Durchführung ohne erneute allgemeine Designfreigabe.

Ziel: Bestehende lokale Bildhistorie um Vergleich und bewusste Bereichsbearbeitung erweitern, danach optionale Ollama-Hilfe, Ressourcenanzeige und echten Knotenfortschritt vervollständigen. Keine neue Architektur, Abhängigkeit, Modelle oder Cloud. Bestehenden Checkout wegen laufzeitgebundener uncommitteter Abhängigkeiten und früherer Entscheidung behalten; dateiweise Baselines statt Reset/Worktree-Wechsel.

## Grenzen und Prüffokus

- Originale, Modelle, bestehende Aufträge, Fremdänderungen und Pause-Dateien erhalten. Quellen unter dem ChatGPT-Spiegel nicht bearbeiten.
- Kein automatisches Übernehmen/Berechnen. Keine globalen Interrupt-/Free-Aktionen gegen fremde Instanzen/Aufträge.
- Stale Uploads, Masken und Vorschläge dürfen keine neuere Bildauswahl überschreiben.
- Nach Speicherfehlern darf kein unvollständiger endgültiger Snapshot einen Wiederholungsversuch blockieren.
- Unterschiedliche Bildgrößen und EXIF-Ausrichtung explizit behandeln; Bereichskopie ist kein natives Inpainting.
- Fortschritt nur prompt_id-gebunden, Prozent nur für den meldenden Knoten; unbekannte Ladezustände offen anzeigen.
- Echte GPU-/Prozessprüfungen vorher ankündigen, Ergebnisse getrennt von Simulationen und Bildqualität bewerten.

## Aufgaben und Zuständigkeiten

### 0 – Phase 4 schließen (Root + unabhängiger Reviewer)

- [x] Letzten Diff und vorhandene 24/4-Grünlogs unabhängig lesen. Zwei ursprüngliche Recoverybefunde behoben.
- [x] Neuer Befund: Direktes Schreiben der stabilen Eingabekopie kann bei Schreibfehler Teilkopie blockierend hinterlassen. Mit Schreibfehler reproduziert (phase4-publish-red.log), .part/flush/fsync/exklusives Windows-rename ergänzt.
- [x] test_versions.py 17/17 grün (phase4-publish-green.log).
- [x] Re-Review bestätigt Fix und 17/17, keine weiteren konkreten Blocker. Phase 5 zur Implementierung freigegeben.

### 1 – Phase 5: Vergleich und Bereichsmaske

Frontend (Agent compare_ui): neue comparison.js/regions.js im bestehenden Frontend, index.html/styles.css/app.js/results.js anbinden. Beliebige zwei Versionen, Original/Elternversion, gemeinsamer Zoom/Pan und Reset; Vergleich ändert keine Eingabe. Maske schwarz/weiß als PNG über bestehende Uploadroute. Pinsel/Radierer/Leeren, explizit übernehmen oder verwerfen; ungesicherte Maske verhindert unbeabsichtigte Vollbildbearbeitung. Asynchrone Antworten an Quelle/Workflow/Elternversion binden. Fokussierte Verhaltenstests vor Implementierung und Node-Regressionssuite danach.

Backend (Agent region_backend): edit_region optional im Job-POST mit mask_media_id, source_media_id, parent_version_id. Nur versionierte Kontext/KREA-Jobs, Quell- und Elternbindung, PNG-Graumaske nicht leer/transparent, gleiche orientierte Maße. Masken-/Quellhash und verwendete Maße einfrieren. LoadImageMask(red) und ImageCompositeMasked(destination=Original, source=generiert, resize_source=true) vor SaveImage einfügen; benötigte Knoten per object_info prüfen. Bestehenden Sampler/Modelle nicht verändern. Metadaten in VersionStore erhalten. Negative Grenztests und Graph-/HTTP-/Jobs-Integration gezielt prüfen.

Bewertung: Die vorhandenen Edit-Modelle sehen weiterhin das gesamte Bild. Die Komposition übernimmt generierte Inhalte nur in markierten Bereichen auf dem ursprünglichen Bildraster. Keine behauptete semantische Inpainting-Unterstützung oder Garantie innerhalb der Markierung. Native VAEEncodeForInpaint/SetLatentNoiseMask sind vorhanden, aber für diese KREA-Spezialkonditionierung nicht nachgewiesen. Keine neuen Modelle herunterladen.

Root: unabhängiger Review, isolierter Browsernachweis mit simuliertem Compute; Browser- und GPU-Abnahme getrennt halten. Baseline vor Paket und Bericht danach.

### 2 – Phase 6: optionale Ollama-Hilfe

Bestehende providers/ollama.py, tool_planning.py und proposals.js anhand aktueller Tests prüfen. api/ps versus tags bereits getrennt; Originalprompt/Einzelübernahme/kein AutoCompute erhalten. Nur tatsächliche Lücken ändern, insbesondere minimale Änderungen und erhaltende Bildbereiche im Vorschlagsauftrag. Keine erneute Migration oder Modellvergleichsserie. Ausfall darf Start normaler Bildjobs nicht verhindern.

### 3 – Phase 7: Modell-/Ressourcenverwaltung

Bestehende ModelLibrary-Zuordnung und Laufzeitknoten nutzen. system_stats Gerätewerte defensiv auswerten, Modellnamen nicht aus zuletzt benutzt als geladen ableiten. Bewusstes Entladen nur auf API-bestätigt eigener verwalteter Instanz und bei leerer Backendqueue/keinem aktiven oder ungeklärten MORPH-Auftrag, unter bestehendem Joblock. Bei ungeklärter Eigentümerschaft gesperrt. Tests für Fremd-/Adopted-/Busy-Sperren und reale Statusdaten, keine zusätzliche parallele VRAM-Belegung.

### 4 – Phase 8: Fortschritt

Comfy-WebSocket vor Submit verbinden, client_id eindeutig pro Verbindung; nur eigene prompt_id-gebundene Ereignisse übernehmen. Reconnect begrenzt und ohne Resubmit; fehlender Socket lässt queue/history-Polling bestehen. Node value/max als Knotenschritte, keine Gesamtprozent/erfundenen Ladezeiten. Jobdaten persistent, Runtimeinformationen nicht als Abschlussbeleg verwenden. Gezielte Tests für fremde Ereignisse, Unterbrechung, gecachte Nodes, gerichteten Cancel.

### 5 – Phase 9: Integration und reale Abnahme

Nach jeder Phase konkrete Checks lesen und dokumentieren, danach eine angemessene Gesamtsuite. Mit aktuellen Port-/Queue-/VRAM-/Modellvoraussetzungen angekündigte reale Start/adopt/Compute/Versionen/Kleidungswechsel/Vergleich/Cancel-Abnahme durchführen. So wenig neue Berechnungen wie für offene Kriterien nötig; keinen Testmarathon. Originale privat/lokal, keine Uploads. Fehler vollständig bewahren. Start-, Versionen-, Sicherungsanleitung und geänderte Dateien im Abschlussbericht ergänzen. Keine pauschalen Git-Staging-/Commit-/Push-Aktionen.

## Fortschrittsprotokoll

20.10.2026: Übergabestatus des Ursprungs bestätigt handoff_complete; dieser Chat ist einziger Nachfolger. Phase4-Publishfix 17/17 Tests grün, Re-Review zu diesem Zeitpunkt offen. Erster Portcheck wegen PowerShell-Ausgabeformat nicht eindeutig; keine Abwesenheit von Ollama daraus ableiten. E: ca. 65,6 GB frei. Keine Dienste oder Modelle gestartet. Drei Subagenten mit getrennten Aufgaben, Phase5 zunächst lesend bis Reviewfreigabe.

Nachtrag: Phase4 unabhängiger Re-Review PASS. Phase5 Implementierung gestartet (Frontend/Backend getrennt), zusätzlicher Geometriebefund berücksichtigt: KREA-Referenzfit und spätere Komposition benötigen übereinstimmende Seitenverhältnisse. Phase6 vorerst lesende Bestandsprüfung durch Reviewer, keine Implementierung vor Phase5-Abnahme.

Aktueller separater Ressourcencheck: NVIDIA RTX4080,16376MiB Gesamt,2108MiB benutzt,13941MiB frei,3% Auslastung. Listener11434 PID5740 (vorhandenes Ollama), kein Listener8188/8765/8767 im selben Check. Kein Prozess verändert. Dies sind Momentaufnahmen vor späterer echter Abnahme.

Phase5 geschlossen im synthetisch geprüften Umfang: neue Backendfälle13grün plus1Source-Racegrün,58angrenzendeRegressionen. Review fand fehlende effektiveAlpha-Prüfung; root3Regressionen rotnachgewiesen, Quelle/Maske einschließlichPNG-tRNS korrigiert, vollständigeaktuelleBereichssuite17/17grün48.349s, unabhängigerRe-Review freigegeben. Frontend62/62grün, unabhängigkeineP1/P2; kleinerGeometriehinweisnunerstbeiaktiverMarkierung/Receipt,8gezielteControllertestsnachgeprüft. IsolierterBrowser1expliziterSubmit/5Versionen/Reload/keineFehler; Dienstgestopptsession45707exit0,Tabgeschlossen. Details phase5-browser.md,phase5-ui-report.md,phase5-backend.md. EchteGPU-BildabnahmeoffeninPhase9.

Phase6-Entscheidung: Originalauftrag+ursprünglicheFormularwerteunveränderlichimVorschlagsbeleganzeigen, tatsächlicheÄnderungenvor/nachÜbernahmeerhalten; pathfreieModellfamilienprofileundkompakteMinimaländerungsregelergänzen. 8192ByteRequestgrenzebleibt; keineEingabenabschneiden. NativeOllama-Einzelvorschläge dürfenkeineModellpfade/-optionenimPayloadweiterreichen. BestehendeLade-/Übernahme-/Offlineverträgeerhalten. KeineerneuteMigration.

Neue verbindliche Nutzeranweisung: Nach jedem erfolgreich geprüften Arbeitsblock committen. Am20.10 deshalb abgeschlossene Pakete gezielt getrennt nachgesichert: d6477456dc054c3436a6af00f32c61e2d5406b98(Phase4),316f570c50508e44590f6b5a5250954ba2c76d1b(Phase5),ad4551d(Phase6). Zwischenstände über die vorliegenden getesteten Baselines im Index getrennt, Arbeitsdateien dabei nicht zurückgeschrieben; Fremdänderungen/Pause/Modelle/Benutzerdaten nicht gestagt. KeinPush,keinRemote. Index danach leer; unter ui/ nur die bereits fremden alten Berichts-/Preflightlöschungen offen.

Phase6 abgeschlossen: Backend58/58gezielt,Frontend65/65grün, unabhängige Backend-/Frontendreviews ohne konkrete P1/P2. 30Offlinepayloads mit tatsächlichen Workflowdefaults geprüft, Maximum8095/8192Byte (97ByteReserve); keine Eingaben abgeschnitten. Längere Eingaben werden erklärt abgewiesen. Originalauftrag/-formular und Vorher/Nachher-Beleg vor HTTP eingefroren und nach Übernahmen erhalten. Keine echte Sprachmodellanfrage. Bestehende konfigurierte Auswahl qwen3.5-abliterated:9b bleibt erhalten; gespeicherte Instanzkennung ist kein Ladebeweis, api/ps meldete leer.

Nutzerfrage nach dem bisherigen Funktionsblocker beantwortet: Zu enge Prozess-/Argumenterkennung statt kompatibler API-Übernahme plus verdeckte Fehlerdetails am besten belegt. Historischer exakter abweichender Parameter bleibt unbekannt, Schreibweise --port=8188 ist gezielt belegter Parserfehler. Echten Start/Bildauftrag erst in Phase9 prüfen. Aktuell direkt nachgelesener Originalbeleg liegt tatsächlich unter E:\MORPH-Studio\reports\wan-lmstudio\mcp-comfy-start.log:476–478 und506 (Ablehnungen PID135940/PID15608), nicht unter dem im alten Bericht verkürzt erwähnten logs/-Pfad. Keine neue Diagnose oder Modellläufe daraus abgeleitet.

Phase7 freigegeben und in Umsetzung: Agent resource_backend arbeitet nur Guard/Comfy/Jobs/Server/Ressourcenparser+Tests, resource_ui nur Frontend. Beide legen eigene aktuelle Baselines mit HEADad4551d an. Phase8 durch progress_backend nur lesend vorbereitet, noch keine Implementierungsfreigabe; Entwurf umfasst eindeutige persistente client_id, WS vor Submit, explizite Prompt-/Graphbindung, nur Knotenschritte, Polling als Abschlussautorität und verlustfreien Ereignismerge. Phase9 und echte Tests weiterhin offen. Derzeit kein eigener Fixture-/Produktivdienst bekannt aktiv; letzter Fixturestopp bestätigt.

Phase7 inzwischen abgeschlossen und committed1ad7201c2ad619960aa35d96f5226ef0597dbaef: Backend15/15,Guard4/4,alteStart/Stop34/34,angrenzend46/46,Frontend78/78grün. 13getesteteDateihashes vorCommit aktuell identisch. Unabhängige Reviews ohne offeneP1/P2 nach Listenerwechselkorrektur. Browserphase6/7 kombiniert mit1simuliertemVorschlag/1simulierterFreigabe/0Bildsubmissions,OriginalnachÜbernahmeerhalten,StatusausfallsperrtBildstartnicht; siehephase7-browser.md. Fixture53212exit0,Tabgeschlossen. Phase8 nun zurUmsetzungfreigegeben:progress_backendBackend,progress_uiFrontend, jeweilsBaselinesvonHEAD1ad7201. Phase9weiterhinnichtausgeführt, vorbereiteteAnweisunginPhase9-Echte-Abnahme-Anweisung.md. BisherkeineechtenModellaufrufe/Dienststarts/-stoppsinNachfolgechat.

Übergabenachtrag 20.10.2026: Phase8 abgeschlossen, unabhängig geprüft und als 24b02f9a41f706fb6e47f14bfd17d59827121275 committed. Backend12/12 und angrenzend56/56, Frontend90/90 PASS; keine echte Modell-/GPU-Abnahme. Danach nur lesend --check Exit0, keine Listener8188/8765/8767, Ollama11434 PID5740 mit api/ps models=[], RTX4080 2241/16376MiB belegt. Neue QA-Lücke: Sprachmodellaktionen umgehen bisher Joblock/Bildstart-Gates; residente LLM-/Comfy-Belegung wird noch nicht gegenseitig kontrolliert. Lesender Audit empfiehlt gemeinsamen Lock plus positiv belegte GPU-Residenz mit bewusster manueller Freigabe; keine Implementierung begonnen. Vor realer Abnahme gezielt schließen und committen. Phase9-Harness fertig vorbereitet, nur compile/help geprüft, Root-Review offen; keine Liveaktion. Die erste Komprimierung dieses Hauptchats wurde bestätigt. Vollständiger Wechselbericht CHAT-UEBERGABE-01a15a06.md und Status reports/uebergaben/01a15a06-bd67-7d83-a3cc-6eaa8f6b203d.json haben für aktuelle Arbeitsanweisung Vorrang. Keine Pause. Facharbeit endet hier und wird nur im genau einen Nachfolger fortgesetzt.
