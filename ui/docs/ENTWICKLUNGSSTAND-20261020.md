# Entwicklungszwischenstand vom 20.10.2026

Dieser lokale Commit sichert auf ausdruecklichen Nutzerauftrag den begonnenen Entwicklungsstand. Er ist keine Fertigmeldung fuer den vollstaendigen Auftrag.

## Enthalten
- API-basierte ComfyUI-Uebernahme, konkrete Dienstdiagnose und sichere Ergebnisimporte mit Wiederaufnahme ohne erneute Berechnung.
- Einfach/Experte, Drag&Drop und sichtbare Fehlerdetails.
- Eigene Prozessquittung fuer kontrolliertes Starten/Stoppen; uebernommene Instanzen erhalten keine Stopberechtigung.
- Additive Bildprojekte/VersionStore und begonnene Job-/API-/Frontendanbindung.
- Fuer diesen Stand erforderliche bereits vorhandene UI-/Ollama-/KREA-Quelldateien werden gemeinsam gesichert.

## Noch offen
- Phase4 Frontend: Projekt-/Versionsaktionen in app.js anschliessen. Vier neue Frontendregressionen sind deshalb erwartbar rot; 43 von47 bestehen.
- Versionsstore ueber alle Schichten pruefen und unabhaengig reviewen.
- Phasen5-9: Vergleich/Detailerhaltung, ergaenzende Ollama-/Modell-/Fortschrittsfunktionen und echte gezielte Bildabnahme.
- Vollstaendiger Abschlussbericht und Benutzerdokumentation.

## Nachweise und Grenzen
- Phase3:41/41 Frontendtests und isolierte Browserpruefung. Screenshot und Berichte liegen lokal unter E:\MORPH-Studio\reports\entwicklung-20261020.
- Starter einschliesslich sicherem Stopper:34/34 Tests beim Zwischencommit bestanden; ausschliesslich simulierte Handles/Dienste und synthetischer Test-Kindprozess.
- VersionStore:12/12 gezielte Tests; Integration jobs/routes jeweils2/2.
- Produktionsdatenbank, Modelle, Benutzereinstellungen und Pausendateien wurden bis hier nicht veraendert. Konsistente SQLite-Sicherung liegt lokal in reports\entwicklung-20261020\jobs-vor-versionierung.sqlite3 und wird nicht in Git aufgenommen.
- Kein echter Modelllauf, kein echter ComfyUI-Start/Stop und kein Push.

Die technische Elternversion bezeichnet ausschliesslich das Ausgangsbild eines Bearbeitungsschritts. Sie ist keine Inhalts- oder Promptbewertung. Modelle werden nicht veraendert.
