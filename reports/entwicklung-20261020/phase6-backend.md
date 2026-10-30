# Phase 6: modellbezogene Vorschlagskontexte

Stand: 20.10.2026. Lokale Backendentwicklung mit synthetischen Modellheadern und Offline-Providerantworten. Kein Sprach-/Bildmodell geladen oder ausgeführt, kein produktiver Dienst gestartet oder verändert, kein Commit.

## Änderung und Grenzen

`Catalog.prompt_profile()` liefert eine kurze feste Formulierung aus der bestätigten Familie des gewählten Bildmodells. Die bestehende Header-/Rollenprüfung von `ModelLibrary.resolve()` liest dafür Metadaten, keine Gewichte. Im selben Werkzeug „Bild erstellen“ unterscheidet sich die Empfehlung für SD 1.5 von SDXL. Dateinamen, Modellkennungen, Pfade und Modelloptionen werden nicht Teil des Profils. Eine fehlende oder unbestätigte Auswahl erhält ein neutrales Profil; sie wird nicht durch die Standardfamilie ersetzt.

`ToolPlanning` verwendet für das aktuelle Werkzeug die aktuelle manuelle Modellauswahl und für andere Werkzeuge deren gespeicherte Standardauswahl. Fehlende Bildmodelle verhindern den optionalen Werkzeugvorschlag nicht. Der Sprachmodellvorschlag erhält weiterhin keine Modellwahlbefugnis; Schema und Rückgabe schließen Modellfelder aus. Die validierten vollständigen Einstellungs-Snapshots für einzeln und in beliebiger Reihenfolge übernehmbare Karten bleiben unverändert.

Eine gemeinsame deutsche Regel verlangt ausschließlich die gewünschten Änderungen und den Erhalt nicht genannter Person, Gesicht, Pose, Haare und Hintergrund. Das ist eine Anweisung an den Assistenten, kein Nachweis seiner Befolgung oder der späteren Bildqualität.

Der native einzelne Ollama-Vorschlag erhält dasselbe Profil und dieselbe Erhaltungsregel. Sein Systemkontext enthält nur aktuelle Werte ohne Modellfelder; zuvor wurden dort vollständige Kontrollmetadaten einschließlich Modellpfaden/Optionen serialisiert. Die manuelle Auswahl bleibt intern für die anschließende Validierung erhalten. Eine vollständige Größenprüfung erfolgt vor jedem Providerzugriff. Der ältere einzelne LM-Studio-Pfad wurde nicht erweitert; beide Werkzeugplan-Provider verwenden die gemeinsame `ToolPlanning`-Änderung.

Das bestehende Limit bleibt 8.192 Bytes für die vollständige Anfrage nach `json.dumps()` einschließlich Schema und Nachrichten. Auftrag, aktueller Prompt und Negativtext werden vollständig übermittelt oder vor dem Providerzugriff abgelehnt. Es gibt kein Abschneiden und keinen automatischen Wiederholungsversuch. Nur redundante statische Planungstexte wurden gekürzt. Ollama bleibt bei `num_ctx=4096` und `num_predict=1024`; das Bytelimit ist keine modellspezifische Tokengarantie.

## Prüfungen

- Baseline: `phase6-backend-baseline/` enthält die drei bestehenden Implementierungsdateien und zwei bestehende Tests samt SHA256. Die bereits vorhandene Phase-5-Änderung in `catalog.py` wurde übernommen.
- `phase6-backend-red.log`: 7 neue Tests vor Implementierung; 8 fehlgeschlagene Unterfälle und 3 erwartete Fehler durch die noch fehlende Profil-API. Sichtbar fehlten ausgewählte Familie, Erhaltungsregel und native Größenablehnung.
- `phase6-backend-green.log`: dieselben 7 Tests bestanden. Unterfälle prüfen beide Werkzeugplan-Provider, aktuelle SD-1.5-Auswahl gegenüber SDXL-Default, andere Werkzeugdefaults, unbekannte/fehlende Modelle, pfadfreien Kontext und exakte 8.192-/8.193-Byte-Grenze beim nativen Einzelvorschlag vor jeglichem Provider-I/O.
- `phase6-proposals-regression.log`: 17 bestehende Tests bestanden, einschließlich 8.192-Byte-Grenze beider Werkzeugplan-Provider, vollständigem Text, Einzelübernahme-Snapshots, WAN-Kopplung und ausgeschlossenen Modelländerungen.
- `phase6-ollama-regression.log`: 20 bestehende Tests bestanden.
- `phase6-catalog-regression.log`: 6 bestehende Tests bestanden.
- `phase6-catalog-files-regression.log`: 8 bestehende Tests bestanden.
- `git diff --check` für die drei Implementierungsdateien: Exit 0; lediglich Git-Hinweise zur bestehenden Windows-Zeilenendenkonvertierung.

Damit sind 58 fokussierte Tests dieses Backendumfangs bestanden. Die übrigen Projektphasen und Frontendänderungen werden getrennt geprüft. Tests verwenden die projektinterne Python-Laufzeit mit `-B`; Testdaten liegen unter dem bestehenden Projekt-Tempbereich und werden bereinigt.

## Anfragegrößen

`phase6-request-sizes.json` und `.log` enthalten 30 Messungen aus `phase6_request_sizes.py`. Der Offline-Helfer liest die tatsächlich gespeicherten Workflowdefaults. Modellscan und Familienauflösung sind ausdrücklich deklarierte Fixtures für bekannte beziehungsweise unbestätigte Familien; kein aktueller Modellbestand oder Laufbetrieb wird damit bestätigt. Der Auftrag lautet vollständig „Bitte einen Vorschlag.“.

| Werkzeug | Ollama Werkzeugplan | LM Studio Werkzeugplan | Ollama Einzelvorschlag |
| --- | ---: | ---: | ---: |
| Bild erstellen / SDXL | 7.827 | 7.857 | 1.972 |
| Kontext bearbeiten | 7.759 | 7.789 | 1.848 |
| Gesichtstausch | 7.582 | 7.612 | 1.320 |
| Bild zu Video / WAN | 8.028 | 8.058 | 2.602 |
| Qwen Image 2.1 | 7.829 | 7.859 | 2.050 |
| KREA 2 | 7.790 | 7.820 | 1.994 |

Alle Angaben sind serialisierte Bytes einschließlich vollständiger Schema-/Nachrichtenstruktur. Bei den bekannten Familien verbleiben im größten Werkzeugplan 134 Bytes. Die zwölf weiteren Messungen mit unbestätigten Familien liegen ebenfalls unter dem Limit; ihr Maximum beträgt 8.095 Bytes (WAN / LM Studio), also 97 Bytes Reserve. Längere Aufträge oder vorhandene Texte können diese Reserve überschreiten und werden dann ausdrücklich abgelehnt. Die Messungen bestätigen die Größenbegrenzung für diese Defaults, keine allgemeine Promptlänge, Tokenzählung, Modellqualität oder Bildgenerierung.

## Dateiumfang

Geändert: `ui/morph_ui/catalog.py`, `ui/morph_ui/tool_planning.py`, `ui/morph_ui/providers/ollama.py`. Neuer Regressionstest: `ui/tests/test_prompt_profiles.py`. Bestehende Tests, Workflows, Modell-/Dienstkonfiguration und Laufzeitdateien wurden für diese Änderung nicht verändert.
