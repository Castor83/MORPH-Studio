# Phase 3: Einfach/Experte und Bildzuordnung

Stand: 20.10.2026. Begrenzte Erweiterung der bestehenden MORPH-Oberfläche auf Grundlage des freigegebenen Entwurfs. Keine neuen Dienste, Modelle, Downloads oder Berechnungen.

## Ergebnis

- Einfach ist der Ausgangsmodus. Die Hauptansicht zeigt Bildrollen, Hauptprompt, Start und Ergebnis. Der sichtbare Schalter „Expertenmodus“ blendet Modelle, technische Parameter und Modellinventare ein.
- Das Umschalten verändert nur die Sichtbarkeit vorhandener Formularelemente. Texte, manuelle Modellwahl, Größe, Seed, Bildzuordnungen, Vorschlag und offener Startbeleg bleiben erhalten. Es entsteht dabei keine Netzwerkanfrage.
- Der Ollama-Assistent ist in einem ausdrücklich optionalen Bereich aufklappbar. Sein Ausfall blockiert die Bildberechnung nicht. Vorschlag, Modellladen und Berechnung bleiben getrennte Bedienaktionen.
- Jede Bildrolle akzeptiert Dateiauswahl und Drag&Drop über dieselbe Uploadfunktion. Mehrere Dateien, andere Formate und Dateien über 64 MiB werden im jeweiligen Slot erklärt. Die Inhaltsprüfung bleibt zusätzlich beim bestehenden Backend.
- Verspätete Antworten nach einem Werkzeugwechsel werden ignoriert. Bei einer neueren Auswahl derselben Rolle gewinnt ausschließlich deren Antwort; eine ältere noch laufende Übernahme überschreibt sie nicht und hält den Start nach Abschluss der aktuellen Übernahme nicht gesperrt.
- Uploadfehler erscheinen dauerhaft im betroffenen Slot und zusätzlich in der bisherigen Rückmeldung. Es gibt keine automatische Berechnung oder Uploadwiederholung.

## Geänderte Dateien

- `E:\MORPH-Studio\ui\frontend\index.html`
- `E:\MORPH-Studio\ui\frontend\styles.css`
- `E:\MORPH-Studio\ui\frontend\forms.js`
- `E:\MORPH-Studio\ui\frontend\app.js`
- `E:\MORPH-Studio\ui\tests\app.test.mjs`
- `E:\MORPH-Studio\ui\tests\model_forms.test.mjs`

Keine neuen Frontenddateien, API-Endpunkte oder Änderungen an der Serverfreigabeliste. Ausgangsstand: `E:\MORPH-Studio\reports\entwicklung-20261020\phase2-ui-baseline`.

## Nachweise

1. Neue gezielte Tests vor Implementierung: sieben erwartete Fehler wegen fehlender Modus-/Drop-/Slotfehlerfunktionen. Ein zusätzlicher Test für den bereits bestehenden unabhängigen Ollama-Ausfall bestand schon. Beleg: `phase3-ui-red.log`.
2. Nach minimaler Implementierung: gezielte acht Tests bestanden. Beleg: `phase3-ui-green.log`.
3. Vollständige Frontendsuite: 41 Tests bestanden, keine Fehler, keine übersprungenen Tests. Beleg: `phase3-ui-full.log`.
4. `git diff --check` für die sechs geänderten Dateien: keine Whitespacefehler. Git meldet lediglich die vorhandene Windows-Zeilenendenkonvertierung.

Die Tests führen echte Formular-/UI-Funktionen mit kontrollierten DOM- und HTTP-Grenzen aus; keine Quelltext-Grep-Tests. Die Startbeleg-, Upload-, Modellwechsel- und Vorschlagsregressionen sind enthalten. Kein echter ComfyUI-/GPU-Lauf und keine Browser-/Bildqualitätsabnahme in dieser Phase.

## Nächster Schritt

Phase 4: Den separat entwickelten additiven Versionsspeicher anbinden. Dieses Paket enthält noch keine Versions- oder KI-Fortschrittsoberfläche. Browser-/Echtlaufabnahme bleibt der vorgesehenen Gesamtabnahme vorbehalten.
