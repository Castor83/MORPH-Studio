# KREA 2 in der MORPH-Browseroberfläche

Stand: 15. Oktober 2026. **Die vereinfachte MORPH-Oberfläche läuft auf http://127.0.0.1:8765 und enthält jetzt „Bild mit KREA 2 bearbeiten“.** Das Profil wurde im Browser ausgewählt; Bildpflicht, Anweisungsfeld und Startwerte sind geprüft. Eine neue Bild- oder Videoberechnung wurde in diesem Arbeitsschritt nicht ausgelöst.

![Geprüfte KREA-Ansicht](MORPH-KREA-Browser.jpg)

## Bedienung

1. In MORPH **Bild mit KREA 2 bearbeiten** wählen.
2. Unter **Ausgangsbild** ein PNG, JPEG oder WebP auswählen.
3. Die gewünschte Änderung auf Englisch in **Bildbeschreibung / Anweisung** eintragen.
4. Die Startwerte zunächst bei 768 × 768, 8 Schritten, Textstärke 1 und Referenzstärke 1 lassen. Weitere Einstellungen sind aufklappbar.
5. **Berechnung starten** bewusst auslösen. Ein Sprachmodell ist dafür optional.

Das Profil verwendet den zuvor erfolgreich getesteten SNOFS-Q5_1-Merge, den vollständigen Qwen3-VL-4B-Textencoder und den Qwen-Image-VAE. Die Anbindung übernimmt Eingabebild, Prompt, Auflösung, Seed, Schritte, Textstärke und Referenzstärke. Die beiden Groundings, die Referenz-/Ziel-Latent-Verbindung, `fit` und der LoRA-freie Aufbau bleiben erhalten. Neue Ergebnisse werden unter `output/MORPH-UI` gespeichert. Die Originalvorlage und die bisherigen Bilder bleiben unverändert.

## Vorhandene Bereiche

Alle sechs Profile finden bei der Abschlussprüfung ihre benötigten Dateien und ihre Node-Klassen im regulären Dienst:

| MORPH-Auswahl | Status ohne neue Berechnung |
|---|---|
| Bild erstellen | Dateien und Nodes verfügbar |
| Bild bearbeiten | Dateien und Nodes verfügbar |
| Gesichtstausch | Dateien und Nodes verfügbar |
| Bild zu Video | Wan-High-/Low-Paar, Zusatzgewichte und Video-Nodes verfügbar |
| Bild mit Qwen erstellen | Dateien und Nodes verfügbar |
| Bild mit KREA 2 bearbeiten | Neue Anbindung; Dateien, Nodes und Browserformular geprüft |

„Bild zu Video“ wurde zusätzlich im Browser geöffnet: das vorhandene Wan-2.2-Remix-Paar wird angeboten, die Bildpflicht sperrt einen Start ohne Ausgangsbild, Modellhinweise sind leer. Es wurde kein neues Video gerendert. Vorhandene Aufträge und Ergebnisse bleiben im Verlauf.

## Dienste und Änderungen

Die UI verwendet ihren regulären, durch den vorhandenen Starter geprüften MORPH-Rechendienst auf **Port 8188**. Dieser wurde gestartet; dort sind die benötigten KREA- und Video-Erweiterungen geladen. Der Modellcache der eigenen früheren KREA-Testinstanz auf Port 8189 wurde bei leerer Warteschlange freigegeben. Die Instanz wurde nicht als Video-Dienst verwendet. Die Oberfläche wurde nach der Codeergänzung neu gestartet und im Browser geöffnet. Bestehende Ollama-Einstellungen wurden erhalten; eine Anbietermigration war nicht nötig.

Geändert: `ui/morph_ui/catalog.py`, `ui/frontend/app.js`, `ui/tests/support.py`, neue `ui/tests/test_krea_profile.py` und die UI-Anleitung. Vorherige Arbeitskopien einschließlich bereits vorhandener Nutzeränderungen liegen unter `baseline/`; keine Rücksetzungen und kein Git-Commit oder Push. Das GGUF-Dateiformat erhält dieselbe sichere Pfad-, Existenz- und Nichtleerprüfung wie vorhandene Dateitypen. Andere Profile und Modellwahlen bleiben erhalten.

Die Desktop-Quellen wurden inventarisiert und die zusätzliche KREA-Turbo-GUI-Vorlage als Referenz kopiert. Große Modelle wurden nicht doppelt kopiert oder erneut heruntergeladen; das ONNX-Paket wurde nicht installiert. Exakte Flux2-Ablage, fehlende Komponenten und die Erklärung zum ONNX-Ordner stehen in [Desktop-Bestand.md](Desktop-Bestand.md).

## Verifikation und Grenzen

- Neue KREA-Tests zunächst erwartungsgemäß fehlgeschlagen; nach Implementierung acht neue Tests erfolgreich.
- Vollständige lokale Backend-Suite: **135 Tests erfolgreich**.
- Frontend-Suite: **14 Tests erfolgreich**.
- Unabhängige Codeprüfung: keine relevanten Fehler gefunden.
- Live-Datei-/Node-Prüfung aller sechs Profile: [workflows-readiness.json](workflows-readiness.json).
- Browser: KREA-Startwerte, Bildpflicht und Wan-Modellauswahl geprüft. Kein Bild hochgeladen und kein Berechnen-Knopf ausgelöst.

Die Tests verwenden synthetische Daten und simulierte Rechendienste. Ein neuer vollständiger Render über das MORPH-Formular bleibt vom Nutzer auszulösen. Die zwei früheren KREA-Läufe erfolgten direkt über ComfyUI: Shirt-Farbänderung erfolgreich; exakte Gesichtserhaltung nicht belegt; Referenzstärke 4 brachte im einzelnen Vergleich keinen erkennbaren Vorteil. Bestandsbereitschaft ist keine allgemeine Garantie für Speicherbedarf oder Ausgabequalität.
