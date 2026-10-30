# Phase 5 – isolierte Browserabnahme

20.10.2026, Nachfolgechat 01a15a06-bd67-7d83-a3cc-6eaa8f6b203d. Fixture phase5_browser_fixture.py unter Port8767, temporäre SQLite/Dateien und winzige Modellheader, keinerlei echte ComfyUI-/Ollama-/Modellausführung. Vier synthetische Versionen vorgeladen. Der CPU-Testersatz simuliert ein generiertes Bild und die abschließende Bereichskopie; er belegt keine native Tensor-/GPU-Ausführung oder semantische Bildqualität.

Ergebnisse:
- Projekt geöffnet, Version1 links und Version2 rechts ausdrücklich gewählt. Gemeinsamer Zoom600% und Verschieben erzeugten in beiden Bildansichten exakt `translate(5%, 0%) scale(6)`. Eingabekontext blieb leer; Vergleich allein erzeugte keinen Auftrag.
- Original ausdrücklich als Eingabe ausgewählt, KREA-Formular und Bereichsauswahl geöffnet. Größenhinweis bot passend zum 384x256-Original die explizite Übernahme960x640 an. Diese Übernahme änderte nur Formularwerte.
- Mit Zeiger einen Bereich im Hemd markiert: Start gesperrt, lokale Anleitung sichtbar. „Bereich übernehmen“ sicherte die PNG-Maske; danach weiterhin0Submissions/4Versionen (phase5-browser-before-submit.json).
- Genau ein ausdrücklicher Berechnungsklick:1Submission, completed, Graph mit1ImageCompositeMasked, edit_region.mode=masked_composite,5Versionen und persistenter Maskenbeleg (phase5-browser-after-submit.json).
- Seite neu geladen und dasselbe Projekt geöffnet:5Karten Original/Version1/2/3/4, neuer Zwischenstand vonOriginal verknüpft. Kein Ausgangsbild automatisch gewählt, weiterhin1Submission (phase5-browser-after-reload.json).
- Browserkonsole vor/nach Reload ohne Warnung/Fehler. Screenshot phase5-vergleich-browser.png zeigt frei gewählteVersion1/2, phase5-maskenergebnis-browser.png zeigt Original/neuen maskierten Zwischenstand. Sämtliche Bilder sind sichtbar als Simulation gekennzeichnet.

Testdienst über eigenen /_fixture/stop beendet: stopped=true,submissions=1; Execsession45707 exit0. Agentenerstellter BrowserTab geschlossen. Keine Produktionsdatenbank, bestehenden Benutzerbilder, Modelle oder Workflows verändert. Unabhängiger Code-Review läuft separat; echte lokale Bildabnahme bleibt Phase9.
