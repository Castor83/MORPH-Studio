# Phase 4: Bildprojekte und explizite Versionszweige

Stand: 20.10.2026. Frontendpaket fertig implementiert und automatisiert geprüft. Der lokale Zwischencommit `dfaf115` enthält den vorherigen ausdrücklich unfertigen Stand; dieser Bericht bezieht sich auf die danach vervollständigte Anbindung.

## Verhalten

- Nach bestätigter primärer Bildübernahme wird das Original automatisch als Bildprojekt gesichert. Primär ist `image` bei Kontext/KREA/WAN und `target` beim Gesichtstausch. Die Originalsicherung startet keine Berechnung.
- Der Start wartet auf die Originalsicherung. Bei einem Fehler bleibt das Bild ausgewählt; „Original erneut sichern“ wiederholt nur den Speicherauftrag mit derselben Anforderungskennung. Kein automatischer Wiederholungsversuch.
- Projekt und Elternversion sind an konkrete Medien-ID, Rolle und Werkzeug gebunden. Verspätete Upload-/Projekt-/Versionseingaben können keine neuere Auswahl überschreiben. Die Zuordnung ist eine technische Medienbindung, keine Inhaltsbewertung. Modell-/uncensored-Einstellungen werden nicht verändert.
- Projektliste und Versionen werden aus der bestehenden lokalen API geladen und sind nach Neuladen wieder erreichbar. Das Öffnen eines Projekts zeigt ausschließlich den Verlauf und übernimmt kein Bild.
- Original und Kinder erscheinen als Baum. Die erste Bearbeitung heißt „Version 1“, die zweite „Version 2“; Original und Eingabekontext verwenden dieselbe Beschriftung. Technische Kennungen erscheinen nur im Versionsbeleg des Expertenmodus.
- „Weiterbearbeiten“, „Variante erstellen“ und „Original verwenden“ bereiten ausschließlich die ausdrücklich ausgewählte Version über `/input` vor. Danach prüft der Nutzer Auftrag und Einstellungen und startet selbst. Das bisher passende Werkzeug bleibt erhalten, sonst wird KREA 2 oder Kontext gewählt. Beim Gesichtstausch bleibt das Quellgesicht erhalten und die Version wird dem Zielfoto zugeordnet.
- Jede Version bietet einen normalen Mediendownload. Fertige Bilder ohne Projekt können ausdrücklich als neues Original gesichert werden; sie werden dabei nicht automatisch zum nächsten Eingabebild.
- `versioning_error` lässt das fertige Ergebnis sichtbar. Sowohl „Versionsspeicherung erneut prüfen“ als auch „Aktualisieren“ lesen den einzelnen Job per GET erneut und können damit nur dessen Metadatenspeicherung nachholen. Es entsteht kein zweiter Submit.

## Änderungen

Produktdateien: `E:\MORPH-Studio\ui\frontend\app.js`, `results.js`, `index.html`, `styles.css`.

Tests: `E:\MORPH-Studio\ui\tests\app.test.mjs`, `results.test.mjs`. Bestehende Tests anderer UI-Bereiche verwenden einen vollständigen kontrollierten Projekt-API-Ersatz; die Phase-4-Vertragstests prüfen die tatsächlichen Grenzanfragen separat.

Keine neue Frontenddatei oder erforderliche Serverfreigabe. Die tatsächlichen Rückgabeformen aus `E:\MORPH-Studio\ui\morph_ui\versions.py` wurden mit der UI-Anbindung abgeglichen.

## Prüfungen

- `phase4-ui-red.log`: vier neue Anbindungsfälle vor Implementierung erwartbar fehlgeschlagen.
- `phase4-ui-results-red.log`: fehlende Ergebnis-/Versionsfehleraktionen vor Implementierung nachgewiesen.
- `phase4-ui-green.log`: sechs gezielte Fälle bestanden.
- `phase4-ui-recovery-red.log`: fehlender Detailrefresh eines abgeschlossenen Jobs mit Versionsfehler nachgewiesen; behoben.
- `phase4-ui-saving-race-red.log`: ein alter Versionsbutton konnte eine laufende Originalsicherung ungültig machen; rot nachgewiesen, durch genau auf diese Übernahme begrenzte Aktionssperre behoben.
- `phase4-ui-label-red.log`: technische IDs statt lesbarer Original-/Versionsnamen nachgewiesen; gemeinsamer Beschriftungshelper korrigiert.
- `phase4-ui-final.log`: vollständige Frontendsuite **52/52 bestanden**, keine Fehler oder übersprungenen Tests.

Keine echten Dienste oder Modelle durch diesen UI-Agenten gestartet. Browser-/Backend-Integration wird separat von Root ausgeführt und ist kein Ergebnis dieser synthetischen Frontendsuite. Keine Aussage zu Bildqualität oder GPU-Abnahme.

## Weiterarbeit

UI-Dateibereich ist freigegeben. Nächster Schritt ist die laufende integrierte Browserabnahme Original → Bearbeitung → Zweig einschließlich Neuladen; anschließend kann Phase 5 den Vergleich ergänzen.
