# Phase 7 – Ressourcenanzeige und bewusste Freigabe (Frontend)

Stand: 20.10.2026. Umsetzung innerhalb der freigegebenen Phase 7. Kein Browser, Dienststart, Modellaufruf, GPU-Test oder Commit durch diesen Agenten. Unabhängiger Review und echte Integration/Abnahme bleiben beim Hauptagenten.

## Verhalten

- Normale Ansicht zeigt den gemeldeten Gerätenamen, VRAM benutzt/gesamt in GiB und den tatsächlichen Messzeitpunkt. Eine Messung beim Laden sowie bewusstes Aktualisieren verwenden ausschließlich GET `/api/resources`.
- Details zeigen freien Gerätespeicher, RAM, Quelle und ausdrücklich „Geladene Bildmodelle: vom Rechendienst nicht gemeldet“. Zuletzt verwendete Modelle und behauptete Modellnamen aus anderen Antwortfeldern werden nicht als geladene Modelle angezeigt.
- Fehlende, nichtnumerische, negative oder unendliche Speicherwerte heißen unbekannt. Ausfall und unlesbare Ressourcenantworten bleiben ausdrücklich sichtbar. Sie sperren normale Bildjobs nicht. Eine ausstehende Messung gehört nicht zur Start-Sperre.
- Nur die explizite Schaltfläche „Bildmodelle im Rechendienst freigeben“ sendet POST `/api/resources/free` mit leerem Objekt. Freigabe betrifft alle Bildmodelle im eigenen Rechendienst; Ollama bleibt unverändert. Die Oberfläche zeigt sowohl Backend-Sperrgrund als auch aktuelle lokale Sperren für Start, aktive/ungeklärte Aufträge, Uploads und vorbereitende Bildzuordnungen. Der Backend-Lock und seine erneute Prüfung bleiben die maßgebliche Grenze.
- Während der Freigabeanfrage ist ein neuer Bildstart gesperrt. Nach der Antwort endet diese Sperre, bevor die anschließende reine Messung abgeschlossen ist. Eine angenommene Anfrage wird nur als „Freigabe angefordert“ angezeigt; sie beweist keinen abgeschlossenen Entladevorgang.
- Ressourcenanfragen haben eine eigene Generation. Ein alter GET kann weder einen neueren GET noch die Messung nach einer Freigabe überschreiben. Es gibt keine automatische Freigabe beim Laden, Bildwechsel, Start, Abschluss oder Fehler.
- Die Bedienhilfe nennt die technische Grenze, dass direkte ComfyUI-Nutzer außerhalb MORPH durch MORPH nicht gesperrt werden können.

## Dateien und Sicherung

Geändert: `E:\MORPH-Studio\ui\frontend\app.js`, `index.html`, `styles.css`, `E:\MORPH-Studio\ui\tests\app.test.mjs`.

Neu: `E:\MORPH-Studio\ui\frontend\resources.js`, `E:\MORPH-Studio\ui\tests\resources.test.mjs`.

Vorherige Inhalte samt SHA-256: `E:\MORPH-Studio\reports\entwicklung-20261020\phase7-ui-baseline\manifest.json` und dateigleiche Unterordner. Ausgangs-HEAD: `ad4551d3669f74d92e0ed955ced40cd09b80a4cf`. Keine fremden Dateien oder Pausezustände verändert. Die statische Serverfreigabe für resources.js übernimmt der Backend-Agent.

## Prüfungen

| Prüfung | Ergebnis | Beleg |
| --- | --- | --- |
| RED vor Implementierung, App + Ressourcen | 13 neue Fälle gezielt fehlgeschlagen, 38 bisherige App-Fälle bestanden | `phase7-ui-red.log` |
| Erster Implementierungslauf | 50/51; nur zu eng flektierte Textprüfung für den ausdrücklichen Nichtabschluss-Hinweis korrigiert | `phase7-ui-first-green.log` |
| Fokussiert nach Korrektur | 51/51 bestanden | `phase7-ui-green.log` |
| Vollständiges `npm test` einmal | 78/78 bestanden, keine Abbrüche/Skips | `phase7-ui-node-all.log` |
| `git diff --check` für die vier geänderten vorhandenen Dateien | keine Whitespacebefunde / Exit 0; nur bestehende Git-Hinweise zur späteren LF/CRLF-Normalisierung | aktuelle Agentenprüfung |

Neue Verhaltenstests prüfen normale und fehlerhafte Messwerte, fehlende Werte, unbekannte Modellbelegung, Ressourcenfehler, verzögerte Antworten, explizite Freigabe, Backend-/lokale Sperren, Ablehnungsgründe, offene Freigabebestätigung und weiterhin mögliche Bildstarts trotz Ressourcenfehler oder laufendem GET. Testdaten sind synthetisch; echte Dienstidentität, VRAM-Änderung und visueller Browsernachweis sind dadurch nicht nachgewiesen.

## Nächster Schritt

Hauptagent lässt Frontend und Backend unabhängig prüfen, behebt konkrete Befunde, führt die notwendige integrierte Prüfung aus und sichert danach den erfolgreich geprüften Block mit einem gezielten Commit gemäß Nutzeranweisung. Dieser Agent ändert nach Übergabe ohne neuen Befund nichts weiter.
