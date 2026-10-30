# Modellbibliothek: gezielte Reparaturen am 18.10.2026

Aktuell am tatsächlichen Projektpfad E:\MORPH-Studio geprüft. Ausschließlich Dateiköpfe und Dateimetadaten gelesen; keine Modellgewichte geladen, kein GPU-Lauf, kein Download, kein Prozessstart oder -stopp. Vorheriger Quellstand liegt unter baseline/ui/morph_ui/model_library.py.

## Ursache der bisherigen 27 Einträge

Die Bibliothek erfasste nur Safetensors in checkpoints, diffusion_models, text_encoders, vae, loras, unet und clip. Drei Qwen-Komponenten besitzen jeweils einen echten Hardlink im checkpoints-Ordner und im zu ihrem Loader passenden Ordner. Diese drei Paare werden weiterhin jeweils einmal gezählt. ONNX-Gesichtsmodelle, PTH-Vergrößerungsmodelle, Vorschaudecoder und RIFE-Unterstützungsdateien liegen außerhalb dieses sicher auswählbaren Katalogs.

Von den 27 ursprünglichen Einträgen waren neun als unbekannte Architektur markiert. Die Dateiköpfe belegen:

| Bisher unbekannte Dateien | Tatsächlicher Typ | Konsequenz |
|---|---|---|
| flux2-vae.safetensors in checkpoints und diffusion_models | FLUX.2-VAE, 32 latente Kanäle vor Entpackung | Zusatzkomponente, kein Bildcheckpoint und kein FLUX.1-Kontext-VAE |
| snofsSexNudesAndOther_krea2TurboV14.safetensors in checkpoints und diffusion_models | KREA-2-Hauptmodell; Metadaten nennen ConvRot8-Quantisierung | Als KREA erkannt, bleibt bewusst außerhalb des vorhandenen GGUF-Edit-Profils |
| snofs_ideogram_v1_1.safetensors in checkpoints und loras | LoKR-Adapter | Als Zusatzmodell erkannt; keines der sechs Werkzeuge lädt ihn |
| loras/snofs_krea_v1_5.safetensors | LoKR-Adapter für KREA | Als Zusatzmodell erkannt; kein automatisches Hinzuladen |
| text_encoders/qwen3vl_4b_fp8_scaled.safetensors | Qwen3-VL 4B | Passender KREA-Encoder, getrennt von Qwen Image 2.1 / 8B |
| text_encoders/qwen_3_8b_fp8mixed.safetensors | Qwen3 8B ohne Visionkomponente | Komponente für ein anderes Ladeprofil; kein Ersatz für Qwen Image 2.1 |

qwen_image_vae.safetensors besitzt dieselbe geprüfte Wan-VAE-Architektur wie wan_2.1_vae.safetensors. Die Zuordnung bezeichnet jetzt ausdrücklich die gemeinsame Wan-/Qwen-Image-Architektur. Die konkrete, erprobte VAE-Datei des KREA-Profils bleibt unverändert.

## Änderungen

- LoKR-Tensornamen werden zusätzlich zu normalen LoRA-Namen erkannt.
- Sichere Formsignaturen für KREA 2, Qwen3-VL 4B, Qwen3 8B und FLUX.2-VAE ergänzt. Keine Zuordnung allein aufgrund des Dateinamens.
- GGUF-Dateien werden ebenfalls anhand ihres Headers geprüft. KREA-Auswahl benötigt sowohl general.architecture=krea2 als auch die passenden fünf Tensorformen. Safetensors und GGUF werden nicht zwischen verschiedenen Loadern ausgetauscht.
- Der GGUF-Leser liest maximal 8 MiB, keine Gewichte. Verschachtelte Metadatenarrays, zu große Anzahlen, Null-Dimensionen, unbekannte Quantisierungen, nicht passende Blockbreiten, überlappende/fehlende Datenbereiche, abweichende Gesamtgröße und während der Prüfung geänderte Dateien werden abgewiesen.
- Öffentliche neue Rollen: krea_model, krea_encoder; rein klassifizierte Komponentenrollen flux2_vae und qwen3_encoder. Bestehende Auswahlrollen bleiben erhalten.
- Synthetische KREA-Testdateien wurden von beliebigen Bytes auf gültige sparse Header umgestellt. Die Fixtures liegen ausschließlich im Projekt-Temp-Bereich und werden niemals ausgeführt.

## Geprüftes Ergebnis

model-inventory-before.json: 27 gruppierte Safetensors-Einträge. model-inventory-after.json: 30 gruppierte Safetensors-/GGUF-Einträge. Der Zuwachs besteht aus dem bisherigen KREA-GGUF und den zwei schon vorhandenen FireRed-Encoder-/Vision-GGUF-Dateien. Keine Dateien verschoben oder gelöscht.

Keine unbekannte Architektur und keine ungültige Datei im aktuellen Bibliotheksumfang. Vier Einträge bleiben ausdrücklich ohne aktives Ladeprofil: die beiden separat abgelegten KREA-Turbo-Safetensors-Dateien sowie die zwei FireRed-GGUF-Komponenten. Das fehlende FireRed-Hauptmodell wurde nicht ergänzt; kein neues Werkzeug eingebaut.

Gezielte RED-Prüfung vor Änderung: acht neue Fälle schlugen wie erwartet fehl. Abschließende Bibliotheksprüfung: **51/51 bestanden**, davon 13 neue Zuordnungs-/GGUF-Fälle und 38 vorhandene Bibliothekstests. Beleg: model-library-tests.log. Dazu gehören Header-Lesegrenzen ohne Gewichtslesezugriff, Architekturtrennung, beschädigte/verkürzte GGUF-Dateien, Überlappung, Null-Dimensionen, verschachtelte Arrays, Dateiaustausch sowie vorhandene Pfad-/Hardlink-/Junction-Sicherungen.

Diese Prüfungen belegen Dateierkennung und Auswahlgrenzen. Sie belegen keine neue Modellberechnung, Bildqualität oder VRAM-Abnahme.
