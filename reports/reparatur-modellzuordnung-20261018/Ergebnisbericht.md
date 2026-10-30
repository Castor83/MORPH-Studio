# MORPH Studio: Modellzuordnung und Reparatur – 18.10.2026

Das bestehende Projekt unter **E:\MORPH-Studio** wurde direkt untersucht, gesichert und gezielt repariert. Die reparierte Oberfläche läuft unter http://127.0.0.1:8765. Keine Neuinstallation, Downloads, Löschung, Modellberechnung oder kostenpflichtigen Cloud-Aufrufe.

## Tatsächliche Werkzeugzuordnung

Alle Pfade in der folgenden Tabelle beziehen sich auf `E:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\models`. Vollständige absolute Pfade und Lader stehen in `six-tool-model-dependencies.json` und `workflows-after.json` sowie unmittelbar beim Werkzeug in der Oberfläche.

| Werkzeug | Tatsächliche Modelle und Komponenten |
|---|---|
| Bild erstellen | `checkpoints/sd_xl_base_1.0.safetensors`; alternativ vollständiger SD1.5-Checkpoint `checkpoints/v1-5-pruned-emaonly-fp16.safetensors`. Encoder und VAE sind eingebettet. |
| Bild bearbeiten | `diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors`, `text_encoders/clip_l.safetensors`, `text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors`, `vae/ae.safetensors`. |
| Gesichtstausch | `insightface/inswapper_128.onnx`; unter `insightface/models/buffalo_l/` die fünf Dateien `1k3d68.onnx`, `2d106det.onnx`, `det_10g.onnx`, `genderage.onnx`, `w600k_r50.onnx`. Gesichtswiederherstellung ist auf `none` gestellt. |
| Bild zu Video | `diffusion_models/Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors` und passendes `Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors`; `text_encoders/nsfw_wan_umt5-xxl_fp8_scaled.safetensors`, `vae/wan_2.1_vae.safetensors`, `upscale_models/4x_foolhardy_Remacri.pth`. RIFE liegt gesondert unter `E:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\custom_nodes\ComfyUI-VFI\rife\train_log\flownet.pkl`. |
| Bild mit Qwen erstellen | `diffusion_models/morph-ui-qwen21/noctQUncensoredRealismBuiltOn_v40Base_fp16.safetensors`, `text_encoders/morph-ui-qwen21/qwenImage21TextEncoderOriginal_v10_3241887.safetensors`, `vae/morph-ui-qwen21/qwenImage21VAEOriginalBf16_v10.safetensors`. |
| Bild mit KREA 2 bearbeiten | `diffusion_models/KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf`, `text_encoders/qwen3vl_4b_fp8_scaled.safetensors`, `vae/qwen_image_vae.safetensors`. |

Die sechs API-Vorlagen sind in dieser Reihenfolge `Phase2-1-Fotobild-SDXL-api.json`, `LMStudio-Bildbearbeitung-Kontext-api.json`, `LMStudio-Gesichtstausch-ReActor-api.json`, `LMStudio-Video-aus-Bild-Wan-api.json`, `MORPH-Qwen-Image-21-api.json` und `KREA2-SNOFS-Edit-20261015-api.json` unter `E:\MORPH-Studio\workflows`.

Alle 23 Modell-/Hilfsdateiverweise sind vorhanden und nicht leer. Alle sechs aktuellen Prüfungen der tatsächlichen ComfyUI-Laderauswahl bestehen ohne Hinweise. Kein aktueller Katalogworkflow schaltet eine LoRA zu. Dies bestätigt Zuordnung und Verfügbarkeit, keine neue Bild-/Videoqualität oder VRAM-Abnahme.

## Warum 27 Dateien teilweise nicht zugeordnet waren

Die ursprüngliche Liste erfasste ausschließlich Safetensors und enthielt verschiedene Rollen statt 27 austauschbarer Bildgeneratoren. Neun Einträge hatten unvollständig erkannte Architekturen:

- Zwei `flux2-vae.safetensors`: FLUX2-Bilddecoder, kein vollständiger Checkpoint und kein VAE für das vorhandene FLUX1-Kontext-Werkzeug.
- Zwei `snofsSexNudesAndOther_krea2TurboV14.safetensors`: KREA2-Safetensors mit eigenem ConvRot8-/Ladeprofil. Kein Ersatz für den GGUF-Lader des vorhandenen Edit-Werkzeugs.
- Zwei `snofs_ideogram_v1_1.safetensors` und `snofs_krea_v1_5.safetensors`: LoKR-Adapter, also Zusatzmodelle; keines der sechs Werkzeuge hat einen aktiven LoRA-Pfad.
- `qwen3vl_4b_fp8_scaled.safetensors`: passender KREA-Encoder, getrennt vom Qwen3-VL-8B-Encoder für QwenImage21.
- `qwen_3_8b_fp8mixed.safetensors`: Qwen3-8B-Textencoder, von keinem der sechs aktuellen Profile verwendet.

Diese Rollen werden jetzt erkannt. Das KREA-GGUF und zwei vorhandene FireRed-GGUF-Komponenten fehlten wegen des bisherigen Dateifilters vollständig. Jetzt umfasst die Bibliothek **30 Safetensors-/GGUF-Einträge**: 16 mit zugehörigem Werkzeug und 14 bekannte, aktuell ungenutzte Dateien/Komponenten. Keine aktuell unbekannte Safetensors-Architektur oder als beschädigt eingestufte Datei. Vier Einträge bleiben ausdrücklich ohne kompatibles aktives Ladeprofil: zwei KREA-Turbo-Safetensors und zwei FireRed-GGUF-Komponenten.

FireRed wurde weder fertig eingerichtet noch nachgeladen. ONNX-, PTH- und RIFE-Dateien zählen nicht zur auswählbaren Safetensors-/GGUF-Bibliothek; ihre Verwendung steht separat beim Werkzeug. 30 ist somit nicht die Zahl aller physischen Modelldateien im Projekt.

Drei Qwen-Hardlinkgruppen werden zu je einem Eintrag zusammengefasst. Gleichnamige weitere Dateien mit unterschiedlicher Dateiidentität bleiben sichtbar. Es wurde keine Dublette gelöscht oder durch Hashläufe erneut geprüft.

## Der rechte Ollama-Bereich

Er ist nachweislich optional: `/api/jobs` führt über JobService zu ComfyUI und ruft keinen Sprachmodellprovider auf. Modellwahl, explizites Laden, Vorschlag und Berechnungsstart sind getrennte Aktionen. Das Sprachmodell darf keine Bildmodelle wechseln oder selbst eine Berechnung auslösen.

`qwen-image-turbo-uncensored:latest` ist laut lokaler `/api/show`-Auskunft trotz des Namens ein Qwen3.5-Sprach-/Visionmodell: Architektur `qwen35`, 9.653.104.368 Parameter; Elternmodell `SetneufPT/Qwen3.5-9B-Coder_Q4_256k_ABL_16GB-GPU:latest`. Es ist kein QwenImage-Diffusionsgenerator. Die Metadatenabfrage lädt es nicht. Bereinigter Beleg: `ollama-qwen-image-turbo-metadata.json`.

Der native Ollama-Adapter verlangt Loopback und prüft lokale Modellmetadaten/Completion-Fähigkeit; Cloud- und reine Embedding-Modelle werden vor Laden/Vorschlag abgewiesen. Globale Ollama-Einstellungen blieben unverändert.

## Umgesetzte Reparaturen

1. Headererkennung für KREA, beide Qwen-Encoder, FLUX2-VAE und LoKR ergänzt. GGUF-Parser liest maximal 8 MiB Header und prüft Struktur, Quantisierungsblöcke, Datenbereiche, Größe und Dateiidentität ohne Gewichte/GPU-Import.
2. KREA-GGUF und passender 4B-Encoder sind auswählbar; der VAE des vorhandenen Profils bleibt fest. Inkompatible KREA-Safetensors werden nachvollziehbar ausgeschlossen.
3. Pro Werkzeug exakte ausgewählte Dateien, im Inventar passende Werkzeuge oder Gründe fehlender Verwendung. Feste Komponenten bleiben auch bei fehlendem Hauptmodell zugeordnet. Weitere WAN-Paare enthalten beide Partner; verwaiste High-Dateien werden nicht angeboten.
4. Unveränderte Inventarheader werden zwischengespeichert. Jede tatsächliche Auswahl/Erstellung öffnet und prüft das gewählte Modell weiterhin frisch. Momentaufnahme: Katalog kalt 1,78 s; warmes Inventar 0,75 s.
5. Speichern, Aktualisieren und Laden der Ollama-Auswahl sind im Browser gegen überlappende Antworten gesperrt; die Auswahl springt beim Aktualisieren nicht mehr auf einen alten Wert zurück.
6. Vorschlagskarten liefern vollständige geprüfte Nicht-Modell-Einstellungen. Einzelannahme oder andere Reihenfolge erzeugt keine ungültige Kombination aus WAN-Schrittzahl und Modellwechsel. Bilder und manuelle Bildmodelle bleiben geschützt.
7. Die gesamte Vorschlagsanfrage einschließlich Schema wird vor Providerzugriff auf 8.192 serialisierte Bytes begrenzt. Keine stille Kürzung. Kurze Standardanfragen aller sechs Werkzeuge passen; die gemessenen Beispiele lassen 399–875 Bytes Spielraum. Das ist ein Größenlimit, keine modellspezifische Tokengarantie. Kontext 4.096 und Ausgabegrenze 1.024 bleiben bestehen.
8. `start-morph-ui.ps1 -Restart` prüft den eigenen Prozess und verlangt eine serverseitige Startsperre: Alle Aufträge einschließlich älterer ungeklärter Belege werden geprüft, neue Starts gesperrt, erst danach wird nur die eigene Oberfläche beendet. ComfyUI/Ollama bleiben bestehen. Normales Starten verwendet die gesunde eigene Oberfläche weiter.

## Sicherung und Zustandserhaltung

- Vor Änderungen: 98 UI-/Workflow-/Start-/Dokumentationsdateien unter `E:\MORPH-Studio\reports\reparatur-modellzuordnung-20261018\baseline`, SHA-256-Manifest `baseline-manifest.json`.
- Vorhandene fremde Git-Änderungen gesichert in `existing-changes.patch`/`git-before.txt`; nichts zurückgesetzt. Einstellungen und konsistente Auftragsdatenbank unter `baseline/user/morph-ui`. Diese Sicherung enthält lokale Einstellungen und ist nicht zur öffentlichen Weitergabe bestimmt.
- Branch `main`, HEAD `a1a412746988c253f2747512ce5dfe10b0b85fde`; kein Remote, kein Commit/Push/Reset.
- Alle 31 Datenbankaufträge, Workflows und Pausendateien byte-/datensatzgleich erhalten; Nachweis `preservation-final.json`.
- Keine Modelle, privaten Eingaben/Ausgaben oder synchronisierten Projektdateien geändert, verschoben oder gelöscht. Keine Pakete/Treiber/globalen Einstellungen verändert.
- Nur die eigene Oberfläche aktiviert und anschließend den sicheren Neustart geprüft. ComfyUI blieb PID 23856, Ollama PID 7828. Aktuelle UI PID 90396. Keine neue Automation.

## Gezielte Prüfungen

| Prüfung | Ergebnis | Beleg |
|---|---|---|
| Betroffene Backendbereiche | 136 Tests bestanden | `backend-targeted-final.log` |
| Abschließende Zuordnungsfälle | 7 Tests bestanden | `dependencies-final-green.log` |
| Nach Neustartsperre: Aufträge und Serverrouten | 21 Tests bestanden | `restart-job-routes-final.log` |
| Frontend | 28 Tests bestanden | `frontend-final.log` |
| Reale ComfyUI-Laderauswahl | 6/6 ohne Hinweise, 23 Verweise | `live-checks-after.json` |
| Reale Browseroberfläche | 30 Dateien; KREA-Auswahl und Komponenten; SD1.5-Auswahl folgt im Dateipfad bei unveränderten 1024×1024; Start wartet auf Prüfung/Pflichtbild | `Browser-KREA-Modellzuordnung.png`, `browser-proof.json` |
| Windows-Starter | Start, sicherer Neustart und Wiederverwendung bestätigt | `restart-live.log`, `status-final.json` |
| Unabhängige Prüfung | GGUF-Blocktabelle gegen installierte Primärquelle geprüft; WAN-Paar- und Neustart-Randfälle gefunden und korrigiert | Bibliotheks-/Zuordnungs-/Neustarttests |

Die Zahlen enthalten überlappende Nachprüfungen und sind nicht als unterschiedliche Tests zu addieren. Keine komplette Wiederholung aller Projekttests. Automatisierte Modell-/Rechenfälle waren synthetisch bzw. simuliert. Keine echte Inferenz.

Ein erster Testaufruf scheiterte vor dem Import am Suchpfad des eingebetteten Python; der korrigierte Aufruf bestand 136 Tests. Eine erste Aktivierungsprüfung brach wegen UTC-Vergleich vor jeder Prozessänderung ab. Danach wurde nur die exakt identifizierte UI bei gesperrter Auftragsdatenbank und ohne aktive eigene Aufträge beendet. Beides waren keine Modellfehler oder Bildberechnungen.

## Grenzen und nächster Schritt

NVIDIA meldet RTX 4080 mit 16.376 MiB VRAM; Momentaufnahme 3.148 MiB belegt, 12.901 MiB frei. Kein fremdes Modell freigegeben. Die großen Qwen-/WAN-Modelle können Arbeitsspeicher-Auslagerung benötigen. Passende Dateien/Lader garantieren weder beliebige Bild-/Videogrößen noch Geschwindigkeit oder Bildqualität bei 16 GB. Einstellungen wurden nicht eigenmächtig erhöht.

Deutsche Vorschlagsqualität und neue Bild-/Videoausgaben wurden nicht durch Inferenz geprüft. Kein Modellvergleich. Der nächste Schritt ist die normale Bedienung der reparierten Oberfläche: Werkzeug, gegebenenfalls Ausgangsbild und Anweisung wählen. Eine echte Berechnung startet erst durch den bewussten Klick auf „Berechnung starten“.

## Quellen

Lokale Primärquellen: `ui/morph_ui/{catalog,model_library,comfy,jobs,server,tool_planning}.py`, Provider, Frontend, sechs API-Workflowdateien, installierte ComfyUI-Modellerkennung und `gguf/constants.py`, tatsächliche `/object_info`-Laderauswahl. Referenzchat „Fotobearbeitung Einstellungen uitleg“, ID `6ad393bc-cffc-83eb-8734-6f39b52ead80`: Dialog und verfügbare Bildpfade abgerufen. Eine erneute Bereitstellung durch den Nutzer war nicht erforderlich.

- [ComfyUI: Modelle, Ordner und Lader](https://docs.comfy.org/basic-concepts/models)
- [Ollama: Chat-API](https://docs.ollama.com/api/chat)
- [Ollama: FAQ und Kontext](https://docs.ollama.com/faq)
- [Offizieller QwenImage21-Workflow](https://comfy.org/workflows/bb7e03924a5c-bb7e03924a5c/)
