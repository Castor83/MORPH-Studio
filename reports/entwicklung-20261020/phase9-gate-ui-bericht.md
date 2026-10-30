# Phase 9 – gegenseitige Frontend-Sperren und bewusste Unknown-Auflösung

Arbeitsbereich: `E:\MORPH-Studio`, bestehender Branch `main`, Ausgangs-HEAD `18522b6255befb633f5b193159f84326d521dbb5` am 20.10.2026. Unterauftrag des Hauptchats, kein Commit durch diesen Agenten. Historische PAUSE-Dateien wurden gelesen und nicht verändert; die aktuell autorisierte Entwicklung ist nicht pausiert. Quellenmirror und fremde Änderungen bleiben unverändert.

## Ursache und Umsetzung

Die im Übergabebericht `CHAT-UEBERGABE-01a15a06.md` benannten Lücken waren im aktuellen Frontend vorhanden: Bildstart prüfte weder `modelBusy` noch `proposing`; Laden/Freigeben/Vorschlag prüften keine aktiven Bildaufträge; Ressourcen-Free berücksichtigte keine laufenden Vorschläge. Die Sperren sind nun gegenseitig und kehren bei gesperrtem Klick sofort zurück. Es gibt keine Warteschlange für zurückgewiesene Aktionen, kein automatisches Laden, Freigeben oder erneutes Submit.

`ui/frontend/app.js`:

- Bildstart und Bildmodell-Free bleiben während Laden/Freigeben/Vorschlag gesperrt.
- Alle aktiven Bildzustände (`preparing`, `submitting`, `queued`, `running`, `unknown`), laufende Übergabe und ungeklärte Startbelege sperren Sprachaktionen und Ressourcen-Free.
- Ressourcen-Free sperrt Laden/Freigeben/Vorschlag. Laufender Vorschlag sperrt ebenfalls Laden/Freigeben.
- Modell-/Instanzauswahl und Verbindungsdialog prüfen die Sperre auch in ihren Eventhandlern. Eine zurückgewiesene Einstellungsänderung wird nach Entsperrung nicht nachgeholt.
- Die mit dem Backend abgestimmte Antwort `GET /api/status: language_state={busy, uncertain_instances}` wird bei Start und Statusaktualisierung gelesen. Nach jeder Modellmutation und jedem Vorschlag erfolgt eine frische Statusabfrage.
- `busy` sperrt alle betroffenen mutierenden Aktionen. Bei genau einem gespeicherten unbekannten Ziel zeigt die Oberfläche dessen Namen und den Grund. Bildstart/Laden/Vorschlag/Free und Verbindungsauswahl bleiben gesperrt; die bewusst angeklickte Sprachmodellfreigabe verwendet ausschließlich dieses gespeicherte Ziel, auch ohne Eintrag in der geladenen Modellliste. Erst der frisch bestätigte serverseitige Zustand hebt die Sperre auf. Es wird kein Ziel aus Modelldatei, Auswahl oder Größe erfunden.
- Der vorhandene Timer liest auch bei serverseitigem Busy oder unbekanntem Ziel weiter. Wird eine fremde Sprachaktion in einem anderen Fenster abgeschlossen oder dort bewusst geklärt, aktualisiert der angenommene Statusübergang zusätzlich die Modellliste lesend. Während eigener Mutation übernimmt deren vorhandener Abschlussweg diese Aktualisierung. Es gibt dabei keinen mutierenden Aufruf.
- Bestehende Formularwerte, Startbelege und Vorschlagsübernahmen bleiben erhalten. Optionale Ollama-Leseausfälle sperren gewöhnliche Bildarbeit weiterhin nicht grundsätzlich.

`ui/frontend/results.js` zeigt `job.warnings: string[]` dauerhaft als reinen Text im Auftragsbeleg an. Der tatsächliche Auftragszustand bleibt maßgeblich; ungültige Warnungsstrukturen erzeugen keine Nachrichten. Diese Anzeige ergänzt beispielsweise den Hinweis auf unbekannten optionalen Ollama-GPU-Zustand ohne Mutation oder Retry.

## Nachweise

Alle Prüfungen sind lokale kontrollierte JavaScript-Fixtures mit echtem Frontendcode und simulierten HTTP-Antworten. Keine echten Dienste, Provider, Modelle oder Produktivdatenbanken wurden angesprochen. Kein Browser-/GPU-/Qualitätsnachweis.

| Beleg | Ergebnis |
|---|---|
| `phase9-gate-ui-red.log` | 7 neue Gate-Tests zunächst erwartungsgemäß rot, 0/7 bestanden |
| `phase9-gate-ui-green.log` | Dieselben 7 Gate-Tests nach schmalem Fix grün |
| `phase9-gate-ui-warning-red.log` | Warnungsanzeige: 2 erwartete Fehler; 1 zusätzlicher Strukturgrenzfall bereits korrekt |
| `phase9-gate-ui-warning-green.log` | 3/3 bestanden |
| `phase9-gate-ui-recovery-red.log` | 3/3 neue Status-/Unknown-Recovery-Tests erwartungsgemäß rot |
| `phase9-gate-ui-recovery-green.log` | Dieselben 3/3 grün |
| `phase9-gate-ui-settings-red.log` | 1 neuer Auswahl-/Verbindungs-Gatetest erwartungsgemäß rot |
| `phase9-gate-ui-settings-green.log` | Derselbe Test grün |
| `phase9-gate-ui-busy-refresh-red.log` | 1 reproduzierter Race: ein während eigener Ladung beobachteter Busy-Status verhinderte nach bestätigter Ladung die Modelllistenaktualisierung |
| `phase9-gate-ui-busy-refresh-green.log` | Derselbe Test grün; ausschließlich die interne Listenaktualisierung nach bestätigter eigener Mutation darf den veralteten Busy-Snapshot übergehen. Keine Mutation wird dadurch erlaubt; der abschließende frische Status bleibt maßgeblich |
| `phase9-gate-ui-status-race-red.log` | Ein zusätzlicher asynchroner Race erwartungsgemäß rot: eine alte Busy-Statusantwort überschrieb den frischen Abschlusszustand |
| `phase9-gate-ui-status-race-green.log` | Derselbe Test grün, einschließlich später Fehlerantwort; ein Antwortrevisionszaun verwirft veraltete Erfolge und Fehlschläge |
| `phase9-gate-ui-remote-recovery-red.log` | Erwarteter Fehler beim Öffnen der Seite während einer fremden Sprachaktion: fehlendes weiteres Statuspolling |
| `phase9-gate-ui-remote-recovery-green.log` | Derselbe Test grün für Busy und Unknown, inklusive erneuter rein lesender Modelllistenaktualisierung; die Fixture führt den echten registrierten Timer-Callback gezielt ohne Wartezeit aus |
| `phase9-gate-ui-final.log` | Abschließend `node --test ui/tests/app.test.mjs ui/tests/results.test.mjs ui/tests/resources.test.mjs`: **84/84 PASS**, Exit 0 |
| `phase9-gate-ui-final-hashes.json` | SHA-256 der vier abschließend geprüften Dateien |

Ein Zwischenlauf wurde gezielt beendet, nachdem eine bestehende Vorschlagsfixture alle späteren HTTP-Abfragen unbegrenzt festhielt. Der zusätzliche Status-Read machte diese zu breite Testsimulation sichtbar. Die Fixture hält jetzt ausschließlich `/api/tool-proposals`; der Originalzweck (späte Vorschlagsantwort überschreibt geändertes Formular nicht) ist unverändert. Das unvollständige Log bleibt unter `phase9-gate-ui-controller-fixture-hang.log` erhalten und ist kein PASS-Beleg. Der eigene Testprozess wurde beendet; der anschließende vollständige fokussierte Lauf ist oben belegt.

Die komplette Projekt-/UI-Suite führt der Hauptagent nach Integration des Backendblocks einmal aus. Bereits abgeschlossene Phasen wurden nicht zur Orientierung wiederholt. `git diff --check` für die vier bearbeiteten Dateien hat keine Whitespace-Fehler gemeldet; Git weist lediglich auf die Windows-Zeilenendennormalisierung hin.

## Dateien und Grenzen

Bearbeitete Entwicklungsdateien ausschließlich:

- `E:\MORPH-Studio\ui\frontend\app.js`
- `E:\MORPH-Studio\ui\frontend\results.js`
- `E:\MORPH-Studio\ui\tests\app.test.mjs`
- `E:\MORPH-Studio\ui\tests\results.test.mjs`

Vorherige Dateien liegen unter `phase9-gate-ui-baseline/`; Hashes und sämtliche eigenen Logs tragen `phase9-gate-ui*`. Keine Backenddatei durch diesen Implementierungsschritt verändert. Keine Pause, Datenbankmigration, Prozesssteuerung eines echten Dienstes, Modellaktion, Installation oder globale Änderung. Die Backendautorisierung, persistente Unknown-Bindung und tatsächliche GPU-Residenzprüfung werden gesondert implementiert und unabhängig geprüft. Das Frontend schützt seine Bedienaktionen; direkte fremde Clients liegen außerhalb davon.

Nächster Schritt im Hauptchat: unabhängiges Diffreview der vier Frontenddateien und des separaten Backendblocks, anschließend genau eine gemeinsame finale Suite und selektiver lokaler Commit durch Root.
