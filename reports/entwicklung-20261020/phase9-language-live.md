# Echte optionale Sprachhilfe – ein einzelner Auftrag

20.10.2026, 18:40–18:41 UTC. MORPH UI PID103344, lokales Ollama. Bestehendes ausgewähltes `huihui_ai/qwen3.5-abliterated:9b` über `/api/models/load` einmal geladen; vorher keine geladenen Modellinstanzen (acht Modelle installiert), eigenes Laden bestätigt. Genau eine `/api/tool-proposals`-Anfrage. Keine Übernahme, kein Bildsubmit, kein Vergleich/Retry, keine manuelle Verbindungs-/Modellauswahländerung. Die normalen Lade-/Entladerouten speichern die aktive Instanzkennung; nach bestätigtem Entladen ist sie leer.

Antwort: ein KREA-Schritt, deutsche Erklärung und deutscher Prompt. Hemd dunkelblau, Gesicht/Haare/Haut/Körperhaltung/Hintergrund/Beleuchtung/Bildausschnitt ausdrücklich erhalten. Controls 768², acht Schritte, CFG1, ref_boost1 und festgelegter Seed entsprechen dem beabsichtigten Einzeltest.

Bewertung: Schema PASS, Deutsch PASS, Werkzeugwahl/inhaltliche Eignung für diesen engen Wunsch PASS. Die Erhaltung im erzeugten Bild ist damit noch nicht belegt. Keine allgemeine Modellqualitätsgarantie.

Anschließend separat angekündigte `language-unload`-Aktion: ausschließlich eigenes bestätigt geladenes Modell gezielt entladen, Bestätigung plus frisches Inventar und geklärter language_state geprüft. `unload_confirmed=true`, keine Unknown-Instanz. Keine fremden Modelle entladen.

Unveränderte Originalbelege: `phase9-live/language-20261020T184017518408Z.json`, `phase9-live/language-unload-20261020T184108360329Z.json`; beide ACTION_RETURNED, Exit0. Zustandsjournal bleibt lokal mutable und wird nicht als statischer Abschlussbeleg committed.

Nächster Schritt: bestehendes synthetisches Original als eigene API-Kopie mit konservativer Hemdmaske in einem Abnahmeprojekt vorbereiten; danach getrennt angekündigte KREA-Einzeljobs.
