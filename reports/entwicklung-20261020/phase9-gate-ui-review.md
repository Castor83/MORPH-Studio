# Unabhängiger Frontendreview des gemeinsamen GPU-Gates

Reviewmodus: ausschließlich lesend, keine eigenen Quelländerungen, keine Liveaktionen und keine Wiederholung einer Testsuite. Geprüft wurden `ui/frontend/app.js`, `ui/frontend/results.js`, die neuen Gate-/Recovery-/Settings-/Warnungsregressionen in `ui/tests/app.test.mjs` und `ui/tests/results.test.mjs` sowie die vorhandene Schnittstelle von `resources.js`. Root übernimmt die gemeinsame abschließende Prüfung und Versionierung. Backend bleibt unverändert.

## Konkreter Reviewbefund P2 und Bearbeitung

`refreshServiceStatus()` hatte keinen Revisionszaun gegen verspätete Antworten. `refreshJobs()` setzte `state.polling=false` vor dem awaited Statusread, sodass mehrere Statusreads überlappen konnten. Eine vor dem Abschluss der Sprachaktion gelesene Antwort mit `busy=true` konnte nach einer später angefragten und bereits angezeigten Antwort mit `busy=false` eintreffen und die UI erneut sperren. Ohne aktive Bildjobs oder offenen Startbeleg liest der bisherige Timer keinen weiteren Status. Das betrifft Start, Sprache, Settings und Free und kann deshalb einen bewussten weiteren Arbeitsschritt verhindern, obwohl der Server wieder frei ist.

Root hat diesen Befund als gezielte Regression/Korrektur an den Frontendagenten gegeben. **Im final gemeldeten Stand behoben:** `serviceStatusRevision` versieht jeden Statusread mit einem fortlaufenden Index; sowohl Success als auch Catch dürfen nur noch den jüngsten Read anwenden (`app.js:119–122`). Die Regression hält den älteren Statusread offen, lässt einen späteren Read nach abgeschlossenem Load bestätigen und liefert dann entweder eine alte busy-Antwort oder einen alten Fehler. Beide Fälle behalten den aktuellen freien Zustand. Dazugehörige Rot-/Grünlogs wurden gelesen; keine eigene Testwiederholung.

## Weiterer offener P2: Remote-Busy wird ohne Bildjob nicht erneut gelesen

Im geprüften Stand `app.js:436–444` setzt Boot einen aktuell wahren serverseitigen busy-Zustand und überspringt dadurch den ersten Modellrefresh. Bei leeren Bildjobs und fehlendem pending-Beleg erfüllt anschließend kein Timerdurchlauf seine Pollbedingung. Wenn die außerhalb dieses Browserfensters begonnene Sprachaktion fertig wird, bleibt der Status in diesem Fenster busy. Load/unload/Vorschlag/Start/Free und Modellrefresh bleiben gesperrt, während der Hinweis ausschließlich zum Warten auffordert. Nur ein nicht ersichtlicher manueller Klick auf „Aufträge aktualisieren“ würde den Serverstatus neu lesen.

Das lässt sich aus den tatsächlichen Kontrollzweigen ableiten; es wurde kein eigener Funktionstest gestartet. Konkretes Szenario: Oberfläche während einer noch laufenden Sprachaktion aus einer zweiten Seite oder nach Browser-Reopen öffnen; keine Bildjobs und kein Startbeleg; Sprachaktion im anderen Browserfenster abschließen. Ein Statusrevisionszaun verhindert Antwortvertauschungen, erzeugt aber keinen neuen Read. Vorschlag für die gezielte Korrektur: Pollbedingung um beobachtetes `languageState.busy` erweitern und beim Übergang zurück zu frei den initial übersprungenen Modellrefresh nachholen. Das ist reine Status-/Modelllistenabfrage; keine Mutation und kein Retry des Sprachaufrufs. Root ist informiert, Entscheidung/Korrektur liegt beim Frontendagenten.

Der bereits separat von Root gefundene und vom Frontendagenten korrigierte zweite Refreshfehler wurde im Code gelesen: Ein internes `refreshModels(true)` nach bestätigtem load/unload darf den lokal noch gehaltenen modelBusy-Flag und einen veralteten serverseitigen busy-Hinweis für diesen reinen GET übergehen. Normale Mutationseinstiege bleiben gesperrt; vor der abschließenden lokalen Entsperrung wird der Serverstatus erneut gelesen. Die ergänzte Regression hält den Lade-POST offen, liest währenddessen serverseitig busy, bestätigt danach den Load und prüft die tatsächlich neu angezeigte geladene Instanz.

## Weitere kontrollierte Pfade

- `modelBusy` und `proposing` werden vor dem ersten mutierenden await gesetzt. Der Bild-Submithandler sowie der Ressourcencontroller prüfen die Sperre synchron. Gesperrte Klicks werden nicht in eine spätere Aktion umgewandelt.
- Aktive Bildzustände einschließlich preparing, submitting und unknown, offene Startbelege, begonnene Bildübergabe und laufende bewusste Ressourcenfreigabe sperren Sprachaktionen bereits im Handler. Die Backendhülle bleibt unabhängig maßgeblich.
- Ein gespeicherter unbekannter Sprachzustand wird aus `language_state.uncertain_instances` gelesen. Genau ein solcher Name wird als ausdrückliches unload-Ziel verwendet, auch wenn die Modellliste leer und keine bestätigte instance_id vorhanden ist. Mehrere Ziele würden keine willkürliche Auswahl erzeugen. Es gibt keinen automatischen unload-Aufruf.
- Die UI sperrt bei Unknown Bildstart, Laden, Vorschläge, Freigabe der Bildmodelle sowie Auswahl-/Verbindungsänderungen. Der ausdrückliche unload-Klick bleibt nur ohne andere aktive Arbeit zugänglich. Nach seiner Antwort folgt ein frischer Statusread.
- Auswahl- und Settingshandler prüfen ihre Sperre zusätzlich zu disabled. Der Settingsdialog prüft nach seinem asynchronen GET nochmals, ob inzwischen eine Sperre entstand. Ein abgewiesener Handler verändert später keine Einstellungen.
- `job.warnings` wird nur als Liste nichtleerer Texte gerendert. Die Texte werden über textContent ausgegeben; der echte Jobstatus bleibt erhalten. Die Warnung erzeugt weder Modellmutation noch Retry und wird nicht in eine erfolgreiche GPU-/Qualitätsabnahme umgedeutet.

Bewertungsgrenze: Quell- und Fixtureprüfung. Kein eigener Browser-/GPU-Nachweis und keine allgemeine VRAM-Fit-Garantie. Fremde direkte Clients bleiben außerhalb des MORPH-Locks.

## Prüfbinding und Urteil

Der vom Frontendagenten gemeldete finale fokussierte Lauf wurde im vorhandenen Log abgelesen: `phase9-gate-ui-final.log`, **83 Tests, 83 PASS, 0 FAIL**, Dauer 228.0045 ms. Die Dateihashes wurden unabhängig gelesen und stimmen mit `phase9-gate-ui-final-hashes.json` überein:

| Datei | SHA256 |
| --- | --- |
| `ui/frontend/app.js` | `A185A06A4A1B89E0BB15757076F0EC5B3CFB3C6CF64421D5A92AA1FF92A28B5E` |
| `ui/frontend/results.js` | `97C0BA0427FE56474861D5E5D80E73243B2C374DFE3913F6C8317CCFA95CEF00` |
| `ui/tests/app.test.mjs` | `C623CE3B5DDC404C270C8222B4802A84CE71CC2E4A88D9C323004CC6D0727325` |
| `ui/tests/results.test.mjs` | `A435D670CB36ADFE9A2FB0AB26FCBF5F0783A6CE8ABEE0D1715F66CE38A0C6E5` |

Urteil zu diesem Dateistand: kein offener P1; ein konkreter offener P2 beim fortgesetzten Read eines echt beobachteten Remote-Busy ohne Bildjob. Der zuvor gefundene P2 zu verspäteten Statusantworten ist im geprüften Stand geschlossen. Keine sonstigen offenen P1/P2 in den oben begrenzt geprüften Gate-/Recovery-/Settings-/Warnungspfaden.
