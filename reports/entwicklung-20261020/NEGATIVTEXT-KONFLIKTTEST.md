# Echte Einzelprüfung: widersprüchlicher alter Negativtext

Nutzerauftrag 20.10.2026: „dann teste jetzt“. Getesteter Quellstand `a12bff907fb9a4a08af06ecec3767a16fb23d499`, Repository `E:\MORPH-Studio`, Branch `main`, laufende eigene UI PID 152816. Keine Produktcodeänderung und keine Wiederholung früherer Offline-/Bildprüfungen für diesen Auftrag.

## Ergebnis: FAIL für diesen Konfliktfall

Nachtrag aus der anschließenden Codeprüfung: Die gespeicherte Antwort ist der fertig aufbereitete MORPH-Vorschlag, nicht die native Ollama-Rohantwort. Der damalige Parser konnte einen vom Modell ausgelassenen Negativtext automatisch aus dem alten Formular ergänzen. Ob im konkreten alten Lauf das Modell den Text selbst lieferte oder MORPH ihn ergänzte, ist deshalb nicht belegt. Das FAIL des fertigen Vorschlags bleibt bestehen; eine eindeutige Zuweisung allein an das Sprachmodell wäre zu weitgehend. Der anschließende Fix und sein Ergebnis sind in `NEGATIVTEXT-VERTRAG.md` dokumentiert.

Genau ein neuer POST an `/api/tool-proposals`, über den vorhandenen Ollama-Provider mit bereits geladenem `gpt-oss-20b-32k:latest`. Antwort am 20.10.2026 um 23:18:25 Europe/Berlin nach 16,020 Sekunden. Keine Modellauswahl-/Lade-/Entladeaktion, kein automatischer Retry und keine Bildberechnung. Gespeicherte UI-Auswahl `huihui_ai/qwen3.5-abliterated:9b` blieb unverändert; das Ergebnis ist keine Probe dieses 9B-Modells.

| Feld | Wert |
| --- | --- |
| Neuer Auftrag | Erstelle einen präzisen Bildprompt: eine blaue Keramiktasse auf einem Tisch, ohne Auto. |
| Alter Bildprompt | Ein rotes Auto auf einer Straße. |
| Alter Negativtext | Keine blauen Gegenstände. |
| Zurückgegebener Bildprompt | Eine blaue Keramiktasse auf einem Tisch, realistisch, detailreich, natürliche Beleuchtung, keine Autos. |
| Zurückgegebener Negativtext | Keine blauen Gegenstände. |
| Vorgeschlagenes Werkzeug | sdxl |

Der neue positive Bildwunsch wird berücksichtigt. Der Ausschluss blauer Gegenstände bleibt jedoch bestehen und widerspricht weiterhin der blauen Tasse. Die ausdrücklich eingebaute Regel `negative: Auftragswidersprüche entfernen` genügte in dieser echten Probe nicht. Eine formal gültige Antwort und erfolgreicher HTTP-Aufruf sind deshalb keine fachliche Abnahme dieser Konfliktauflösung.

Ein unabhängiger Agent las ausschließlich die gespeicherte Anfrage/Antwort und bewertete denselben Fall ebenfalls **FAIL**. Keine zusätzlichen Tests, HTTP-/Modellaufrufe oder Änderungen durch diesen Agenten. Aussage ausschließlich für diesen einen Fall und dieses Modell; keine allgemeine Fehlerrate und keine Bildwirkung untersucht.

## Zustandsprüfung und Belege

Vor/nach der Probe sämtliche DB-Tabellen per vollständigem geordnetem Zeilenhash gleich: 44 Jobs, 87 Medien, 2 Projekte, 5 Versionen, keine persistierte Sprachmutation. Integrität `ok`, keine Fremdschlüsselfehler. Öffentlich ausgelesene Einstellungen gleich. Eigene UI 152816 nachher untätig, `uncertain_instances=[]`; Comfy blieb gestoppt und Port 8188 frei. Keine Modelle, DB, Bilder oder Originale als Quelländerung gestaged.

Exakte Anfrage/Antwort: `negative-conflict-request.json`, `negative-conflict-response.json`. Zustände: `negative-conflict-before.json`, `negative-conflict-after.json`; DB-Hashes: `negative-conflict-db-before.json`, `negative-conflict-db-after.json`, jeweils im selben Berichtsordner.

SHA256 Anfrage: `BC882802B5056D48990397D8E209F812EB8E5D174ABC863C4584B862FA458B40`. SHA256 Antwort: `BEAE2F28DEB3AEE63B45C3C38FE9D9045876C8FBEB9D4D6AE3C27992DE4FA947`.

Die bislang als UNVERIFIED geführte tatsächliche Befolgung ist damit für diesen Fall **nachweislich fehlgeschlagen**. Der Softwarestand zur Prompt-Ausarbeitung und Echoablehnung wird dadurch nicht zurückgesetzt; vollständige Negativtext-Konfliktauflösung ist weiterhin nicht erledigt. Keine weitere Modellanfrage und kein verdeckter Korrekturversuch. Die Behebung dieses konkreten Fehlers bleibt offen.
