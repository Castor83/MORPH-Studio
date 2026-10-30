# Unabhängiges Backend-Diffreview durch Frontendagent

20.10.2026, `E:\MORPH-Studio`. Auftrag des Hauptagenten: ausschließlich lesende Prüfung des Backend-Gate-Diffs und der neuen Regressionen. Der Reviewer hat keine Backenddatei verändert, keine Python-Suite wiederholt und keine echte Ollama-/Comfy-/GPU-/Datenbankaktion ausgeführt. Bewertungsbasis sind aktuelle Quellen, Diff und vorhandene protokollierte Fixtureergebnisse.

## Ergebnis

Im unten gebundenen finalen Quellstand **keine offenen P1/P2-Befunde** in den gezielt geprüften Sprach-/Bild-/Free-Gates. Dies ist ein begrenztes Quellreview; die gemeinsame finale Suite und ein echter Funktionstest bleiben separate Nachweise.

Ein konkreter P2 wurde im Review gefunden und dem Hauptagenten gemeldet: `_loaded_names` verwarf ungültige `/api/ps`-Einträge still. Eine bestätigte bewusst angeklickte Reconcile-Freigabe konnte dadurch `{'models':[{}]}` wie eine leere Liste als angebliche Abwesenheitsbestätigung behandeln, den persistierten Unknown-Beleg löschen und danach Bildarbeit erlauben. Der Backendautor hat dies eng korrigiert: Alle Einträge müssen einen gültigen eindeutigen Namen besitzen; widersprüchliche `name`/`model`-Felder werden abgelehnt. Ein tatsächlich leeres `models:[]` bleibt gültig.

Die Korrektur und ihre neuen Tests wurden anschließend erneut gelesen. Die Recovery-Regression startet zunächst einen simulierten Chat-Timeout, bestätigt danach den ausdrücklich angeforderten Unload-POST und liefert für dessen anschließende frische `/api/ps`-Abfrage einen ungültigen Eintrag. Der erwartete 409/Unknown-Beleg bleibt bestehen, Bildstart bleibt gesperrt. Ein nachfolgender neuer bewusster Unload mit gültiger leerer Liste löst ihn. Separate Strukturgrenzfälle prüfen ungültige sowie widersprüchliche Namen ohne zusätzlichen POST.

Vorhandene Belege, vom Reviewer gelesen und nicht selbst erneut ausgeführt:

- `phase9-gate-backend-invalid-ps-red.log`: 3 Tests, 10 erwartete Assertion-Fehler vor Korrektur, darunter tatsächlich HTTP200 statt des geforderten HTTP409 im Reconcile-Fall.
- `phase9-gate-backend-invalid-ps-green.log`: 41 Tests OK in 28.260 Sekunden nach Korrektur, einschließlich Gate-/Providerregressionen. Die asyncio-Ausgaben benennen langsame isolierte Fixturetasks; sie sind kein echter Modelllauf.

## Kontrollierte Pfade

- `language_busy` wird nach Erwerb des gemeinsamen Locks vor dem ersten await gesetzt. Bildcreate und Free prüfen es vor dem Warten auf den Lock und erneut danach. Neue Sprachaktionen prüfen den gehaltenen Lock und sämtliche ungelösten gespeicherten Bildjobs vor Provideraufruf. Ein abgelehnter Request wird nicht später automatisch ausgeführt.
- Bereits gespeicherte Anforderungskennungen liefern ihre bestehende Quittung auch während Sprachbusy; der neue frühzeitige Rückgabeweg erzeugt keinen zweiten Submit.
- Der Begonnen-Beleg wird unmittelbar vor `/api/generate` oder `/api/chat` dauerhaft geschrieben. Ein Ausfall eines vorherigen reinen Leseaufrufs erzeugt keinen neuen Unknown-Beleg. Timeout/Abbruch nach begonnenem POST lässt den Beleg erhalten. Der `finally`-Pfad setzt Busy zurück und stellt den Providerobserver wieder her, ohne den Beleg zu entfernen.
- Die bestätigte Providerantwort muss `done:true` und exakt dasselbe Modell enthalten. Ein zwar abgeschlossener, aber inhaltlich ungültiger Vorschlag erzeugt keinen erfundenen noch laufenden Request; reale weitere GPU-Residenz wird gesondert vor Bildstart geprüft.
- Nur der bewusst angeforderte Unload genau des gespeicherten Ziels und am gespeicherten normalisierten Endpunkt darf den Unknown-Fence passieren. Fehlgeschlagene oder unbestätigte Freigabe lässt Unknown stehen. Auch Recovery kann keine aktive Sprach-/Bildarbeit übergehen. Einstellungen sind während Sprachbusy, Unknown oder gehaltenem Lock gesperrt; nach einer externen Endpunktänderung wird der falsche Zielserver abgelehnt.
- Positives numerisches `size_vram` wird ausschließlich aus frischem native `/api/ps` herangezogen und sperrt Bildarbeit mit Modellnamen. Null und eine gültige leere Liste erlauben weiter; unerreichbares/ungültiges optionales ps erzeugt nur einen Hinweis. Das beseitigt keinen eigenen Unknown-Beleg.
- Vor Laden/Vorschlag werden die Comfy-Queue und echte `torch_vram_total`-Werte geprüft. CPU-RAM wird ausgenommen. Positive Nicht-CPU-Reservierung sperrt die optionale Sprachaktion; ein frisch bestätigter freier Port bei gestopptem Dienst erlaubt sie. Eine erreichbare unprüfbare Instanz wird abgelehnt. Kein neuer automatischer Start, Unload oder globaler Free wird erzeugt.

## Gebundene Quellen

| Datei | SHA-256 des abschließend gelesenen Standes |
|---|---|
| `ui/morph_ui/jobs.py` | `D7A91C52372D76E6D72845315C210604C30DA974264971421AFDB9B70EFB16C5` |
| `ui/morph_ui/server.py` | `AF0492BE6A7EF5CE8EFBA11FBCC27D9B2CE7387395DA43B6634E3474FA9C38F6` |
| `ui/morph_ui/providers/ollama.py` | `B085F48778BDF22503AF3DA1CB71A8A42468A0CCD5D338C6C898A0686936C9E5` |
| `ui/tests/test_language_gate.py` | `4FEF5E54C685EAF72434C53CD76546374D621A6B43292E750CCFDE2CC2D19A5D` |

Zusätzlich wurden die vorhandenen Grenzen von `LocalHttp`, `ComfyClient`, `SettingsStore` und dem Serverfehlerumschlag geprüft. Der MORPH-Lock kann direkte fremde Clients und externe Dateiedits nicht serialisieren. Beschädigte interne Unknown-Daten ohne eindeutigen Zielnamen benötigen gezielte Diagnose. Lesende Residenzprüfungen sind keine allgemeine VRAM-Fit-Garantie. Diese Grenzen stehen bereits im Backendbericht und sind keine neu zugesagten Fähigkeiten.
