# KREA 2 Edit: Quellen und Grenzen

Stand: 15.10.2026. Dieses Dokument hält öffentliche Primärquellen, die gewählten Testparameter und statische Kompatibilitätsbefunde fest. Es bewertet keinen Bildlauf. Ausführungsstatus und Ergebnis gehören in den separaten Ausführungsbericht.

## Offizielle Vorlage und unser einzelner Test

Quellen: [Node-README](https://github.com/lbouaraba/comfyui-krea2edit/blob/main/README.md), [Workflow krea2_identity_edit.json](https://github.com/lbouaraba/comfyui-krea2edit/blob/main/workflows/krea2_identity_edit.json), [Identity-Edit-Modellkarte](https://huggingface.co/conradlocke/krea2-identity-edit).

| Einstellung | Offizielle Vorlage bzw. Empfehlung | Unser Test |
|---|---|---|
| Modell | Vorlage: Krea 2 Turbo FP8 plus Identity Edit v1.2 | vorhandener SNOFS-Merge Q5_1; keine zusätzliche Identity-LoRA |
| Ausgabe | Vorlage etwa 1 MP; README höchstens 2 MP | 768 × 768, ein Bild |
| Schritte / CFG | Vorlage 10 / 1; README Turbo 8 / 1; Modellkarte 8–12 / 1 | 8 / 1 |
| Sampler / Zeitplan / Denoise | euler / simple / 1 | euler / simple / 1 |
| Referenzstärke | README-Grundwert 1; Workflow empfiehlt 4 für stärkere Ähnlichkeit | ref_boost 1; ref_boost_a 1 |
| Bildgrundierung / Geometrie | 768 / fit | 768 / fit |
| Zufallsstartwert | Vorlage zufällig | fest: 20261015 |

Der Bearbeitungsauftrag lautet, an einem synthetischen Erwachsenenporträt nur das rote T-Shirt dunkelblau zu färben. Die tatsächlichen Veränderungen bewertet der separate Ausführungsbericht. Beide Edit-Nodes bleiben aktiv. Der Textencoder ist qwen3vl_4b_fp8_scaled mit Typ krea2; der negative Bildencoder erhält dasselbe Bild und einen leeren Text. target_latent erhält denselben leeren Ausgangslatent wie der Sampler. Laut README vermeidet diese Verbindung eine VAE-Codierung mitten im Sampling und mögliche nachfolgende CPU-Auslagerung bei knappem Grafikspeicher.

Die Raw-Angaben sind nicht einheitlich: Das README und die Modellkarte nennen für Entfernen großer Inhalte etwa 20 Schritte und CFG 3; die Notiz im Workflow nennt Raw mit 40 Schritten und CFG 3–4. Die Turbo-Einstellung des Tests darf deshalb nicht als bestätigte Empfehlung für jeden Krea-Merge dargestellt werden.

Gesicherte lokale Quellenkopien: [README](official-node-README.md), [Originalworkflow](official-workflow-original.json). Die tatsächlichen Testwerte stehen in [submitted-request.json](submitted-request.json); die Vorbereitung in [preflight.json](preflight.json).

## Herkunft des konkreten Merges bleibt teilweise offen

Die [Civitai-Seite des Merges v1.0](https://civitai.red/models/2950620/krea-2-edit-snofs-merge?modelVersionId=3341696) verlangt bei unserem öffentlichen Zugriff eine Anmeldung. Originalseite und öffentliche API lieferten Zugriffsfehler. Das ist eine Zugriffsgrenze, kein Nachweis, dass das Modell fehlt.

Die dem Autor zugeschriebene Aussage lautet, Identity Edit v1.2 und SNOFS seien bereits eingebaut. Diese Aussage konnte hier nicht anhand einer zugänglichen Primärmodellkarte unabhängig bestätigt werden. Ebenso bleibt offen, ob der konkrete Merge auf Turbo oder Raw beruht. Name, Dateigröße und GGUF-Architektur beweisen beides nicht. 8 Schritte und CFG 1 sind daher eine unbestätigte Turbo-Annahme für diesen begrenzten Test. Der Nutzerauftrag, zunächst keine zusätzliche Identity-LoRA anzuwenden, bleibt maßgeblich.

## Der passende VAE

Der [offizielle Krea-Code](https://github.com/krea-ai/krea-2/blob/main/autoencoder.py) verwendet den Qwen-Image-VAE mit 16 Latentkanälen und achtfacher räumlicher Kompression. Die [Comfy-Org-Krea-Datei](https://huggingface.co/Comfy-Org/Krea-2/blob/main/vae/qwen_image_vae.safetensors) hat exakt **253.806.246 Bytes** und SHA256:

`a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f`

Die lokale Datei wurde gegen diese Größe und Prüfsumme geprüft; Nachweis: preflight.json. Die ältere Qwen-Image-ComfyUI-Veröffentlichung enthält dieselbe Datei mit derselben Prüfsumme.

Der vorhandene Wan-2.1-VAE besitzt zwar passende Grunddimensionen, ist aber kein belegter gleichwertiger Ersatz: Der [Qwen-Bericht, Abschnitt 2.3](https://arxiv.org/html/2508.02324v1#S2.SS3), beschreibt einen eingefrorenen Wan-Encoder und einen für Bilder nachtrainierten Decoder. Unterschiedliche Dateiprüfsummen allein wären dafür kein ausreichender Beleg.

Der Qwen-Image-2.1-VAE ist strukturell inkompatibel: [offizielles Projekt](https://github.com/QwenLM/Qwen-Image-2.1) und [ComfyUI-Erkennung](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/sd.py) beschreiben 64 Latentkanäle, Faktor 16 und RGBA. Krea benötigt 16 Kanäle und Faktor 8.

## Begrenzte Loader-Anpassung

Der installierte GGUF-Loader kannte die Architektur krea2 nicht. Geändert wurde ausschließlich die Architekturliste in loader.py: krea2 wurde zu IMG_ARCH_LIST ergänzt. Vorbild ist der ursprüngliche [Krea-Unterstützungscommit 16ddaa43a1a25b66e9ee7f02e9a4d97e759cba63](https://github.com/molbal/ComfyUI-GGUF/commit/16ddaa43a1a25b66e9ee7f02e9a4d97e759cba63).

Die konkrete Datei enthält 256 Q5_1- und 174 F32-Tensoren, keine BF16-Tensoren. Textprojektor und zweidimensionale Modulation besitzen die erwarteten Dimensionen. Q5_1-Decodierung und ihre Hilfsfunktionen stimmen strukturell mit [molbal-Stand f1d050fac00b0505cba519e44ad7fb18c34318b0](https://github.com/molbal/ComfyUI-GGUF/tree/f1d050fac00b0505cba519e44ad7fb18c34318b0) überein. Daraus ergab sich für diesen Test kein weiterer erforderlicher Eingriff in nodes.py, ops.py oder dequant.py. Dies ist ein statischer Befund und kein Laufzeitnachweis.

Sicherung: [GGUF-loader.py.before](GGUF-loader.py.before). Änderungsnachweis: [loader-change.json](loader-change.json).

- SHA256 vorher: ffff39d209ce22654e67378b80c6a3ca3d349cf8f00ec267085bd16e194730c2
- SHA256 nachher: 240c151ed58f16111597306bc8993997303595d449729fed86de9aec9ec49ce1