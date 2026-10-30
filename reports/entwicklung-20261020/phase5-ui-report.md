# Phase 5 – Frontend: Versionsvergleich und Bereichsauswahl

Stand: 20.10.2026. Bestehender Checkout; keine Dienste, Modelle, Downloads oder Commits durch den Frontend-Teilauftrag gestartet.

## Umsetzung

- `E:\MORPH-Studio\ui\frontend\comparison.js`: Zwei beliebige persistente Versionen nebeneinander; Original-/Elternversion bequem wählen, Ansichten tauschen. Gemeinsamer Zoom 100–600 %, synchrones Verschieben mit Zeiger oder Pfeiltasten. Die Ansicht bleibt bei einer Aktualisierung desselben Projekts erhalten. Vergleich ändert weder Eingabebild noch Auftragswarteschlange.
- `E:\MORPH-Studio\ui\frontend\regions.js`: Bereich auf dem aktuellen, gesicherten Eingabebild für KREA 2/Kontext weiß markieren, radieren, Pinselgröße wählen, ausdrücklich übernehmen oder mit „Ganzes Bild bearbeiten“ verwerfen. Export als deckende graue PNG in Quelldimensionen; Upload erst nach Übernehmen. Unübernommene Markierungen blockieren den Berechnungsstart.
- Maske ist an Werkzeug, Bild-ID, Projekt und Elternversion gebunden. Bild-/Kontextwechsel verwerfen die Bindung. Verspätete Bildlade- und Uploadantworten können keine alte Markierung an ein neues Eingabebild hängen.
- Exaktes Seitenverhältnis wird vor Maskenspeicherung geprüft. Die ausdrückliche Aktion „Passende Bildgröße übernehmen“ wählt unterstützte Dimensionen mit gleichem Seitenverhältnis; kein stiller Größenwechsel. Ein späterer inkompatibler Größenwechsel blockiert einen maskierten Start mit konkreter Hilfe.
- `app.js`, `results.js`, `index.html`, `styles.css`: Integration und Versionskarten-Aktion „Vergleichen“. Maskierter Auftrag erhält zusätzlich `edit_region:{mask_media_id,source_media_id,parent_version_id}`. Ohne übernommene Maske fehlt dieses Feld vollständig.
- `E:\MORPH-Studio\ui\tests\image_editing.test.mjs`, `app.test.mjs`: Geometrie, synchroner Bildausschnitt, Versionenauswahl, explizite Aktionen, Startschutz, verspätete Antworten und konkrete Job-Bindung.

## Nachweise

Baseline vor der ersten Änderung: `phase5-ui-baseline/` und `phase5-ui-baseline-hashes.txt` in diesem Verzeichnis. Vorhandene Phase-4-52/52-Prüfung wurde zur Orientierung nur gelesen.

`phase5-ui-red.log`: Die vier ersten Tests scheiterten gezielt an fehlenden Modulen/Funktionen.

`phase5-ui-final.log`: `node --test tests/*.test.mjs` im Verzeichnis `E:\MORPH-Studio\ui` – **62 Tests, 62 bestanden, 0 Fehler**, Exit 0. Darunter reale Frontend-Controller mit kleinem DOM-/Canvas-Doppel und App-Integration; keine Bildinferenz. `git diff --check -- ui/frontend ui/tests/app.test.mjs` ohne Befund.

Browsernachweis führt der Hauptagent getrennt aus. Die Node-Prüfungen belegen keine reale Modellqualität, keinen Kleidungswechsel und keine allgemeine Identitätserhaltung.

## Grenzen

Die Markierung ist eine abschließende Bereichskomposition. Das Modell sieht das ganze Ausgangsbild; es handelt sich nicht um semantisches Inpainting. Innerhalb der Markierung können Inhalt, Details, Ausrichtung und Übergänge abweichen. Der Backend-Vertrag sichert die genaue Quellgeometrie und prüft Maskendatei, Elternversion und Quellbild nochmals. EXIF-gedrehte Quellen benötigen gemäß Backend-Beschränkung zunächst eine ohne EXIF-Drehung gespeicherte PNG. Optionaler Wischregler und Differenzmodus sind nicht umgesetzt.

Abschlussnachtrag Root: Unabhängiger Frontendreview ohne konkrete P1/P2. Der rote Seitenverhältnishinweis erscheint nun erst bei einer aktiven Markierung oder gesicherten Maske; Vollbildjobs bleiben ohne Größenanpassung bedienbar. Acht betroffene Controllertests danach erneut gezielt grün (phase5-ui-hint-check.log). Isolierter Browserbeleg einschließlich Reload und explizitem Maskenauftrag steht in phase5-browser.md; Testdienst und Tab wurden beendet.
