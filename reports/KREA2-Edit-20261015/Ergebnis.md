# KREA 2 Edit mit SNOFS Q5_1: erster lokaler Test

Stand: 15. Oktober 2026. **Ein Bildlauf erfolgreich abgeschlossen.** Am vorhandenen synthetischen Erwachsenenporträt wurde das rote T-Shirt dunkelblau. Gesichts-, Haar- und Bartdetails wurden dabei sichtbar neu gezeichnet; eine exakte Identitätserhaltung ist nicht nachgewiesen.

## Ergebnis und Bedienung

- [Ergebnisbild](../../output/KREA2-Tests/20261015/SNOFS_shirt_blue_00001_.png), 768 × 768 Pixel, RGB, 668.301 Bytes.
- [Grafischer Workflow](../../workflows/KREA2-SNOFS-Edit-20261015.json), aus der offiziellen Vorlage abgeleitet; [API-Fassung](../../workflows/KREA2-SNOFS-Edit-20261015-api.json).
- Aktuelle Testoberfläche: **http://127.0.0.1:8189**. Im Menü **Workflows** ist **KREA2-SNOFS-Edit-20261015** gespeichert und wurde geöffnet. Die Dateiwahl lässt sich dort gegen eigene Eingaben austauschen.
- [Synthetische Vorlage](../../input/Phase3-Referenz-Erwachsener.png). Es wurde kein privates Foto verwendet und kein Bild an einen Cloud-Bilddienst gesendet.

Die neue Testinstanz bleibt auf Port 8189 geöffnet. Sie verwendet ausschließlich den GGUF-Loader und die Krea-Edit-Erweiterung, läuft mit `--offline` und speichert Eingaben, Ausgaben und steuerbare Caches im MORPH-Projekt. Modelle können im lokalen Speicher zwischengespeichert bleiben. Die Warteschlange war nach dem Test leer.

## Tatsächlich ausgeführter Test

| Parameter | Wert |
|---|---|
| Modell | KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf |
| Textencoder | qwen3vl_4b_fp8_scaled.safetensors, Typ krea2, vollständiger Bildencoder |
| VAE | qwen_image_vae.safetensors aus Comfy-Org/Krea-2 |
| Zusätzliche LoRA | keine |
| Ausgabe / Batch | 768 × 768 / 1 |
| Seed | 20261015, fest |
| Schritte / CFG | 8 / 1 |
| Sampler / Scheduler / Denoise | euler / simple / 1 |
| ref_boost / ref_boost_a / fit_mode | 1 / 1 / fit |
| Grounding | 768; positives Bild-Text-Encoding und leeres negatives Bild-Text-Encoding |
| Auftrag | Nur das rote T-Shirt dunkelblau färben; Gesicht, Haare, Bart, Pose, Hintergrund und Ausschnitt bewahren |
| Prompt-ID | bf951a07-a61f-4f40-b1b1-19afe0e098a5 |
| Status | execution_success; completed=true; keine Node-Fehler |
| Dauer | ComfyUI meldet 93,44 Sekunden einschließlich Laden und Codieren |

Es wurde genau ein Prompt eingereiht und ein Bild erzeugt. Keine automatische Wiederholung oder Parametersuche. `target_latent` und der Sampler erhalten denselben leeren Ausgangslatent. Das Log bestätigt die Referenzcodierung vor dem Sampling.

93,44 Sekunden sind eine Messung dieses einzelnen ersten Laufs einschließlich Modellladen und keine belastbare Geschwindigkeitsangabe für weitere Läufe. Zwischenzeitlich wurden auf der GPU etwa 14,5 GiB Gesamtbelegung beobachtet; dies enthält andere GPU-Nutzung und ist keine Messung des maximalen Krea-Verbrauchs.

## Prüfung und visuelle Grenzen

Die API nahm den Auftrag ohne Validierungsfehler an. PNG-Decodierung, Abmessungen und eingebettete Modell-/Samplerparameter sind geprüft. Der Server ergänzt beim Eingabebild einen Änderungsfingerabdruck (`is_changed`); deshalb ist das eingebettete Prompt-Objekt nicht bytegleich zur vorbereiteten API-Datei. Klassen und sämtliche Ausführungsparameter stimmen nach Ausblenden dieses Server-Fingerabdrucks überein.

Die unabhängige statische Prüfung bestätigte 12 ausführbare Nodes und alle 18 übereinstimmenden UI-/API-Verbindungen. Der gespeicherte Workflow wurde anschließend auch in der Browseroberfläche geladen; eine Meldung über fehlende Nodes erschien dabei nicht.

Die unabhängige Sichtprüfung bestätigt:

- Rot zu Dunkelblau: **bestanden**.
- Pose, grobe Frisur, Bartgestaltung und quadratischer Porträtausschnitt: nah an der Vorlage.
- Strenge Erhaltung: **nicht bestanden**. Augen-/Brauen-, Mund-, Haut-, Haar- und Bartdetails wurden sichtbar neu gezeichnet. Hintergrundschattierung, Ausschnitt und Schulter-/Shirtkonturen verschieben sich leicht.
- Keine auffälligen Doppelgesichter oder groben Formfehler in diesem Ergebnis.

Das Ergebnis gilt nur für dieses synthetische Porträt und diesen Seed. Es ist keine biometrische Prüfung und belegt keine allgemeine Identitätserhaltung, Verlässlichkeit bei privaten Fotos, Zwei-Bild-Bearbeitung, Objektentfernung, größere Auflösungen oder weitere Merge-Einstellungen.

## Bestandsprüfung und Änderungen

Der SNOFS-Merge liegt auf E: unter `ComfyUI_windows_portable/ComfyUI/models/diffusion_models/` mit **10.660.189.216 Bytes (9,93 GiB)**. Die benannte V:-Datei hatte dieselbe Größe. Der lokale Header bestätigt Architektur `krea2`, Quantisierung Q5_1, 430 Tensoren: 256 Q5_1 und 174 F32. Für die bereits vorhandenen großen Modelle wurde keine erneute vollständige Hashprüfung vorgenommen. Der vorhandene Textencoder hat 5.242.467.968 Bytes. Beide wurden wiederverwendet und nicht erneut heruntergeladen.

Die vom Nutzer angekündigte Datei `qwen_image_vae.safetensors` war für diesen Zugriff weder unter dem erwarteten Modellpfad noch bei der gezielten Suche im MORPH-Projekt sichtbar. Das ist eine Grenze der Bestandsprüfung, keine Aussage über andere Ablageorte. Ergänzt wurde die [offizielle Datei](https://huggingface.co/Comfy-Org/Krea-2/blob/main/vae/qwen_image_vae.safetensors), **253.806.246 Bytes**, mit bestätigter veröffentlichter SHA256-Prüfsumme. Der vorhandene Qwen-Image-2.1-VAE ist strukturell inkompatibel; der Wan-VAE ist kein belegter gleichwertiger Ersatz. Einzelheiten: [Quellen und Grenzen](Quellen-und-Grenzen.md).

Der installierte GGUF-Loader zeigte die Datei an, lehnte aber die Architektur intern ab. Geändert wurde nur die Architekturliste in `custom_nodes/ComfyUI-GGUF-main/loader.py`: `krea2` wurde ergänzt. Die unveränderte Originaldatei liegt in [GGUF-loader.py.before](GGUF-loader.py.before). Der [Änderungsnachweis](loader-change.json) enthält vorherige und neue Prüfsumme sowie den ursprünglichen Upstream-Commit. Kein Paketupdate und keine weitere Loader-/Kernänderung waren für diesen Lauf nötig.

Neu angelegt wurden die Workflow-Dateien, Quellen-/Laufnachweise, eine benannte Kopie des synthetischen Eingabebilds sowie die Ausgabe. Die Workflow- und Eingabekopie liegen sowohl für die zuvor manuell gestartete ComfyUI-Verzeichnisstruktur als auch für den normalen MORPH-Starter bereit. Es wurde nichts gelöscht; bestehende Nutzeränderungen und alte Testergebnisse wurden erhalten. Kein Git-Commit oder Push.

## Dienstzustand und Freigabegrenze

Der geplante Neustart der ursprünglichen ComfyUI-Instanz auf Port 8188 wurde von der automatischen Freigabeprüfung mit **„blocked by policy“** abgewiesen; eine genauere Begründung wurde nicht geliefert. Der betreffende Stop-/Start-Befehl wurde nicht ausgeführt. Stattdessen wurde die eigene Testinstanz auf Port 8189 gestartet, PID **81312**. Die beiden Ports wurden nicht verwechselt.

Bei der Abschlussprüfung war Port 8189 erreichbar und seine Warteschlange leer. Port 8188 war zu diesem späteren Zeitpunkt für diesen Zugriff nicht mehr erreichbar; Ursache und Zeitpunkt wurden nicht festgestellt. Es wurde kein weiterer Neustart versucht. Die Loader-Korrektur liegt auf der Platte und wird bei einem späteren normalen MORPH-Start ebenfalls geladen. Der aktuelle geprüfte Einstieg ist Port 8189.

## Belege

- [Vorbereitung und Dateibestand](preflight.json), [Loader-Anpassung](loader-change.json)
- [Eingereichter Auftrag](submitted-request.json), [Einreichungsbeleg](submission-receipt.json), [Ausführungshistorie](execution-history.json)
- [Ausgabeverifikation](output-verification.json), [unabhängige Sichtbewertung](visual-review.json)
- [Quellen und Modellgrenzen](Quellen-und-Grenzen.md), [Originalworkflow](official-workflow-original.json), [Node-README](official-node-README.md)
- Laufzeitlogs: `E:\MORPH-Studio\logs\krea2-20261015-stdout.log` und `E:\MORPH-Studio\logs\krea2-20261015-stderr.log`

Die genaue Turbo-/Raw-Grundlage und die eingemischten Identity-Gewichte dieses konkreten Merges konnten nicht anhand einer zugänglichen Primärmodellkarte unabhängig bestätigt werden. 8 Schritte und CFG 1 bleiben deshalb eine getestete Einstellung dieses Einzelfalls. Die Vorgabe, beim ersten Test keine weitere Identity-LoRA hinzuzufügen, wurde eingehalten.
