# Negativtext: explizite Modellangabe statt stiller Altübernahme

Stand 20.10.2026 gegen 23:26 Europe/Berlin. Arbeitsbereich `E:\MORPH-Studio`, `main`, Ausgangscommit `89c15a4a14e36fa5993ac658d8ba1ebe1b0b6f39`. Nutzerfrage nach dem fehlgeschlagenen Konflikttest: „und jetzt wie weiter“. Enger Routinefix innerhalb des bestehenden Entwicklungsauftrags; keine neue allgemeine Architektur oder Modellauswahl.

## Gesicherte Ursache und Aussagegrenze des alten Tests

`ToolPlanning.parse()` begann mit sämtlichen aktuellen Formularwerten und überlagerte sie mit den vom Sprachmodell gelieferten Änderungen. Das Antwortschema ließ `controls.negative` bislang weg. Wenn die Modellantwort keinen Negativtext enthielt, ergänzte MORPH deshalb den alten. Die Codeprüfung und der neue rote Regressionstest belegen diesen Fehlerpfad.

Der vorherige Livebeleg in `NEGATIVTEXT-KONFLIKTTEST.md` ist die bereits aufbereitete MORPH-Antwort, keine native Ollama-Rohantwort. Sein fachliches FAIL bleibt bestehen. Ob dort das Modell den alten Ausschluss ausdrücklich lieferte oder MORPH ihn bei fehlender Angabe ergänzte, bleibt UNVERIFIED. Eine eindeutige Zuweisung allein an das Sprachmodell war zu weitgehend; der alte Bericht enthält jetzt diesen ausdrücklichen Nachtrag.

## Schmale Korrektur

- Antwortschema fordert `controls.negative` für SDXL, WAN und Qwen21 ausdrücklich. Leertext ist gültig; diese drei Werkzeuge besitzen ein Negativfeld. Andere Werkzeuge bekommen kein zusätzliches Feld.
- Parser verlangt dieselbe Angabe **vor** dem Überlagern der aktuellen Werte. Fehlt sie, wird der gesamte Vorschlag als unvollständig abgewiesen; kein alter Negativtext wird als Ersatz übernommen.
- Ein ausdrücklich leerer oder neuer Negativtext ersetzt den bisherigen. Die Modellanweisung verlangt eine neue Angabe, gegebenenfalls leer, und die Entfernung von Auftragswidersprüchen.
- `self.current`, Einstellungen, WAN-Kopplung, Modellbindungen, Rollenfolge, vollständiger alter Nutzerkontext und unveränderter neuer Auftrag bleiben erhalten. Weiterhin 8.192 Bytes vor I/O, Kontext 4.096, Ausgabe 1.024, ein Call ohne Retry. Keine automatische Übernahme oder Bildberechnung.
- Geänderte Quellen: `ui\morph_ui\tool_planning.py`, Tests `ui\tests\test_tool_proposals.py`; kurze Bedienerklärung in `ui\README.md`.

Dies ist eine technische Vollständigkeitsprüfung. Ein vom Modell ausdrücklich gelieferter, inhaltlich widersprüchlicher Negativtext ist damit nicht generell erkennbar. Die Formprüfung wird nicht als semantischer Beweis ausgegeben.

## Prüfung

Neue Regression zuerst RED: zwei Tests, zwei erwartete Providerfehler für die bisher erlaubte fehlende Negativangabe; expliziter Leer-/Ersatztext war bereits gültig. `negative-contract-red.log`. Gültige synthetische Planfixtures liefern jetzt den vorgeschriebenen Negativtext mit; der Fehlendtest entfernt ihn ausdrücklich.

Finale vier betroffene Pythonmodule **60/60 PASS, Exit 0, 19,324 s**, `negative-contract-green.log`. Schema und manueller Parser für beide Provider, kein Retry, Leer-/Ersatztext, bestehende Standard-/exakte Bytegrenze, WAN, Profile, Prompt-Ausarbeitung und Echoablehnung abgedeckt. Projektlokaler Embedded Python, keine Modelllast durch diese Tests. Keine unveränderte ganze UI-/Phase-9-Suite erneut ausgeführt. Dateihashes `negative-contract-tested-hashes.json`; nach dieser Prüfung keine weitere Logikänderung.

Unabhängiger frischer Quellenreview: keine konkreten Findings. Er bestätigte die übereinstimmende Pflichtangabe in Schema/Parser und die erhaltene String-/Längenvalidierung. Keine eigenen Tests oder Modellaktionen dieses Reviewers. Quell-/Dokumentationsdiffcheck erfolgreich; rohe Testlogs unverändert erhalten.

## Genau eine echte Probe nach der konkreten Korrektur

Eigene untätige UI kontrolliert aktualisiert: 152816 → 155060, Starter Exit 0. Bestehender Comfy-Dienst blieb gestoppt, 8188 frei. Eine Anfrage über `/api/tool-proposals` mit bereits geladenem `gpt-oss-20b-32k:latest`; keine Lade-/Entlade-/Auswahlaktion. Gespeicherte UI-Wahl `huihui_ai/qwen3.5-abliterated:9b` unverändert, keine Aussage über dieses nicht getestete Modell.

Identischer fachlicher Testinhalt: neuer Wunsch blaue Keramiktasse auf einem Tisch ohne Auto; alter Bildprompt rotes Auto auf Straße; alter Negativtext „Keine blauen Gegenstände.“. Antwort am 20.10.2026 um 23:25:42 Berlin, 15,435 s:

- Werkzeug: `sdxl`.
- Positivprompt: **„Eine blaue Keramiktasse aus feinem Porzellan, auf einem Holztisch, ohne Auto im Bild.“**
- Negativtext: **„Kein Auto.“**

**PASS für die Negativtext-Konfliktauflösung dieses Einzelfalls.** Der Ausschluss blauer Gegenstände wurde ersetzt; positiver Wunsch und Negativtext widersprechen sich hier nicht. Ein unabhängiger Agent bestätigte diese Bewertung anhand der gespeicherten Anfrage/Antwort, ohne weitere Ausführung. Zusatzdetails Porzellan/Holztisch waren nicht ausdrücklich verlangt: keine allgemeine Promptqualitätsabnahme und keine Bildbewertung.

Exakte Belege: `negative-contract-live-request.json`, `negative-contract-live-response.json`; SHA256 Anfrage `92E28AED9287E9F50701D0CABD7CD2BAFBE84E4BD6C5923F144F0EC299DF8B04`, Antwort `404141BDC7264AC13004648C058104F7C40BD5C7EC38C65F0A046F125F36E9D5`.

## Daten und Schlusszustand

Alle DB-Tabellen vor/nach der Probe vollständig per geordnetem Zeilenhash gleich: 44 Jobs, 87 Medien, zwei Projekte/fünf Versionen, keine persistierte Sprachmutation; Integrität ok, keine Fremdschlüsselfehler. Öffentliche Einstellungen gleich. Eigene UI 155060 anschließend untätig, `uncertain_instances=[]`; Comfy gestoppt/8188 frei. Belege `negative-contract-before.json`, `negative-contract-after.json`, `negative-contract-db-before.json`, `negative-contract-db-after.json`, `negative-contract-restart.log`.

Fix implementiert, geprüft und im laufenden Dienst aktiv. Kein weiterer Modellversuch, Bildstart, Modellwechsel, Datenmigration oder neue Automation. Fremdänderungen und frühere Löschungen bleiben außerhalb dieses selektiven Commits; keine Modelle, Originale, Bilder, aktive DB oder mutable Übergabestatusdateien gestaged. Allgemeine semantische Zuverlässigkeit bleibt eine Grenze; der frühere FAIL wird weder gelöscht noch rückwirkend zu PASS umgeschrieben.
