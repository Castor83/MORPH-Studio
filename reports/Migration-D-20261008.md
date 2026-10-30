# MORPH Studio: Umzug nach D:

Am 8. Oktober 2026 wurde die komplette lokale Installation von `V:\MORPH-Studio` nach `D:\MORPH-Studio` verschoben.

- Vor der Umstellung wurden alle 63.961 Dateien (33.528.504.433 Bytes) zwischen Quelle und Ziel mit SHA-256 verglichen: vollständig identisch. Kopierprotokoll ohne Fehler.
- Aktive Start-, Stop-, Test- und Fortsetzungspfade sowie Projektregeln und aktuelle Bedienungsdokumentation wurden auf D: angepasst.
- Git-Historie und vorhandene uncommittete Arbeiten wurden übernommen. Kein Commit oder Reset. Git vertraut ausschließlich dem ergänzten konkreten Zielpfad `D:/MORPH-Studio`; dies ist wegen exFAT ohne Dateibesitzer erforderlich.
- `PAUSE_STATE.md`, `PAUSE_SNAPSHOT.json` und historische Nachweise bleiben unverändert. Der Fortsetzungscheck vergleicht jetzt aufgelöste Ordnerpfade, damit der frühere Pfad über die Weiterleitung gültig bleibt. Fremde Projekt-Snapshots werden weiterhin abgelehnt; beide Fälle geprüft.
- `V:\MORPH-Studio` ist ausschließlich eine Junction nach D:, keine zweite Datenkopie. Der alte Datenbestand ist entfernt; rund 31,3 GiB auf V: freigegeben.
- Python und CUDA auf D: erkennen die RTX 4080. ComfyUI startet von D: mit Eingaben, Ausgaben, Temp und Benutzerordner auf D:, Offline-Modus und Listener ausschließlich `127.0.0.1:8188`. API und leere Warteschlange geprüft. Kein neuer Bild- oder Modelllauf.

Prüfmanifest, Kopierprotokolle und Migrationsprüfungen: `D:\MORPH-Studio-Migrationsprotokoll-20261008`.

Die synchronisierte ChatGPT-Projektkopie unter C: bleibt unverändert; die vollständige Arbeitsinstallation liegt auf D:.
