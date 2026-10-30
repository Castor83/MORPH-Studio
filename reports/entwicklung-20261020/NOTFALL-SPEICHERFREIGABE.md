# Notfall-Schaltfläche für Bildspeicher

Nutzerauftrag20.10.2026: „Speicher freigeben für den notfall einen button einrichten“. Umsetzung im bestehenden `E:\MORPH-Studio`, Branch main; Sourcecommit `c5b1fa7`. Kein Push. Bestehende Fremdänderungen bleiben erhalten.

## Verhalten

Unter **Rechendienst · Speicher** steht jetzt sichtbar **Notfall: Speicher vollständig freigeben**, auch bei eingeklappten Ressourcendetails. Die Erklärung nennt die Wirkung vor dem Klick: eigenen untätigen ComfyUI-Dienst beenden, Modell-/ReActor-/ONNX-Caches dieses Prozesses dadurch verwerfen. Er bleibt gestoppt; erst ein nächster bewusst gestarteter Bildauftrag nutzt den vorhandenen Start bei Bedarf. Kein sofortiges Nachladen, keine neue Bildberechnung oder Installation. Ollama ist kein Ziel dieser Aktion.

Dies ergänzt die normale asynchrone Freigabe. Diese kann PyTorch-/Comfy-Modelle freigeben, ließ beim vorangegangenen ReActor-Lauf jedoch32MiB PyTorch-Reservierung sowie zusätzliche Prozessreserven zurück. Der neue Weg beendet den gesamten genau zugeordneten eigenen Rechendienst. Er gibt keine fremden Prozesse oder deren GPU-Speicher frei.

## Schutz und Umsetzung

Expliziter einzelner POST `{}` an `/api/resources/emergency-release`. Bestehender Host-/Origin-/Aktionsheader-Schutz; keine übergebenen PIDs/Modellangaben zulässig. Geteilte MORPH-Sperre, Prüfung aller gespeicherten Aufträge einschließlich älterer/unklarer/beschädigter Zeilen, laufender Sprache und persistierter eigener Sprach-Unknowns. Geladene untätige Ollama-Modelle sind keine neue Blockade; keine Abhängigkeit von dessen Inventar.

StartLock bleibt über zwei frische Queueprüfungen, quittungsgebundenes TERMINATE-Handle, Erstellungszeit-/Exe-/Listenerverifikation, Prozessende und Portnachweis gehalten. Gestoppt wird dasselbe geprüfte Prozessobjekt, kein nachträglich anhand einer PID neu gesuchter Prozess. Erfolg erst bei bestätigtem Ende und freiem Port. Bei Listenerwechsel oder unbestätigtem Ausgang sichtbarer Fehler ohne zweiten Stop oder automatische Wiederholung. Clientabbruch gibt die MORPH-Sperre nicht frei, solange der native Stop noch läuft. Ressourcenanzeige lehnt Freigabe auch bei Sprach-Unknown ab.

Grenze: Direkte fremde Clients können außerhalb der MORPH-Sperre zwischen letzter Queueprüfung und Stop Aufträge an denselben Dienst senden. Die Prozessbindung verhindert das Stoppen eines anderen Prozesses; sie ist keine atomare Sperre für sämtliche fremden Clients.

Dateien: `E:\MORPH-Studio\ui\frontend\resources.js`, `styles.css`, `ui\README.md`; `E:\MORPH-Studio\ui\morph_ui\comfy.py`, `jobs.py`, `server.py`; `E:\MORPH-Studio\tools\lmstudio-wan-chat\start_mcp.py`. Neue Fälle in `E:\MORPH-Studio\ui\tests\test_emergency_release.py` und `resources.test.mjs`.

## Prüfungen

- UI zuerst3 neue Fälle RED, danach Ressourcen-/App-Module72/72 PASS, Exit0.
- Backend zuerst14 Fälle mit erwarteten Fehlern RED; zusätzliche Ressourcen-Unknown-Lücke gezielt RED. Finale neue/angrenzende Ressourcen-/Sprachgate-Module52/52 PASS,46.586s, Exit0.
- Passendes Startermodul34/34 PASS,1.071s, Exit0. Keine erneute gesamte Backend-/Frontendregression oder Modellvergleichsserie.
- Unabhängiger UI-Lesecheck ohne wesentlichen Befund. Backend von anderem Agenten implementiert, Hauptagent las den finalen Diff gesondert. Fünf Backenddateien exakt gegen final getestete SHA256 abgeglichen; `emergency-tested-hashes.json`. Code-/Dokumentations-Diffcheck bestanden. Rohe Logs unverändert.

Ein anfänglicher Testimportaufruf wurde korrigiert; dies war kein Produktfehler. Zwei nicht passende Patchkontexte wurden vor jeder Änderung abgewiesen und mit zutreffendem Kontext angewendet. Keine Tests oder Codeänderungen dadurch als abgeschlossen ausgegeben.

## Echte Einzelprüfung

Vorher UI103344/Comfy107180, gültige eigene Quittung, leere Backendqueue, keine ungelösten MORPH-Aufträge oder Sprachaktionen. Die eigene Oberfläche kontrolliert mit bestehendem `start-morph-ui.ps1 -NoBrowser -Restart` auf UI142056 aktualisiert; Comfy dabei nicht neu gestartet. Danach genau ein bewusster Klick auf die neue Taste.

Ergebnis: Comfy107180 beendet, eigene Quittung stopped/managed=false, Port8188 frei; native Kontrollabfrage bestätigte fehlenden Prozess und Listener mit Exit0. UI zeigt bestätigtes Ende; Taste danach gesperrt. Kein automatischer zweiter Versuch und kein neuer Comfy-Start. `Ressourcen derzeit nicht verfügbar` ist bei gestopptem Messdienst erwartbar.

DB vor/nachher vollständig zeilenweise gleich, Integrität ok:43 Jobs/85 Medien. Keine Bild-, Modell-, Original- oder DB-Dateien geändert. Der erste kombinierte Nachweisaufruf endete wegen der erwartbar nicht vorhandenen Prozess-/Listenerobjekte mit Shellstatus1; seine JSON-Prüfungen waren erfolgreich. Der ausdrückliche negative Kontrollbeleg `emergency-native-exit-proof.json` bestätigt beide Abwesenheiten mit Exit0.

Ollama-Inventar wurde ausschließlich gelesen. Zwischen Vorher-/Nachhermessung erschien ein6.05GB-GPU-Sprachmodell; die Notfallroute selbst fragt Ollama weder ab noch lädt/entlädt sie Modelle. Der auslösende andere Client wurde nicht bestimmt. Daher **keine unveränderte globale GPU-/Ollama-Belegung behauptet**. Die NVIDIA-Gesamtbelegung stieg in diesem Zeitfenster; vollständige Freigabe der gesamten GPU ist nicht Ziel oder Ergebnis dieser prozessgebundenen Aktion.

Belege unter `E:\MORPH-Studio\reports\entwicklung-20261020\`: `emergency-live-before.json`, `emergency-live-after.json`, `emergency-native-exit-proof.json`, `emergency-button-ui-live.json`, Screenshot `emergency-button-live.png` und die roten/grünen Testlogs. Baseline der ursprünglichen committed Quelldateien in `emergency-button-baseline`; kein DB-Backup erforderlich, da keine Schema-/Datenmigration. Bilder, DB, Modelle, mutable Quittungen und Baselinekopien bleiben außerhalb des neuen Quellcommits.

Abgeschlossen: Button implementiert, gezielt offline und einmal echt geprüft. Comfy ist absichtlich gestoppt. Das vorhandene Starten bei nächster Bildberechnung blieb unverändert und wurde nicht durch eine zusätzliche Inferenz erneut getestet.
