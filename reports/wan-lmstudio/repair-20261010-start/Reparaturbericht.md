# MORPH-Verbindung in LM Studio repariert

Stand: 10. Oktober 2026, erfolgreiche Prüfung gegen 22:53 Uhr (Europe/Berlin).

## Ergebnis

Der zuvor dokumentierte Fehler bei `comfyui_upload_image` wurde für den allgemeinen Start- und Uploadweg behoben und mit einem neutralen Testbild geprüft. Die installierte LM-Studio-Erweiterung konnte ComfyUI starten, den Dienststatus abfragen, das Bild übertragen und die leere Warteschlange bestätigen.

Eine Bild- oder Videoberechnung und eine Sprachmodellvorhersage wurden nicht ausgeführt. Private Fotos wurden weder verwendet noch verändert. Die automatische Werkzeugentscheidung des Sprachmodells während einer normalen Chatantwort wurde nicht erneut geprüft.

## Änderung

Der Wrapper `D:\MORPH-Studio\tools\lmstudio-wan-chat\start_mcp.py` startet das vorhandene portable ComfyUI jetzt direkt mit dessen Python. Die PowerShell-Zwischenstufe, die in den bisherigen Versuchen sofort ohne Ausgabe mit Code 0 endete, wird für diese Verbindung nicht mehr verwendet.

Die bisherigen Startargumente, das Arbeitsverzeichnis, sämtliche Projekt- und Offline-Verzeichnisse sowie die Umgebungswerte für Ultralytics wurden übernommen. Der Start bleibt unsichtbar, an `127.0.0.1:8188` gebunden und im Offline-Modus. Sperre gegen Doppelstarts, Prüfung der Prozessidentität, Ablehnung fremder Portbelegung, Bereitschaftsprüfung und Zeitlimit bleiben erhalten. Ein eigener Python-Prozess wird jetzt auch während des Startens erkannt. Die Logausgabe wird ungepuffert geschrieben.

Die Ursache des ungewöhnlichen PowerShell-Exitcodes 0 selbst ist weiterhin nicht belegt. Die Reparatur ersetzt diesen nachweislich fehlschlagenden Startpfad durch den erfolgreich geprüften direkten Start.

## Prüfung

- Zwei neue Fehlertests scheiterten vor der Änderung und bestanden danach: direkter Anwendungsstart ohne funktionierende alte Shell-Startdatei; Erkennung des eigenen startenden Python-Prozesses ohne Doppelstart.
- Sämtliche elf Python-Tests und 18 Node-Tests des betroffenen Verbindungsprojekts bestanden.
- Ein unabhängiger Code-Review fand keine blockierenden Befunde.
- Die installierte Erweiterung lieferte sieben Werkzeuge. Ihre tatsächlichen Implementierungen für Status, Upload und Warteschlange wurden aufgerufen.
- ComfyUI startete einmal als PID 48720 und wurde von späteren Werkzeugaufrufen wiederverwendet.
- `comfyui_upload_image` meldete einen erfolgreichen Upload und keine fehlgeschlagene Datei. Das neutrale weiße PNG hat 32 × 32 Pixel und 95 Bytes. Original und hochgeladene Kopie haben dieselbe SHA-256-Summe: `3572d085e4f346e7b745d1931e667cbb970b2d1b0fef03d7fb82030f2b53829b`.
- Die abschließende Warteschlange war leer. Es wurde kein Renderauftrag übermittelt.
- Beide vorbereiteten Workflows besitzen sämtliche benötigten Knotentypen im gestarteten Dienst: Bildbearbeitung 14 Typen, Wan-Video 16 Typen. Das ist eine statische Verfügbarkeitsprüfung, kein Berechnungsnachweis.

## AnimateDiff und Triton

Der AnimateDiff-Ordner enthält nur ein leeres `models`-Unterverzeichnis. Der fehlende Erweiterungscode wurde bereits im Startprotokoll vom 9. Oktober gemeldet. Ob der Ordner lediglich vorbereitet, unvollständig eingerichtet oder später verändert wurde, ist nicht nachgewiesen; ein Verursacher ist nicht belegt.

Die AnimateDiff- und PatchTritonVAE-Warnungen bestehen weiter. Die beiden vorbereiteten Bild-/Wan-Workflows benötigen diese Knoten nicht. Für die Verbindungsreparatur wurden deshalb keine weiteren Pakete oder Erweiterungen installiert.

## Belege und Sicherungen

Vorherige Dateien und technische Prüfergebnisse liegen unter:

`D:\MORPH-Studio\reports\wan-lmstudio\repair-20261010-start`

Der maschinenlesbare Livebeleg ist `installed-provider-result.json`. Der neue Start steht in `D:\MORPH-Studio\reports\wan-lmstudio\mcp-comfy-start.log`. Der Dienst bleibt gestartet. Modelleinstellungen und die vorhandenen Bild-/Video-Workflows wurden nicht geändert.
