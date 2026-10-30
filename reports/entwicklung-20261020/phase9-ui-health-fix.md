# Echter UI-Start: Diagnose und gezielte Korrektur

Erster echter Start über `start-morph-ui.ps1 -NoBrowser`: Prozess 120292 lief korrekt, der Starter meldete trotzdem fehlende Bestätigung. Gespeicherte gültige `/api/status`-Antwort nach 3.272s überschritt das HTTP-Limit von 3s. Status wartet auf Comfy-API-/Listenerdiagnose; die genaue Zeitaufteilung wurde nicht gemessen. Kein zweiter Dienst gestartet.

Korrektur: neuer GET `/api/health` liefert ausschließlich App, Version, PID und Projektpfad. Starter nutzt diesen. Die bestehenden Identitäts-, Listener- und Erstellungszeitprüfungen bleiben erhalten; Hostschutz gilt weiterhin. Kein längeres blindes Timeout und keine Änderung der Rechendienstprüfung.

Gezielte Regression: neuer Fall zuerst RED (404), danach Server- und Neustartmodule zusammen 10/10 PASS in 13.275s, Exit0. Der neue Test verbietet Comfy-/Settings-/Platzabfragen und prüft Identitätsdaten sowie Fremdhost-Ablehnung. Ein erster Aufruf der Einzelprüfung konnte wegen des isolierten Embedded-Python-Suchpfads das Testmodul nicht importieren; nach explizitem Testpfad folgte der tatsächliche RED-Beleg. Keine Produktsuite erneut zur Orientierung ausgeführt.

Frischer unabhängiger Gegencheck von Agent reactor_final_check: kein Befund im begrenzten Diff. Anschließend ausschließlich eigene untätige UI nach Prozess-/API-/Receipt-/Listenerbindung und bestätigtem prepare-restart neu gestartet. Erster manueller Identitätsguard stoppte vor Mutation, weil PowerShell JSON-Datumsstrings als DateTime liest; zeittypgerechter Vergleich bestätigte die Identität. Keine fremden Prozesse gestoppt. Neuer echter NoBrowser-Start: Exit0 und bestätigte Bereitschaft; frische Healthantwort und Zeit in `phase9-ui-health-live.json`.

Migration ebenfalls echt geprüft: `phase9-live-migration.json`, alle ursprünglichen 38 Aufträge/71 Medien zeilenweise unverändert. Automatisches Migrationsbackup exakt gleich zur vorherigen konsistenten Sicherung; Integrität ok. DB/Backups werden nicht committed.

Belege: `phase9-ui-health-red.log`, `phase9-ui-health-green.log`, `phase9-ui-controlled-restart.json`, `phase9-ui-health-live.json`, `phase9-live-migration.json`. Die vorherigen 285/107/38 Gesamtbelege beziehen sich auf 5b2c00d. Für diesen engen zusätzlichen Fix gilt der neue 10-Fälle-Beleg plus echter Start, keine behauptete erneute Gesamtabnahme.

Nächster Schritt: angekündigter einzelner deutscher KREA-Werkzeugvorschlag über das vorhandene gewählte 9B-Modell, anschließend getrennt angekündigte eigene Modellfreigabe. Keine automatische Bildberechnung.
