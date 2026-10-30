# Bilder bearbeiten und Videos erstellen in LM Studio

Die Bedienung erfolgt im normalen LM-Studio-Chat. ComfyUI übernimmt die Berechnung lokal im Hintergrund. Die Erweiterung löst lokale Bildanhänge für die Bearbeitung auf; die Bilder bleiben gleichzeitig für das Chatmodell sichtbar.

1. Ein Chatmodell mit Bild- und Werkzeugunterstützung auswählen. **Gemma 4 12B Instruct QAT** ist bereits vorhanden; LM Studio meldet beide Fähigkeiten. Sein Zusammenspiel mit einer laufenden Bild-/Videoberechnung ist noch nicht durch einen neuen Modelllauf geprüft.
2. Im Bereich **Program** die Erweiterung **bilder-und-videos** (`morph/bilder-und-videos`) aktivieren. Für diesen Ablauf nur diese Verbindung aktivieren, damit Werkzeuge nicht doppelt angeboten werden.
3. Das Preset **MORPH - Bilder und Videos** auswählen.
4. Ein Bild anhängen und den Auftrag auf Deutsch schreiben.

Beispiele:

- „Ändere die Kleidung zu einer blauen Jacke. Erhalte das Gesicht und den übrigen Hintergrund.“
- „Ersetze den Hintergrund durch einen sonnigen Garten.“
- „Erstelle daraus ein Video: Sie hält die Katze stolz zur Kamera und gibt einen Luftkuss. Die Kamera bleibt ruhig.“
- „Ändere zuerst die Jacke zu Rot und erstelle danach aus dem bearbeiteten Bild ein Video mit sanftem Blinzeln.“

Mehrere Bilder brauchen eine eindeutige Zuordnung. Falls LM Studio bei einem Bild keinen lokalen Pfad liefert, den vollständigen Dateipfad nennen; der Chat darf kein anderes Bild einsetzen.

Bildbearbeitung nutzt FLUX Kontext und erzeugt ein PNG. Änderungen an Kleidung, Frisur, Hintergrund und Gegenständen lassen sich damit beauftragen. Gesicht und andere Details können sich dabei ebenfalls verändern; exakte Identität ist nicht garantiert. Gesichtstausch mit einem zweiten Quellgesicht ist **noch nicht eingerichtet**: Dafür fehlen die entsprechende Erweiterung, Modelle und ein eigener Ablauf.

Videos nutzen Wan. Die vorbereiteten Startwerte sind 512 × 512 Pixel, 81 Ausgangsframes und acht Berechnungsschritte. Zusätzlich entstehen eine Version mit flüssigerer Bewegung und eine vergrößerte Version. Bild- und Videoergebnisse liegen unter `D:\MORPH-Studio\output\LMStudio`. Originaldateien bleiben erhalten.

Das bereits fertiggestellte Video liegt unter `D:\MORPH-Studio\output\LMStudio\Katze-Luftkuss-Upscale_00001.mp4` (1024 × 1024 Pixel, 30 Bilder pro Sekunde, 3,83 Sekunden, ohne Ton). Die Frau hält die Katze zur Kamera und gibt einen sichtbaren Luftkuss. Alle drei damaligen Ausgaben wurden vollständig fehlerfrei dekodiert; Einzelbilder wurden angesehen. Finger wirken stellenweise weich. Die gesamte Wiedergabe wurde nicht auf Flackern geprüft.

Prüfstand der neuen Chat-Anbindung: Die installierte Erweiterung liefert alle sieben vorgesehenen Werkzeuge. Status, leere Warteschlange und Abholung der drei fertigen Videos wurden darüber tatsächlich geprüft. Ein von LM Studio aufbereitetes Bild wurde mit der installierten Vorverarbeitung aufgelöst und über das native Upload-Werkzeug übertragen; Bildanhang und Dateiinhalt blieben erhalten. Dafür wurde kein neues Bild oder Video berechnet und kein Chatmodell geladen. Die vorbereiteten Abläufe wurden mit den tatsächlich registrierten Knoten und Modellnamen abgeglichen; 16 Tests der Chat-Erweiterung und acht Tests des Hintergrundstarts bestanden. Die Aktivierung in der Oberfläche, die Ausführung der Vorverarbeitung während einer normalen Chatantwort, die automatische Entscheidung des Chatmodells und ein neuer Bearbeitungsauftrag im normalen Chat sind noch nicht bestätigt. Beleg: `reports\wan-lmstudio\native-installed-plugin-probe.json`.
