# MORPH Studio: Nachtrag zur sicheren Dienstverwaltung

Stand: 20.10.2026. Lokaler Zwischencommit: `dfaf115` (`WIP: Stabilize MORPH services and begin persistent image history`).

## Änderung und Zweck

Eine erreichbare, kompatible lokale ComfyUI-API kann MORPH unabhängig vom ursprünglichen Starter verwenden. Daraus entsteht keine Berechtigung, deren Prozess zu beenden. Der frühere Stopper prüfte lediglich den Python-Pfad und ein grobes Befehlsmuster; diese Auswahl über den Port wurde entfernt.

- `E:\MORPH-Studio\tools\lmstudio-wan-chat\start_mcp.py`: Eigene Starts erhalten eine separate atomar geschriebene Quittung unter `E:\MORPH-Studio\reports\wan-lmstudio\mcp-comfy-owned.json`. Sie enthält PID, Windows-Erstellungszeit als exakten FILETIME-Text, Projektpfad, Interpreter, Skriptpfad und Verwaltungsstatus. Die Erstellungszeit stammt unmittelbar vom ursprünglichen Popen-Prozesshandle. Misslingt die sichere Erfassung, bleibt der gestartete Dienst ohne Stopberechtigung. Eine spätere API-Übernahme überschreibt diese Quittung nicht.
- `E:\MORPH-Studio\stop-morph.ps1`: Ruft ausschließlich den Guard mit `--stop-managed` auf. Der Guard verlangt eine gültige eigene Quittung, vergleicht die Erstellungszeit und den Interpreter am geöffneten Prozesshandle und prüft die exakten Projektargumente. Er beendet ausschließlich den geprüften Handle. Es gibt keinen Ersatzweg über Portsuche, Prozessnamen oder eine alleinige PID. Fehlende, alte, bereits abgeschlossene oder widersprüchliche Belege führen zu einer erklärten Ablehnung.
- `E:\MORPH-Studio\start-morph.ps1`: Verwendet denselben Guard mit `--start-only`. Damit laufen auch Starts über `MORPH-Start.cmd` durch Synchronisierung, API-Prüfung und eigene Quittierung. Dieser Modus startet keinen MCP-Server. Der Rechendienst läuft im Hintergrund; das Startfenster ist danach nicht sein Lebenszyklus.
- `E:\MORPH-Studio\tools\lmstudio-wan-chat\tests\test_start_mcp.py`: Regressionen für gültige und ungültige Quittungen, PID-Wiederverwendung mit anderer Erstellungszeit, abweichendes Startprofil, fehlgeschlagene Erfassung, unveränderte Quittung bei API-Übernahme und getrennte Start-/Stop-Modi. PowerShell-Funktionen werden mit ersetztem Guardaufruf geprüft.

Start und Stop verwenden dieselbe Startsperre. Ein erfolgreicher Stop markiert die Quittung als abgeschlossen; sie wird nicht gelöscht. Historische Dienste ohne neue vollständige Quittung bleiben unangetastet. Für sie wird keine nachträgliche Berechtigung allein aus PID oder API-Antwort abgeleitet.

## Sicherung und Prüfung

Die vier Ausgangsdateien wurden vor diesem Nachtrag separat unter `E:\MORPH-Studio\reports\entwicklung-20261020\stopper-baseline` gesichert. `manifest.json` enthält ihre absoluten Pfade und SHA-256-Werte. Frühere Sicherungen wurden nicht überschrieben.

Vorhandene Prüfnachweise:

- `stopper-red.log` und `stopper-green.log`: neue Managementregressionen zunächst fehlgeschlagen, anschließend zusammen mit den bisherigen Guardtests bestanden.
- `stopper-wrapper-red.log` und `stopper-wrapper-green.log`: PowerShell-Aufrufer zunächst fehlend, anschließend mit simuliertem Guardaufruf bestanden.
- `zwischencommit-starter.log`: vollständiger gemeinsamer Lauf mit **34 Tests, 0 Fehlern, OK**. Der Nachtrag übernimmt dieses nachgelesene Ergebnis; für den Bericht wurden keine Tests wiederholt.

Die Stoptests verwenden künstliche Prozesshandles und ersetzte native Funktionen. Der bestehende Startertest verwendet ausschließlich eine erzeugte synthetische `main.py` in einem temporären Testprojekt. Es wurden weder ein echter ComfyUI-Dienst noch ein Modell gestartet oder ein echter Dienst beendet. Ein tatsächlicher Stop und die native Windows-Ausführung bleiben damit praktisch ungetestet; die Regressionen belegen die geprüften Entscheidungs- und Identitätsgrenzen.

## Bedienung und nächster Schritt

`MORPH-Start.cmd` stellt die lokale API über den Guard bereit oder übernimmt eine passende vorhandene API. `MORPH-Stop.cmd` beendet ausschließlich einen passend quittierten eigenen Start; die Meldung einer Ablehnung ist kein Anlass für einen breiteren Prozessstopp.

Nächster Schritt: den Nachtrag im weiteren Integrationsstand berücksichtigen und die Bildhistorie unabhängig auf Datenintegrität und Wiederaufnahme prüfen. Für die Dienstverwaltung sind keine weiteren Modellläufe oder Prozessaktionen aus diesem Bericht abgeleitet.
