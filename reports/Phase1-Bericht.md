# MORPH Studio v1.0 – Phase 1

Stand: 8. Oktober 2026. Phase 1: 5/5 bestanden. Gesamtplan: 5/40.

| Punkt | Ergebnis und Prüfung |
|---|---|
| 1. System und Speicher | Windows 11 Home, Ryzen 7 7800X3D, 48 GB RAM, RTX 4080 mit 16 GB VRAM, NVIDIA-Treiber 616.56. V: ist NTFS auf Samsung SSD 850 PRO 256 GB; Windows meldet Healthy. Vorher 68,05 GiB frei. |
| 2. Eigenständiger Projektordner | Installation, Python, Modelle, Workflows, Eingaben, Ausgaben, Benutzerdateien, Logs und projektseitige Caches ausschließlich unter V:\MORPH-Studio. Keine Schreiboperationen in Forge oder anderen bestehenden Projekten; keine globalen Python-, PATH- oder Treiberänderungen. |
| 3. Python/PyTorch/CUDA | Offizielle portable Laufzeit: Python 3.13.14, PyTorch 2.14.0+cu130, CUDA-Laufzeit 13.0. Echte GPU-Matrixberechnung gegen CPU-Ergebnis bestanden; maximale Abweichung 0,0000763. Abschließendes pip check: No broken requirements found. Ein separates CUDA-SDK war nicht erforderlich. |
| 4. ComfyUI installieren/starten | ComfyUI 0.39.0, Frontend 1.53.10. API und Browseroberfläche geladen und geprüft. Listener nur 127.0.0.1:8188; --offline aktiv, externe Frontend-Verbindungen durch Content-Security-Policy eingeschränkt, Partner-Nodes deaktiviert. |
| 5. GPU und echter Testlauf | SD 1.5 FP16, 512 × 512, 20 Euler-Schritte, CFG 7, Seed 42. Vollständige Erzeugung mit Modell, Textencoder, Sampling und VAE auf lokaler Laufzeit; CUDA-Gerät im Log bestätigt. ComfyUI meldet 3,24 s, Test inklusive Abfrage 4,11 s. PNG geöffnet, Abmessungen und nichtleerer Bildinhalt geprüft, rote Tasse visuell bestätigt. |

## Speicher

Projektdateien: 8.31 GiB. Auf V: frei: 71.53 GiB. Die freie Kapazität hat sich während der Einrichtung unabhängig von der Projektgröße verändert; sie ist deshalb kein zuverlässiges Maß des Installationsverbrauchs. Maßgeblich ist die direkt gemessene Größe des MORPH-Ordners. Die Ursache der laufwerksweiten Veränderung wurde nicht untersucht.

- cache: 0.09 GiB
- ComfyUI_windows_portable: 6.35 GiB
- downloads: 1.87 GiB
- input: 0.00 GiB
- logs: 0.00 GiB
- output: 0.00 GiB
- reports: 0.00 GiB
- temp: 0.00 GiB
- user: 0.00 GiB
- workflows: 0.00 GiB

Das Installationsarchiv bleibt für eine Wiederherstellung erhalten (1,87 GiB). Das Testmodell belegt 1,99 GiB. GPU-Speicher nach dem Bildtest laut ComfyUI: rund 3,35 GiB belegt auf dem gesamten Gerät; kein Spitzenwert während der Erzeugung gemessen.

## Behobener Fehler und offene Grenzen

Das offizielle portable Paket enthielt drei laut Paketmetadaten benötigte Vorlagen-Medienpakete nicht. Ergänzt wurden ausschließlich comfyui-workflow-templates-media-video 0.3.101, media-image 0.3.160 und media-other 0.3.229 in der eigenen Laufzeit. Danach Abhängigkeitsprüfung bestanden.

Keine blockierenden Probleme für Phase 1. Die Meldungen zu nicht installierten AMD-, Ascend- und Triton-Backends betreffen optionale andere Rechenpfade; NVIDIA-CUDA funktioniert. Eine PyTorch-Deprecation-Warnung verhindert den Test nicht. Eigene Erweiterungen und Modelle späterer Phasen sind noch nicht getestet.

Der Test lief mit vorhandenen lokalen Modellgewichten und im Offline-Modus, ohne Cloud-Konto oder Cloud-Berechnung. Ein Test bei physisch getrenntem Internet wurde nicht durchgeführt. Windows-eigene Logs, Browserprofil, Defender-Aktivität und Auslagerungsdatei können weiterhin auf Systemlaufwerken liegen; die projektseitig steuerbaren Cache- und Temp-Pfade liegen auf V:. Es wurden keine globalen Windows-Pfade umgestellt.

## Bedienung

ComfyUI läuft aktuell. Oberfläche: http://127.0.0.1:8188

Nach Beenden oder Neustart MORPH-Start.cmd im Projektordner doppelklicken und die Adresse im Browser öffnen. Ein aktiver Start bleibt im Fenster sichtbar; dort Strg+C zum Beenden. Den aktuell von der Einrichtung gestarteten Hintergrunddienst mit MORPH-Stop.cmd beenden. Nicht zweimal starten.

Unter Workflows liegt Phase1-Bildtest.json. Alternativ workflows\Phase1-Bildtest.json in die Oberfläche ziehen. Laden und Run in der Browseroberfläche wurden ebenfalls erfolgreich geprüft; diese identische Wiederholung nutzte den bereits berechneten Ergebnis-Cache. Für eine neue Berechnung Prompt oder Seed ändern. Bilder landen in output, Eingaben in input. Der API-Testworkflow liegt zusätzlich als workflows\phase1-test-api.json vor.

## Quellen und Nachweise

- Offizielle Distribution: https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.39.0
- Offizielle Installationsbeschreibung: https://github.com/Comfy-Org/ComfyUI
- Testmodell: https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive
- Archiv-SHA256: 3dca347842ed1c6c833105fafb1669284685a3e54df41578d5f94bcc898ae039
- Modell-SHA256: e9476a13728cd75d8279f6ec8bad753a66a1957ca375a1464dc63b37db6e3916
- reports: system-baseline.json, release-asset.json, gpu-test.json, image-test.json, dependency-check.txt, installed-packages.txt, storage.json
- logs: comfyui-stdout.log und comfyui-stderr.log

Nächster Schritt: Phase 2 – ein geeignetes fotorealistisches Bildmodell und einen speicheroptimierten Edit-Workflow auswählen.
