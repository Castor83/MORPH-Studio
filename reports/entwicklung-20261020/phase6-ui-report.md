# Phase 6 – Frontend: unveränderlicher Originalbeleg und tatsächliche Änderungen

Stand: 20.10.2026. Ausführung durch Subagent prompt_ui; vorhandenen Phase-5-Stand unverändert als Baseline gesichert. Frontend-Arbeit abgeschlossen für unabhängigen Review, keine Dienste/Modelle/Berechnungen gestartet.

## Geändert

- ui/frontend/app.js: Vor dem POST an /api/tool-proposals werden Auftragstext, Werkzeug-ID, sämtliche aktuelle Formularwerte und die Grundeinstellungen aller angebotenen Werkzeuge kopiert und eingefroren. Der API-Vertrag bleibt unverändert; der Originalbeleg bleibt ausschließlich lokal im Vorschlagszustand. Das Antwortobjekt kann diesen Beleg nicht überschreiben.
- ui/frontend/proposals.js: Originalauftrag und ursprüngliche Nicht-Modell-Formularwerte erscheinen getrennt von der Antwort des Prompt-Assistenten. Jeder Schritt zeigt Vorher-/Nachherwerte ausschließlich für tatsächlich geänderte Nicht-Modellfelder. Beim ursprünglichen Werkzeug gelten die Anfragewerte, bei anderen Werkzeugen deren am Anfragezeitpunkt erfasste Grundeinstellungen. Diese Vergleichsbasis bleibt nach einer oder mehreren Übernahmen bestehen.
- ui/frontend/index.html und styles.css: getrennte Darstellung von Original, Antwort und Änderungen; lange Texte und Zeilenumbrüche bleiben lesbar. Alle vom Nutzer/Assistenten stammenden Werte werden über textContent ausgegeben.
- ui/tests/app.test.mjs und tool_proposals.test.mjs: drei neue Verhaltenstests. Vorhandener XSS-Test auf Textinhalt mit Vorher-/Nachher-Präfix angepasst, Prüfung auf fehlende erzeugte img-Knoten erhalten.

## Erhaltene Verträge

Einzelübernahme und bestehende Kontext-/Busy-Prüfungen bleiben bestehen. Originales Auftrags-Textfeld wird nicht ersetzt. Vorschläge ändern keine Modellfelder. Gleiches Werkzeug erhält Bilder/übrige Parameter; Werkzeugwechsel nutzt weiterhin den bestehenden chooseWorkflow-Ablauf. Keine zusätzliche Änderung an Bildprojekt-Kontext oder Bereichsmasken. Übernahme erzeugt keinen /api/jobs-POST und lädt/entlädt kein Sprachmodell.

## Nachweise

- Baseline der sechs Dateien einschließlich SHA-256: E:\MORPH-Studio\reports\entwicklung-20261020\phase6-ui-baseline\sha256.json.
- Gezieltes Rot: phase6-ui-red.log, drei Tests fehlgeschlagen wegen fehlendem Originalbeleg bzw. fehlenden Vorher-/Nachherwerten. Kein Syntax- oder Harnessfehler.
- Gezieltes Grün: phase6-ui-green.log, 3/3 Tests grün. Belegt Anfragezeitpunkt (programmgesteuerte spätere Promptanzeige ersetzt den Beleg nicht), Einfrieren des Belegs, Erhalt nach zwei expliziten Übernahmen, unveränderten Auftragstext, keine Jobs-/Modellaufrufe sowie unveränderte Felder nicht in der Differenz.
- Gesamter vorhandener Node-Lauf genau einmal nach Implementierung: npm.cmd test; phase6-ui-node-all.log, 65/65 grün, Exit 0, Dauer des Node-Testlaufs 163.7075 ms. Das sind synthetische Verhaltenstests, kein Browser-/GPU-/Bildqualitätsnachweis.
- git diff --check für die sechs Dateien: Exit 0, keine Whitespacefehler. Nur bestehende Git-Hinweise auf LF/CRLF.
- Direkter Vergleich app.js/proposals.js gegen Phase-6-Baseline gelesen. Phase-5-Vergleichs-/Bereichsfunktionen wurden nicht bearbeitet.

## Schnittstelle für Review

Optionaler lokaler Zusatz zum Vorschlagsobjekt:

    original: {
      instruction: string,
      workflow_id: string,
      controls: { [controlName]: string | number },
      workflow_defaults: { [workflowId]: { [controlName]: string | number } }
    }

Alle Objekte dieses Originalbelegs sind eingefroren, Formularwerte sind primitive Werte. renderProposals benötigt keine neue Positionsargumente und bleibt für vorhandene Vorschlagsobjekte ohne original funktionsfähig. Ohne Originalbeleg nutzt die bestehende Darstellung die Werkzeug-Grundeinstellungen als Vergleichsbasis.

Offen: unabhängiger Review, gegebenenfalls späterer isolierter Browsernachweis und echte Abnahme in Phase 9. Keine Commits, Installationen, Dienste, Modelle oder Browser ausgeführt. Alle Frontend-Mutationen sind bis zum Review gestoppt.
