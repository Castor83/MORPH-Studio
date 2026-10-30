# MORPH: Umstellung auf Ollama

Auftrag vom 15.10.2026: Die vorhandene lokale MORPH-Oberfläche verwendet Ollama für Sprachmodell-Vorschläge. Das Oberflächendesign kommt auf Nutzerwunsch später.

## Umfang

- Aktives Projekt: `E:\MORPH-Studio`; vorhandene Änderungen bleiben erhalten. Kein Git-Reset, Staging oder Commit.
- Native Ollama-Endpunkte für installierte/geladene Modelle, ausdrückliches Laden/Freigeben und strukturierte Vorschläge.
- Nur lokale Modelle und lokale HTTP-Verbindungen; kein Download und keine freie Werkzeugausführung durch das Sprachmodell.
- Vorschläge werden vor Übernahme geprüft. Ein Vorschlag reicht keinen Bild-/Videoauftrag ein und verändert keine manuelle Bildmodell-Auswahl.
- Bisherige Verbindungseinstellungen werden vor der Umstellung exakt gesichert. Alte Kennungen und Zugangsschlüssel werden nicht an Ollama weitergegeben.
- ComfyUI, Bildmodelle, 18 Workflows, Eingaben, Ausgaben und vorhandene Tests bleiben erhalten. Der gemeinsame Startwrapper im historischen LM-Studio-Ordner bleibt erforderlich.

## Arbeitsschritte

1. Bestandsprüfung und Sicherung: erledigt. Baseline: 89 Python- und 14 Node-Tests bestanden.
2. Erledigt: Ollama-Adapter und Tests; sichere Verbindungsmigration; aktive Einbindung und Hinweistexte.
3. Erledigt: Unabhängige Codeprüfung ohne offene Blocker; 127 Python- und 14 Node-Tests bestanden.
4. Erledigt: Aktive Oberfläche meldet Ollama, vier Modelle und null geladene Modelle. Originaldateien unverändert.
5. Erledigt: Bedienung aktualisiert; Abschlussbericht.md enthält Nachweise und Grenzen.

## Prüfgrenzen

Die Live-Prüfung umfasst Verbindung, Modellliste, geladenen Zustand und Konfiguration. Sie lädt kein Modell, erzeugt keinen Sprachmodell-Vorschlag und startet keine Bild-/Videoberechnung. Generierungs-/Ladeverhalten wird mit isolierten Testdiensten geprüft. Die Funktion an einem echten Sprachmodell wird damit nicht als getestet ausgegeben.

Die ursprüngliche Konfiguration und die geschützte Dateiübersicht liegen lokal unter `before/` und `baseline.json`; diese Sicherungsdaten sind in diesem Berichtsordner von Git ausgeschlossen.
