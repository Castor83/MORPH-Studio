# Phase7 – Ressourcenanzeige und bewusste Speicherfreigabe

Stand: 20.10.2026. Ausgangscommit `ad4551d3669f74d92e0ed955ced40cd09b80a4cf`. Umsetzung im bereits freigegebenen Checkout; kein Staging, Commit oder Push durch den Backendagenten. Fremdänderungen und vorhandene Modelle wurden nicht verändert. Ausgangsdateien samt SHA-256 stehen unter `E:\MORPH-Studio\reports\entwicklung-20261020\phase7-backend-baseline\manifest.json`.

## Verhalten

`GET /api/resources` liest ausschließlich die bestehende ComfyUI-API. Die Abfrage startet keinen Dienst und fordert weder Modellladen noch Generierung oder Speicherfreigabe an. Die tatsächliche lokale ComfyUI-Implementierung liefert unter `/system_stats` `system.ram_total`, `system.ram_free` sowie `devices[].vram_total` und `vram_free` in Byte. Die Oberfläche erhält Quelle und UTC-Zeitpunkt des erhaltenen Messwerts sowie defensiv berechnete Nutzungswerte. Fehlende, negative, nicht endliche, boolesche und widersprüchliche Zahlen werden nicht als gültige Messungen ausgegeben. Nicht erreichbare oder unlesbare Statusdaten liefern einen normalen Ressourcenbeleg mit `available:false`, leeren Geräten und unbekannten Werten. Rohdaten wie `system.argv` werden nicht ausgegeben. Geladene Modellnamen bleiben ausdrücklich `model_state:'unknown'`; die Historie zuletzt verwendeter Modelle ist kein Ladebeleg.

Vertrag: `{available, measured_at, source, devices:[{name,type,index,vram_total,vram_free,vram_used}], ram:{total,free,used}, model_state:'unknown', unload:{allowed,reason}, error?}`. Zahlen sind Bytewerte oder `null`; bei fehlender Messung ist `measured_at:null`. `source` lautet `ComfyUI /system_stats`.

`POST /api/resources/free` verlangt `{}` und den bestehenden lokalen Host-/Origin-/Aktionsschutz. Die Aktion hält den Joblock, liest alle gespeicherten Aufträge und sperrt bei aktiven, ungeklärten, unbekannten oder beschädigten Einträgen; die Grenze der letzten 30 angezeigten Aufträge wird nicht verwendet. Sie akzeptiert ausschließlich den quittierten lokalen HTTP-Endpunkt. Die Guardprüfung verlangt die aktuelle eigene Managementquittung mit korrekter Version, Projekt, Interpreter, Skript, PID und genauer Windows-FILETIME. Ein neuer Query-/Synchronize-Handle besitzt ausdrücklich kein Terminate-Recht. Prozesslebenszeit, laufende Interpreterdatei, vollständiges Startprofil und aktuelle Listener-PID müssen übereinstimmen. Derselbe Handle bleibt durch die Prüfung und den HTTP-Aufruf offen und wird danach geschlossen. Zwischen zwei Queueprüfungen und auch nach der letzten Queueprüfung wird der Listener erneut nachgewiesen. Busy-/unlesbare Queue und beobachtbare Identitätswechsel sperren die Aktion. Der Stopper wird hierfür nie aufgerufen.

Eine erfolgreiche Anfrage setzt ausschließlich die vorhandenen ComfyUI-Flags `unload_models:true` und `free_memory:true`. Die Antwort lautet `{accepted:true, completed:false, message:'Freigabe angefordert'}`. Die lokal gelesene ComfyUI-Implementierung verarbeitet diese Flags erst später in ihrem Worker. Deshalb ist HTTP 200 kein Beweis einer abgeschlossenen Entladung oder eines bestimmten VRAM-Gewinns. Es gibt keine automatische Entladung bei Compute und keinen automatischen Wiederholungsversuch bei Zeitüberschreitungen. Backendfehler werden ohne fremde Rohdetails weitergegeben; die Meldung bewahrt den unbestätigten Zustand. Ollama, andere Instanzen und fremde Modelle erhalten keine Aktion.

## Dateien

- `E:\MORPH-Studio\ui\morph_ui\resources.py`: defensive, öffentliche Messwertdarstellung ohne Historienableitungen.
- `E:\MORPH-Studio\ui\morph_ui\comfy.py`: reine Messwertabfrage, lesender Managementnachweis und einmalige ausdrückliche Freigabeanforderung.
- `E:\MORPH-Studio\ui\morph_ui\jobs.py`: alle gespeicherten Aufträge und gemeinsamer Joblock.
- `E:\MORPH-Studio\ui\morph_ui\server.py`: zwei Routen und Freigabe des neuen statischen Frontendmoduls `resources.js`.
- `E:\MORPH-Studio\tools\lmstudio-wan-chat\start_mcp.py`: gemeinsam verwendeter strenger Quittungsleser und neue rein lesende Prozess-/Listenerprüfung. Die bestehende Stop-Funktion behält ihren separaten Terminate-Handle und unveränderten Stopablauf.
- `E:\MORPH-Studio\ui\tests\test_resources.py` und `E:\MORPH-Studio\tools\lmstudio-wan-chat\tests\test_resource_guard.py`: neue gezielte Tests.

## Prüfungen und Belege

Alle folgenden Nachweise verwenden künstliche Messwerte, temporäre Datenbanken, simulierte native Prozessfunktionen oder lokale HTTP-Testserver. Keine echte Ressourcenabfrage, keine GPU-Abfrage, kein Modelllauf und kein tatsächliches `/free` oder Prozessbeenden wurden für diese Phase ausgeführt.

- `phase7-backend-red.log`: zunächst 12 fehlgeschlagene neue Ressourcenfälle wegen fehlender Methoden und HTTP-Routen.
- `phase7-guard-red.log`: vier fehlgeschlagene Guardfälle wegen fehlender lesender Managementprüfung.
- `phase7-target-binding-red.log`: eigener 8188-Prozessbeleg autorisierte zunächst einen abweichenden HTTP-Endpunkt; Regression reproduziert und Endpunktbindung ergänzt.
- `phase7-error-red.log` und `phase7-error-green.log`: rohe Backendfehlerdetails zunächst sichtbar; nach Korrektur vier gezielte Fehler-/Freigabeprüfungen bestanden.
- `phase7-final-listener-red.log`: unabhängiger Reviewbefund als reproduzierbarer Fehler – Portbesitzerwechsel während der letzten Queueabfrage wurde zunächst nicht erneut geprüft. Abschließende Listenerprüfung ergänzt.
- `phase7-backend-final.log`: **15 Tests bestanden, 0 Fehler, 4.280 Sekunden**. Enthält alle Zustände aus ACTIVE, einen älteren offenen Auftrag jenseits von 30 jüngeren abgeschlossenen Aufträgen, beschädigte Einträge, Busy-/ungültige Queue, Eigentums-/Endpunktwechsel, Lockserialisierung, unveränderte Offlinebedienung und ausschließlich angenommene Freigabe.
- `phase7-guard-green.log`: **4 Tests bestanden, 0 Fehler, 0.009 Sekunden**. Quittung, Query-Rechte, PID-/FILETIME-/Interpreter-/Listenerwechsel, Handle-Schließen und Schreib-/Start-/Stopfreiheit geprüft.
- `phase7-stop-regression.log`: **34 vorhandene Start-/Stop-/Adoptionstests bestanden, 0 Fehler, 2.099 Sekunden**. Keine Erweiterung der Stopbefugnisse.
- `phase7-adjacent-green.log`: **46 angrenzende Tests bestanden, 0 Fehler, 114.209 Sekunden** (`test_jobs`, `test_server`, `test_comfy_service`, `test_edit_region`). Vorhandene Bereichsmasken-/Kompositions- und Alphaprüfungen bleiben grün. Der letzte lokale Patch betrifft ausschließlich die endgültige Ressourcenfreigabeprüfung und wurde anschließend von der vollständigen aktuellen 15er-Ressourcensuite geprüft.

`phase7-backend-tested.json` bindet die getestete Backendfassung über SHA-256 an die Dateien. Python meldet in den ausführlichen Logs teilweise langsame asyncio-Fixtureabschnitte; die Testläufe schließen mit `OK`, ohne fehlgeschlagene Behauptungen oder Testfehler.

## Verbleibende Grenzen und nächster Schritt

Die reguläre ComfyUI-API bietet keine atomare Operation „prüfe Queue und Prozessidentität und entlade“. Direkte ComfyUI-Nutzer umgehen den MORPH-Joblock; ein neuer Auftrag oder Listenerwechsel nach der letzten Prüfung ist damit technisch nicht vollständig auszuschließen. Die vorhandenen globalen Free-Flags haben keinen unabhängigen Abschlussbeleg. Solche Grenzen werden nicht durch synthetische Tests zu einer Garantie erklärt. Kompatible oder übernommene Instanzen ohne aktuelle eigene Quittung bleiben gesperrt.

Die echte Windows-Handleausführung und das tatsächliche Speicherverhalten bleiben für die angekündigte Phase9-Abnahme offen. Unmittelbar nächster Schritt: unabhängigen Review der aktuellen Dateien und Belege abschließen; danach entscheidet ausschließlich der Hauptchat über den freigegebenen Blockcommit und die Fortsetzung mit Phase8. Keine weiteren Backendmutationen bis zu einem konkreten Reviewbefund.
