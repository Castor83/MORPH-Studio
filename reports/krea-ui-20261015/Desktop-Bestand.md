# Desktop-Dateien und zusätzliche Vorlagen

Stand: 15. Oktober 2026. Die Desktop-Quellen wurden ausschließlich lesend geprüft. Es wurden keine Modelldateien verschoben, gelöscht oder erneut heruntergeladen und keine Bibliotheken aus diesen Ordnern geladen.

## C:\Users\USER\Desktop\Morthmod

| Datei | Befund und Verwendung |
|---|---|
| qwen3vl_4b_fp8_scaled.safetensors | Bereits auf E: unter `models/text_encoders/`; Größe und vollständiger Header stimmen überein. Das KREA-UI-Profil verwendet die vorhandene E:-Datei. |
| qwen_image_vae.safetensors | Bereits auf E: unter `models/vae/`; Größe und vollständiger Header stimmen überein. Das KREA-UI-Profil verwendet die vorhandene E:-Datei. |
| qwen_3_8b_fp8mixed.safetensors | Bereits auf E: unter `models/checkpoints/`; Größe und vollständiger Header stimmen überein. Für den gespeicherten Flux2-Workflow ist der Loader-Ordner noch anzupassen. |
| qwen2.5-vl-7b-instruct-q8_0.gguf | Qwen2.5-VL 7B, Q8_0, 339 Tensoren, keine Vision-Tensoren im vollständig inspizierten Tensorverzeichnis. Der installierte GGUF-Loader benötigt dazu ein passendes mmproj; ein solches wurde in diesen Quellen und der E:-Inventur nicht gefunden. Kein bereits einsatzbereiter Ersatz für den vollständigen Bild-Textencoder. |
| krea2-turbo-i2i.json | Konventioneller KREA-Turbo-Bild-zu-Bild-Workflow, 12 Nodes, Denoise 0,6. Erwartet `krea2_turbo_bf16.safetensors`, die unter diesem Namen im geprüften Projektbestand fehlt. Optionale Darkbrush-LoRA ist umgangen. Als unveränderte Referenz nach `E:\MORPH-Studio\workflows\Desktop-Krea2-Turbo-I2I-Original.json` kopiert; kein aktives MORPH-Profil daraus behauptet. |

In diesem Ordner liegen fünf Dateien und keine weiteren Video-Basismodelle. Die drei Übereinstimmungen anhand von Größe und Header beweisen passende Struktur und Länge; die vollständigen großen Gewichtsdaten wurden nicht erneut gehasht oder verglichen.

## Flux2-Dateien: exakte aktuelle Ablage

`qwen_3_8b_fp8mixed.safetensors`:

```text
E:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\models\checkpoints\qwen_3_8b_fp8mixed.safetensors
```

`flux2-vae.safetensors` besitzt im geprüften Projekt zwei Verzeichniseinträge:

```text
E:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\models\checkpoints\flux2-vae.safetensors
E:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\models\diffusion_models\flux2-vae.safetensors
```

Passende Loader-Ordner wären `models/text_encoders/` für den Qwen-Textencoder und `models/vae/` für den Flux2-VAE. Hier wurde keine Umordnung vorgenommen. Die zwei VAE-Einträge wurden nicht als unabhängige physische Kopien bestätigt.

## ONNX Runtime

`C:\Users\USER\Desktop\onnxruntime-win-x64-gpu_cuda13-1.29.0` ist ein entpacktes natives Windows-Paket der ONNX Runtime, Versionsdatei **1.29.0**: 41 Dateien, insgesamt 1.152.434.796 Bytes. Es enthält C/C++-Header, Importbibliotheken, CUDA-/TensorRT-/Shared-DLLs und große Debug-Dateien mit Endung `.pdb`. Es enthält kein `.onnx`-Modell, kein Python-Wheel und keinen Programmstarter.

ONNX Runtime führt KI-Modelle aus; der CUDA-Anbieter ermöglicht Berechnungen auf NVIDIA-GPUs. Das Paket ist damit unterstützende Software und kein auswählbares Bild- oder Videomodell. In den geprüften MORPH-UI-, Workflow- und Startdateien wurde kein Bezug zu diesem Desktop-Ordner gefunden. Daraus folgt keine Aussage über andere Programme auf dem Rechner. Das Paket wurde nicht installiert oder zur MORPH-Laufzeit hinzugefügt.

Primärquellen: [ONNX Runtime CUDA](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html), [native C/C++-Nutzung](https://onnxruntime.ai/docs/get-started/with-cpp.html).

## Weitere vorhandene Video- und Bildvorlagen

Das bereits eingebundene Videomodell ist Wan 2.2 Remix I2V 14B mit zusammengehörigem High-/Low-Paar. UMT5, Wan-VAE, RIFE-Gewichte und Remacri-Upscaler sind vorhanden; die zugehörigen Nodes sind im regulären Dienst auf Port 8188 geladen. Die zusätzliche als WAN-High bezeichnete Datei in `checkpoints/` ist laut Header eine LoRA, kein zweites Video-Basismodell. Ihre Verwendung benötigt eine gesonderte LoRA-Anbindung.

FireRed- und Flux2-Klein-GUI-Vorlagen sind gespeichert, aber keine direkt verwendbaren MORPH-Profile: FireRed fehlen Transformer, vollständiger Qwen2.5-VL-Encoder und Lightning-LoRA am erwarteten Pfad. Flux2 Klein fehlen unter anderem der im Workflow verlangte Basis-Checkpoint und die referenzierte LoRA; zudem sind die oben genannten Komponenten falsch abgelegt. Diese Vorlagen wurden nicht als fertig oder erfolgreich gerendert dargestellt.
