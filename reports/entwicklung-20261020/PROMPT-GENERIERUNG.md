# Prompt-Ausarbeitung statt bloßer Befehlswiederholung

Stand 20.10.2026, etwa 23:14 Europe/Berlin. Repository `E:\MORPH-Studio`, `main`, Ausgangscommit `c1a1a748899dda51355979f4d3f9efae7d41c81f`, kein Remote/Push. Fortsetzung der bestehenden Routinefreigabe. Der Nutzerbefund gilt als Tatsache: Die Prompt-Hilfe wiederholt den Befehl statt einen Bildprompt auszuarbeiten. Die vorherige Anzeige-/Prioritätskorrektur allein erfüllte dieses Ziel nicht. Keine erneute Untersuchung oder Ausführung des privaten Nutzerbeispiels.

## Änderung

`ui\morph_ui\tool_planning.py` verlangt jetzt ausdrücklich fertige Prompts: Bildbeschreibung bei Erstellung, Zieländerung plus Erhaltungsumfang bei Bildbearbeitung, Bewegung/Kamera und Erhalt bei Video. Ein kurzes neutrales Editbeispiel zeigt die gewünschte Ausarbeitung. Nicht genannte Bilddetails dürfen weiterhin nicht erfunden werden.

Um den Platz innerhalb derselben 8.192 Bytes zu schaffen, entfallen lediglich die redundanten Katalog-Fließtextbeschreibungen in der Modellnachricht. Werkzeugnamen, ausgewählte Familienprofile, Bildrollen, Defaults, Schrittweiten und aktuelle Einstellungen bleiben erhalten. Der eigentliche UI-Katalog wird nicht geändert. Schema, vollständiger alter Textkontext, unveränderter letzter Auftrag, Parameter, Grenzen, `self.current`, WAN-Kopplung und beide Providerpfade bleiben unverändert.

Ein strukturell gültiger Einzelvorschlag mit Promptfeld wird als `proposal_echo` abgewiesen, wenn sein Prompt nach Groß-/Kleinschreibung und Leerraum exakt dem neuen Auftrag entspricht. Die Meldung sagt klar, dass nur wiederholt und nichts übernommen wurde. Keine automatische Wiederholung, Übernahme oder Bildberechnung. ReActor-Leerprompts, Mehrschrittpläne und alte Prompts für reine Einstellungsänderungen werden nicht generell blockiert. Dies ist eine enge Kopiererkennung, keine semantische Qualitätsprüfung und keine Erkennung beliebiger schlechter Paraphrasen.

## Prüfung

- Neue gezielte Fälle zuerst RED: drei Tests, fünf erwartete Assertionsfehler für fehlende Ausarbeitungsanweisung und Echoablehnung; reine Einstellungen/Mehrschritte blieben gültig. `prompt-generation-red.log`.
- Finale vier betroffene Pythonmodule mit projektlokalem Embedded Python: **58/58 PASS, Exit 0, 19,049 s**, `prompt-generation-green.log`. Beide Provider, normalisierte Kopien, einmaliger Chatcall ohne Retry, vollständige Nachrichten, Profile, Standard-/exakte Bytegrenze vor I/O, WAN und Parsefehlerbehandlung abgedeckt.
- Unabhängiger frischer Read-only-Diffcheck: keine konkreten P1/P2/P3-Befunde. Er bestätigte die geschützte Validierung vor der neuen Echo-Prüfung und den erhaltenen Katalogumfang. Keine unabhängige zweite Test- oder Modellserie behauptet.
- Keine Frontendlogik geändert; die vorherigen 69 UI-/Controllerprüfungen wurden nicht erneut ausgeführt. `git diff --check` der neuen Quellen und Dokumentation erfolgreich. Rohlogs bleiben unverändert, einschließlich etwaiger Testausgabe-Leerzeichen. Dateihashes in `prompt-generation-tested-hashes.json`.

## Eine echte Korrekturprüfung

Eigene untätige UI mit vorhandenem Starter aktualisiert: PID 146872 → 152816. Comfy blieb gestoppt/8188 frei. Genau ein neuer neutraler Korrekturtest nach dieser konkreten Änderung; keine Wiederholung des alten Tassenfalls und kein Vergleichslauf. Bereits geladenes `gpt-oss-20b-32k:latest` über `/api/tool-proposals` verwendet; gespeicherte Auswahl weiterhin `huihui_ai/qwen3.5-abliterated:9b`, keine Auswahl-/Lade-/Entladeaktion.

Auftrag: **„Mach nur den Rucksack dunkelgrün.“** Alter Kontext: gelber Rucksack neben einer Parkbank. Antwort nach 13,741 s am 20.10.2026 gegen 23:14 Berlin: vorgeschlagenes Werkzeug `kontext`, Prompt **„Färbe nur den Rucksack dunkelgrün. Erhalte Form, Licht, Hintergrund und Bildausschnitt.“**

**PASS für diese enge Ausarbeitung:** Der zurückgelieferte Text formuliert die gewünschte Änderung samt Erhaltungsumfang; er ist keine wortgleiche Befehlsrückgabe. Werkzeugwechsel wurde nur vorgeschlagen, nicht übernommen. Kein Bild gestartet und kein privates Nutzerbild verwendet. Exakte Belege `prompt-generation-live-request.json`, `prompt-generation-live-response.json`, `prompt-generation-before.json`, `prompt-generation-after.json`, `prompt-generation-restart.log`.

Alle DB-Tabellen vor/nach der Probe vollständig per geordnetem Zeilenhash gleich: 44 Jobs, 87 Medien, zwei Bildprojekte/fünf Versionen; Integrität ok, keine Fremdschlüsselfehler, keine offene Sprachmutation. Öffentliche Einstellungen gleich. `prompt-generation-db-before.json`, `prompt-generation-db-after.json`. Abschließend eigene UI 152816 bereit, Sprache untätig, Comfy gestoppt. Kein neuer Prozess-/Modell-/Bildmarathon, keine neue Automation.

## Abschluss und Grenzen

Der konkrete Softwareblock ist implementiert, gezielt geprüft und im eigenen laufenden Dienst aktiv. Die zuvor korrigierte Vorschlagsanzeige wird nach Neuladen der Browserseite verwendet. Beide Eingabefelder und die getrennten Übernahme-/Startaktionen bleiben erhalten. Fremdänderungen, alte Löschungen, Modelle, DB, Bilder und mutable Übergabestatusdateien bleiben außerhalb dieses Commits.

Die einzelne echte Ausarbeitung ist kein Nachweis für jede Modellfamilie, jedes Motiv oder allgemeine Promptqualität. Die im Vorgängerbericht `PROMPT-AUFTRAG-PRIORITAET.md` beobachtete Schwäche bei widersprüchlichen alten Negativtexten wurde hier nicht erneut echt geprüft; die explizite Korrekturregel bleibt vorhanden, ihre allgemeine Zuverlässigkeit **UNVERIFIED**. Auch nicht wortgleiche schwache Paraphrasen und semantische Mehrschrittqualität sind nicht durch den engen Echo-Guard abgesichert. Keine vollständige erneute Phase-9-/Bildabnahme behauptet.
