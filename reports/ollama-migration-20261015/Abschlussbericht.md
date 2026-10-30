# MORPH: Ollama-Umstellung abgeschlossen

Stand: 15.10.2026. Aktives Projekt: `E:\MORPH-Studio`. Die vorhandene Oberfläche wurde technisch auf Ollama umgestellt; eine neue Oberflächengestaltung war nicht Teil dieses Schritts.

## Ergebnis

Die bestehende MORPH-Oberfläche unter http://127.0.0.1:8765 verwendet jetzt `OllamaProvider` und den lokalen Ollama-Dienst unter http://127.0.0.1:11434. Live geprüft: Ollama 0.40.4, vier installierte Sprachmodelle, kein geladenes Modell, fünf verfügbare integrierte Workflows ohne gemeldete Dateiprobleme. Der überprüfte Oberflächendienst läuft mit PID 24376 aus der vorhandenen projektlokalen Python-Laufzeit.

Der Startpunkt bleibt `E:\MORPH-Studio\MORPH-Oberflaeche.cmd`. Ein bereits geöffnetes Browserfenster bitte neu laden. Dann Modellliste aktualisieren, ein lokales Modell auswählen und bei Bedarf ausdrücklich laden. Auswahl, Laden, Vorschlag und Bild-/Videoberechnung bleiben getrennte Aktionen. Die bisherige LM-Studio-Modellwahl wurde zurückgesetzt.

## Änderungen

- Neuer nativer Adapter `ui/morph_ui/providers/ollama.py`: installierte/geladene Modelle über `/api/tags` und `/api/ps`; Fähigkeiten und lokale Verfügbarkeit über `/api/show`; ausdrückliches Laden/Freigeben über `/api/generate`; strukturierte Vorschläge über `/api/chat`.
- Aktiver Einstieg `ui/morph_ui/__main__.py` lädt den Ollama-Adapter. Standardkonfiguration und Verbindungshinweise verwenden Port 11434. Fehler benennen den tatsächlich verwendeten Dienst; der aufbewahrte alte LM-Studio-Adapter behält seinen eigenen Dienstnamen.
- Vorschläge verwenden ein JSON-Schema, ausgeschaltete Denk-Ausgabe, 4.096 Kontexttokens und höchstens 1.024 neue Tokens. Ergebnisse werden zusätzlich lokal gegen die aktuellen Workflow-Einstellungen geprüft. Manuelle Bildmodellfelder, zusätzliche Befehlsfelder, ungültige Werte und unvollständige Antworten werden abgewiesen. Keine automatische Wiederholung, keine freie Werkzeugausführung, kein Download.
- Sichere Verbindungsmigration in `ui/morph_ui/settings.py`: ursprüngliche Konfiguration bytegenau gesichert, danach atomar auf Ollama umgestellt. LM-Studio-Modellkennungen und geschützter Zugangsschlüssel werden nicht an Ollama weitergegeben. Erneute Starts erhalten die Ollama-Konfiguration; ein Serverwechsel leert alte Modellkennungen.
- README und Bedienung aktualisiert. Die bisherigen LM-Studio-Anleitungen sind als historischer Bedienweg gekennzeichnet; Ergebnisnachweise bleiben erhalten.

Exakte Sicherung der vorherigen Einstellungen: `E:\MORPH-Studio\user\morph-ui\settings-lmstudio-backup-c01dce3fbee84463b56a1b7c0bc0d804.json`. Bytegleichheit mit der vor Arbeitsbeginn gesicherten Konfiguration ist bestätigt. Eine reine Änderung der alten Einstellungen reicht zur Rückkehr zum früheren Adapter nicht; die vorherigen Anwendungsdateien liegen zusätzlich unter `before/`. Diese Sicherungen bleiben lokal und werden durch die `.gitignore` dieses Berichtsordners von Git ausgeschlossen.

## Erhaltene Bestandteile und Altanbindung

Alle 18 ursprünglichen Workflows sind einschließlich SHA-256 unverändert. Alle 36 ursprünglichen Eingabe-, 56 Ausgabe- und 75 Modelldateien stimmen in Pfad, Größe und Änderungszeit mit der Bestandsaufnahme überein. Große Modelle wurden nicht erneut vollständig gehasht. Die vorhandenen Laufzeiten, Pakete, Bildmodelle und ComfyUI-Dateien wurden nicht verändert, installiert, entfernt oder aktualisiert.

Die vorhandenen `LMStudio-*.json` sind ComfyUI-Graphen und werden weiterhin vom Workflowkatalog verwendet. Ihre Namen begründen keine LM-Studio-Laufzeitabhängigkeit. Ebenso bleibt `tools/lmstudio-wan-chat/start_mcp.py` erhalten: `ui/morph_ui/comfy.py` verwendet diesen providerunabhängigen Startschutz. Der generische MCP-Unterbau und bestehende Tests bleiben erhalten. Das alte native LM-Studio-Plugin, dessen SDK und Einrichtungsskripte sind für die neue Oberfläche inaktiv, werden wegen historischer Nutzung und geteilter Dateien aber nicht pauschal gelöscht. Globale LM-Studio-Installation und andere Projekte bleiben unverändert.

Während der Arbeit kamen die beiden vom Nutzer genannten JSON-Workflows und eine VAE-Datei hinzu. Keine dieser neuen Dateien wurde von der Umstellung verändert. Keine bestehenden Nutzerdaten wurden gelöscht. Es wurden keine Dateien gestagt oder committet und keine alten Git-Löschungen rückgängig gemacht.

## Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Ausgangsstand vor Änderungen | 89 Python-Tests, 14 Node-Tests bestanden |
| Abschließende UI-Python-Suite | 127 Tests bestanden, `python-final.log` |
| Abschließende Frontend-Suite | 14 Tests bestanden, `node-final.log` |
| Native HTTP-Protokollkette | Isolierter Testdienst prüft Auflisten, Laden, Vorschlag, Speichern der Modellwahl und Freigeben; ComfyUI-Startzähler bleibt 0 |
| Verbindungsmigration | Exakte Sicherung, Fehlererhaltung, Geheimnisschutz und wiederholbarer Start geprüft |
| Workflow-Dateiprüfung | Fünf integrierte Workflows, keine Dateiprobleme; keine Berechnung |
| Unabhängige Codeprüfung | Keine offenen blockierenden Befunde, `Codepruefung.md` |
| Live-Verbindung nach Aktivierung | Oberfläche meldet `provider=ollama`, vier Modelle, keine geladen; `live-verification.json` |
| Erhaltungsprüfung | Alle ursprünglichen geschützten Dateien unverändert, Details in `live-verification.json` |

Ein vorhandener Test erwartete zunächst noch die alte Standardadresse auf Port 1234. Seine Schutzprüfung blieb funktional; der Test vergleicht jetzt den vollständigen Einstellungszustand vor und nach fremden Anfragen. Der erste Gesamtlauf mit 126/127 bestandenen Tests liegt unter `python-before-default-test-update.log`; der korrigierte Gesamtlauf besteht vollständig. Weitere Tests wurden nicht entfernt oder abgeschwächt.

Bei der sicheren Dienstaktivierung verhinderte zunächst ein Typvergleich von Zeitstempeln den Neustart: PowerShell hatte den JSON-Zeitstempel bereits als Datum eingelesen. Zu diesem Zeitpunkt war noch kein Prozess gestoppt. Nach Prüfung identischer UTC-Zeitpunkte wurde der Vorgang mit Datumsvergleich fortgesetzt. Ausschließlich der anhand von Port, Prozesspfad, vollständigen Argumenten, Startbeleg und Projektstatus zugeordnete Oberflächendienst wurde neu gestartet. Keine aktiven/unklaren UI-Aufträge lagen vor. Ollama wurde nicht neu gestartet; ComfyUI wurde nicht gestartet oder gestoppt.

## Grenzen und neue Workflow-Dateien

Ein echtes Sprachmodell wurde in dieser Umstellung weder geladen noch zur Generierung aufgerufen. Das Lade-/Entlade-/Vorschlagsverhalten ist mit Testdiensten technisch geprüft; Modellqualität und die erfolgreiche Verarbeitung eines realen Modellvorschlags sind nicht nachgewiesen. Es gab keinen neuen Bild-/Videoauftrag. ComfyUI war bei der Live-Prüfung nicht gestartet; sein Server-Handshake wurde deshalb nicht neu getestet. Der automatische Startschutz blieb unverändert und wurde nicht als neuer echter Start ausgegeben.

Die Dateien `workflows/flux2Klein9bUncensoredImageEdit_v10.json` und `workflows/firered-image-edit-1.1.json` liegen richtig. Sie sind zusätzliche ComfyUI-Workflows; die einfache MORPH-Auswahl enthält weiterhin ihre fünf bisherigen integrierten Workflows. Die neuen Workflows wurden nur gelesen, nicht integriert oder ausgeführt.

`flux2-vae.safetensors` liegt derzeit unter `ComfyUI_windows_portable/ComfyUI/models/diffusion_models/`; sein Header und der Flux-Workflow bestätigen eine VAE. Richtiger Zielordner ist `ComfyUI_windows_portable/ComfyUI/models/vae/`. Die Datei wurde weder verschoben noch überschrieben. Bildmodell, Textencoder und gegebenenfalls LoRA sind separat erforderlich. Ein vollständiger Download aller neuen Workflow-Abhängigkeiten wurde nicht behauptet.

## Primärquellen

- [Ollama: Chat und strukturierte Ausgaben](https://docs.ollama.com/api/chat)
- [Ollama: installierte Modelle](https://docs.ollama.com/api/tags), [geladene Modelle](https://docs.ollama.com/api/ps), [Laden/Freigeben über Generate](https://docs.ollama.com/api/generate)
- [ComfyUI: FLUX.2 Klein, Modellordner und Zusatzdateien](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [Civitai-Originaleintrag des konkreten Flux-Workflows](https://civitai.com/models/2845550) – API meldet Typ Workflows und die Datei `flux2Klein9bUncensoredImageEdit_v10.json`.
