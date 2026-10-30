# Gezielte Reparatur der Werkzeugvorschläge

Stand: 18.10.2026. Ausschließlich Offline-Fixtures und lokale Dateien; keine Modellvorhersage, kein Download und kein Dienststart.

## Ursache und Änderung

- Die Oberfläche mischt beim Annehmen einer Karte deren Einstellungen in das aktuelle Formular. Das Backend prüfte dagegen jede Karte auf Basis des ursprünglichen Formulars beziehungsweise der Werkzeugdefaults. Bei WAN konnten so zwei einzeln gültige Karten nacheinander einen ungültigen Zustand herstellen: ursprünglich steps=6/split=2, danach steps=4, danach split=5.
- Das Backend gibt jetzt für jede Karte den vollständig geprüften Satz aller Nicht-Modell-Einstellungen zurück. Jede Karte ist einzeln und in beliebiger Reihenfolge annehmbar. Die vorhandene manuelle Bildmodellauswahl wird weiterhin nicht an das Sprachmodell gesendet oder durch eine Karte ersetzt. Jede Karte bleibt eine getrennte manuelle Übernahme; kein Bildtransfer und kein Rechenstart.
- Vor jedem Zugriff auf Ollama beziehungsweise den erhaltenen LM-Studio-Adapter wird die vollständig serialisierte Vorschlagsanfrage geprüft: Schema, Systemtext, Auftrag, aktuelle Texte, Modellkennung und alle sonstigen Payload-Felder zusammen höchstens 8.192 Bytes. Die Messung entspricht der Standard-JSON-Serialisierung des vorhandenen HTTP-Adapters. Größere Anfragen werden verständlich abgelehnt, ohne Kürzung oder Provideraufruf.
- Wiederholte Katalogmetadaten wurden kompakter dargestellt. Alle sechs Werkzeugnamen, Beschreibungen, Bildrollen, Typen, Grenzen und Schrittweiten bleiben enthalten. Standard-Negativtexte anderer Werkzeuge müssen nicht mehrfach im Katalog stehen; der tatsächliche aktuelle Text bleibt vollständig erhalten.

Das Byte-Arbeitslimit ist keine modellspezifische Tokenzählung und garantiert allein keine vollständige 4K-Kontextabdeckung. Ollama num_ctx=4096 und num_predict=1024 bleiben unverändert. Die alte, von der aktuellen Werkzeugvorschlagsoberfläche nicht verwendete propose-Methode wurde nicht geändert.

## Geänderte Dateien

- ui/morph_ui/tool_planning.py
- ui/morph_ui/providers/ollama.py: ausschließlich propose_tools
- ui/morph_ui/providers/lmstudio.py: ausschließlich propose_tools
- ui/tests/test_tool_proposals.py

## Prüfung und Grenzen

- RED vor Implementierung: WAN-Snapshot fehlte (4/None statt 4/2); kombinierte große Texte wurden nicht vor dem Provider abgewiesen. Anschließend beide Regressionen GREEN.
- test_tool_proposals: 17/17 bestanden in 11,354 Sekunden. Beleg: proposal-tests.log.
- Angrenzende Ollama-/LM-Studio-Providerfixtures: 30/30 bestanden in 3,096 Sekunden. Beleg: proposal-provider-tests.log.
- Exakte Request-Grenze bei beiden Providern: 8.192 Bytes akzeptiert, 8.193 Bytes abgewiesen; der übergebene Auftrag und aktuelle Texte bleiben unverändert. Schema wird im Grenztest mitgezählt.
- Tatsächliche Workflowdefaults aller sechs Werkzeuge mit Offline-Providern passen: 7.317 bis 7.793 Bytes inklusive kurzem Auftrag. Beleg: proposal-request-sizes.json. Dafür wurde nur die irrelevante Modelloptions-Inventarisierung im Audit ausgeblendet; Modellfelder gelangen ohnehin nicht in die Anfrage. Mit diesen Defaults verbleiben je nach Werkzeug/Provider rund 399 bis 875 zusätzliche ASCII-Bytes für Text; andere Modellkennungen und Texte verändern diesen Spielraum.
- Eine zunächst laufende wiederholte Inventarisierung für die Größenmessung wurde wegen unnötiger Scanarbeit beendet: ausschließlich eigener Audit-Python PID139320, keine Dienste oder fremden Prozesse. Der optimierte reine Payload-Audit war in unter einer Sekunde fertig.
- Vollständige gemeinsame Backend-/Frontend-Abschlussprüfung erfolgt zentral nach Zusammenführung der anderen Reparaturen. Keine Behauptung einer echten Sprachmodellqualitäts- oder Bild-/Videoabnahme.

Unmittelbarer nächster Schritt: gemeinsame Änderungen abschließend zentral prüfen und erst danach den kontrollierten lokalen Oberflächenneustart beurteilen.
