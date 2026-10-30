# MORPH in LM Studio – einfache Anleitung

> Historischer Bedienweg: Seit der Umstellung vom 15.10.2026 verwendet die eigene MORPH-Oberfläche Ollama. Die aktuelle Bedienung steht in `ui/README.md`. Die folgenden LM-Studio-Einrichtungsschritte sind für die aktuelle Oberfläche nicht erforderlich; frühere Ergebnisse bleiben als Nachweis erhalten.

Du gibst deine Aufträge im normalen LM-Studio-Chat ein. Die eingerichtete MORPH-Erweiterung verbindet den Chat mit ComfyUI. ComfyUI übernimmt die Bild- und Videoberechnung lokal im Hintergrund und wird bei Bedarf von der Erweiterung gestartet.

## 1. Den Chat vorbereiten

1. Öffne **LM Studio** und gehe zum **Chat**.
2. Erstelle einen neuen Chat. Unter Windows geht das mit **Strg + N**. [LM-Studio-Dokumentation](https://lmstudio.ai/docs/app/basics/chat)
3. Wähle **Gemma 4 12B Instruct QAT** im Modellfeld und lade es. Der Name kann auch als `gemma-4-12b-it-qat` erscheinen. Das Modell ist bereits vorhanden.
4. Öffne rechts den Bereich **Program** und aktiviere **bilder-und-videos**. Die vollständige Kennung lautet `morph/bilder-und-videos`. Für diesen Ablauf nur diese MORPH-Verbindung aktivieren, damit Werkzeuge nicht doppelt angeboten werden. [Dokumentation zum Bereich Program](https://lmstudio.ai/docs/app/mcp)
5. Wähle in der Chat-Konfiguration das Preset **MORPH - Bilder und Videos**. Ein Preset ist eine gespeicherte Einstellung; dieses enthält die Anweisungen für deine Bild- und Videoaufträge. Es lädt das Chatmodell nicht automatisch. [Dokumentation zu Presets](https://lmstudio.ai/docs/app/presets)

Bei jedem neuen Chat kontrollieren, ob Erweiterung und Preset ausgewählt sind.

## 2. Bilder anhängen

Nutze die Funktion zum Anhängen eines Bildes beim Eingabefeld und wähle deine Datei aus. Vor dem Absenden prüfen, ob das gewünschte Bild als Anhang erscheint.

Für Kleidung, Hintergrund oder ein Video reicht **ein Bild**. Für Gesichtstausch brauchst du **zwei Bilder**:

- **Quellbild:** liefert das neue Gesicht.
- **Zielfoto:** das Gesicht wird hier ersetzt.

Nenne bei zwei Bildern ausdrücklich, welches die Quelle und welches das Ziel ist. Dateinamen sind dafür besonders hilfreich. Bei mehreren Personen im Bild zusätzlich sagen, welche Person gemeint ist.

## 3. Gesicht tauschen – dein Beispiel

Hänge diese beiden Bilder an:

- [Screenshot – Quellgesicht](<D:/sal/Screenshot 2025-03-03 161945 (1).png>)
- [LOVESCAPE – Zielfoto](D:/sal/LOVESCAPE.png)

Schreibe dann:

> Setze das Gesicht aus „Screenshot 2025-03-03 161945 (1).png“ in „LOVESCAPE.png“ ein. Erhalte Haare, Kleidung, Hintergrund und Schrift. Speichere das Ergebnis als Bild.

MORPH verwendet dafür ReActor und speichert ein PNG. Der bereits fertiggestellte Gesichtstausch liegt hier: [LOVESCAPE mit neuem Gesicht](E:/MORPH-Studio/output/LMStudio/LOVESCAPE-Gesichtstausch_00001_.png). Du kannst dieses Ergebnis direkt verwenden. Bei diesem ersten Versuch wirkt das neue Gesicht etwas weich.

## 4. Kleidung oder Hintergrund ändern

Hänge ein Bild an und beschreibe die gewünschte Änderung möglichst konkret.

**Kleidung:**

> Ändere die Kleidung zu einer blauen Jacke. Erhalte das Gesicht, die Haltung und den Hintergrund möglichst unverändert. Speichere das Ergebnis als Bild.

**Hintergrund:**

> Ersetze den Hintergrund durch einen sonnigen Garten. Erhalte die Person und ihre Kleidung möglichst unverändert.

MORPH verwendet dafür FLUX Kontext und speichert ein PNG. Auch bei einer gezielten Änderung können andere Bilddetails abweichen. Schau dir das Ergebnis deshalb an.

## 5. Aus einem Bild ein Video machen

Hänge das gewünschte Startbild an. Beschreibe die Bewegung und die Kamera.

> Erstelle aus diesem Bild ein Video: Sie hält die Katze stolz zur Kamera und gibt einen Luftkuss. Die Kamera bleibt ruhig.

Oder:

> Erstelle aus diesem Bild ein Video mit sanftem Blinzeln und einer ruhigen Kamera.

Für das Foto mit der Katze:

> Erstelle aus diesem Foto ein kurzes Tanzvideo mit sanften Schulter- und Oberkörperbewegungen. Sie hält die Katze sicher. Erhalte ihre vorhandene Kleidung. Die Kamera bleibt ruhig. Führe den Auftrag mit den MORPH-Werkzeugen aus.

MORPH verwendet dafür Wan. Die eingerichteten Startwerte erzeugen einen kurzen Clip. Zusätzlich werden eine Version mit flüssigerer Bewegung und eine vergrößerte Version gespeichert. Ein Video kann mehrere Minuten dauern. Warte auf den Abschluss, bevor du den nächsten Auftrag sendest.

Der erste Tanzclip aus dem Foto mit der Katze ist fertig: [Video öffnen](E:/MORPH-Studio/output/LMStudio/Katze-Tanz-Upscale_00001.mp4). Er dauert 3,5 Sekunden, hat 1024 × 1024 Pixel und keinen Ton. Acht Einzelbilder wurden angesehen: sanftes Wiegen, Kopfbewegung und Lächeln; weißes Oberteil und Katze bleiben erhalten. Hände wirken stellenweise weich, und die Beleuchtung verändert sich. Alle drei Ausgaben wurden vollständig fehlerfrei dekodiert. Die Ausführung lief über die installierten Werkzeuge der LM-Studio-Erweiterung; die automatische Werkzeugentscheidung des Chatmodells wurde dabei nicht getestet.

## 6. Bearbeitung und Video verbinden

Wenn beides gewünscht ist, schreibe beide Schritte ausdrücklich in einen Auftrag:

> Ändere zuerst die Jacke zu Rot. Erstelle anschließend aus dem bearbeiteten Bild ein Video mit sanftem Blinzeln und einer ruhigen Kamera.

Für Gesichtstausch mit anschließendem Video:

> Setze zuerst das Gesicht aus dem Screenshot in das LOVESCAPE-Bild ein. Erstelle danach aus dem fertigen Bild ein Video mit sanftem Blinzeln und einer ruhigen Kamera.

Direkter Gesichtstausch in einer bereits vorhandenen Videodatei ist mit dieser Einrichtung noch nicht vorgesehen.

## 7. Ergebnisse öffnen

Deine Ergebnisse werden hier gespeichert:

[E:\MORPH-Studio\output\LMStudio](E:/MORPH-Studio/output/LMStudio)

Öffne den Ordner im Windows-Datei-Explorer. Bilder haben die Endung **.png**, Videos **.mp4**. Die Originalbilder bleiben erhalten. Eine erfolgreiche Berechnung bestätigt, dass die Datei erzeugt wurde; prüfe anschließend, ob das Ergebnis deinen Vorstellungen entspricht.

## Wenn etwas nicht klappt

**Die Erweiterung fehlt:** Starte LM Studio neu und schaue erneut unter Program nach **bilder-und-videos**.

**Das Preset fehlt:** Nutze die Importfunktion des Preset-Managers und wähle diese vorhandene Datei: [morph-wan-video.preset.json](V:/LMStudio/.lmstudio/config-presets/morph-wan-video.preset.json).

**Das Bild wird nicht gefunden:** Ergänze den vollständigen Dateipfad im Auftrag. Für deinen Gesichtstausch zum Beispiel:

> Quellgesicht: D:\sal\Screenshot 2025-03-03 161945 (1).png. Zielfoto: D:\sal\LOVESCAPE.png. Setze das Quellgesicht in das Zielfoto ein und speichere das Ergebnis als Bild.

**Der Chat beschreibt den Auftrag nur:** Kontrolliere Erweiterung und Preset. Schreibe anschließend: „Führe den Auftrag mit den MORPH-Werkzeugen aus.“

**„This message contains no content“ oder ein Verbindungs-Timeout:** Am 10. Oktober wurde die blockierende Werkzeuginitialisierung repariert. Die Werkzeuge werden jetzt bereitgestellt, bevor ComfyUI vollständig gestartet ist; erst der eigentliche Werkzeugaufruf wartet auf den Hintergrunddienst. Die alte doppelte Verbindung **Wan-ComfyUI** wurde mit Sicherung entfernt. Verwende **bilder-und-videos** und das MORPH-Preset. Diese Reparatur wurde über die tatsächlich installierte Erweiterung geprüft; die automatische Entscheidung des Chatmodells ist weiterhin ein eigener, offener Prüfschritt.

**Eine Fehlermeldung erscheint:** Bewahre die genaue Meldung auf und sende sie hier. Bei einem Speicherfehler oder einem fehlgeschlagenen Rechenlauf nicht denselben Auftrag mehrfach starten.

## Bisher geprüft

Bildanhänge, Werkzeugverbindung, Gesichtstausch und die bereits erzeugten Videos wurden geprüft. Nach der Verbindungsreparatur wurden alle sieben Werkzeuge in 6,7 Sekunden bereitgestellt; ComfyUI-Status und leere Warteschlange wurden bestätigt. 18 Tests der Chat-Erweiterung und neun Tests des Hintergrundstarts bestanden. Beleg: [Verbindungsprüfung](E:/MORPH-Studio/reports/wan-lmstudio/repair-no-render-probe.json). Die automatische Werkzeugentscheidung während einer normalen LM-Studio-Chatantwort ist noch offen. Diese Anleitung beschreibt den dafür eingerichteten Bedienweg; sie bestätigt diesen letzten Chat-Test nicht.

Stand: 10. Oktober 2026. Die Namen und Pfade wurden anhand deiner gespeicherten Einrichtung abgeglichen. Die bestehende ausführliche Dokumentation bleibt unter [LMStudio-Wan-Bedienung.md](E:/MORPH-Studio/LMStudio-Wan-Bedienung.md) erhalten.
