# Modellrecherche für MORPH: Fotos bearbeiten und kurze Videos aus Bildern

Stand: 15. Oktober 2026. Auftrag: geeignete lokal ausführbare, als unzensiert beziehungsweise erwachsenenfähig angebotene Modelle für die vorhandene Hardware bewerten. Reine Recherche und lesende Bestandsprüfung; keine Modellgewichte heruntergeladen, keine Modelle geladen oder ausgeführt, keine Dienste verändert. FireRed bleibt pausiert. Dieser Bericht ergänzt die vorhandenen Dateien.

**Empfehlung:** Als nächsten Fotoeditor das vorhandene **Noct Q V4 Base auf Qwen Image 2.1** prüfen. Den bereits funktionierenden **KREA 2 Edit SNOFS Q5** als Vergleich behalten. Für kurze Bild-zu-Video-Clips zuerst das vorhandene **Wan2.2-Remix I2V v2.0 FP8 High/Low** verwenden. Das ist eine begründete Reihenfolge für die nächste Bewertung, kein behaupteter Qualitätsgewinn ohne Vergleichstest.

## Tatsächlich geprüfte Hardware und Bestand

| Merkmal | Aktuell lesend geprüft |
|---|---|
| Grafikkarte | NVIDIA GeForce RTX 4080, 16.376 MiB Grafikspeicher |
| Prozessor | AMD Ryzen 7 7800X3D, 8 Kerne / 16 Threads |
| Arbeitsspeicher | 48 GB verbaut; Windows meldet 50.635.874.304 nutzbare Bytes |
| Freier Speicher E: | 78.881.353.728 Bytes, rund 79 GB |
| Momentan freier Grafikspeicher | 3.023 MiB |
| Momentan freier Arbeitsspeicher | rund 20,9 GB |

Freier Speicher ist eine Momentaufnahme. Die 16 GB Gesamtspeicher der Karte stehen derzeit nicht vollständig für eine neue Berechnung bereit. Keine fremden Modelle oder Prozesse wurden beendet.

Dateigrößen bezeichnen belegte Modelldaten auf dem Datenträger. Sie sind keine Messung des maximalen GPU- oder RAM-Bedarfs. Referenzbilder, Zwischenwerte, Cache und Decoder benötigen ebenfalls Speicher. Gewichte können dafür phasenweise zwischen RAM und GPU wechseln.

| Bereits vorhandene Kombination | Modelldaten insgesamt | Einordnung |
|---|---:|---|
| KREA Edit Q5 + Qwen3-VL-4B FP8 + Qwen-Image-VAE | 16,16 GB | Der konkrete Editworkflow lief bereits auf diesem Rechner |
| Noct Q V4 FP16 + vorhandener Qwen-2.1-Encoder + eigener Qwen-2.1-VAE | 24,26 GB | Die Gewichte passen nicht vollständig gleichzeitig in 16 GB VRAM; Auslagerung nötig |
| Wan2.2-Remix v2.0 High/Low FP8 + NSFW-UMT5 FP8 + Wan-2.1-VAE | 35,57 GB | Phasenweise Verarbeitung und Auslagerung sind wesentlich |

Die Noct-Ablagen unter checkpoints und morph-ui-qwen21 wurden zuvor als Hardlinks eingerichtet. Gleiche Dateinamen an diesen Stellen belegen daher keine zusätzliche vollständige Kopie. In dieser Recherche wurden nur Größe und bei ausgewählten Safetensors der kleine Dateikopf gelesen, keine vollständigen Modell-Hashes berechnet.

## Was „unzensiert“ tatsächlich belegt

Es sind drei getrennte Fragen: Prüft eine Anwendung Ein- oder Ausgaben mit einem Filter? Wurden die Bildgewichte für zusätzliche Darstellungen verändert? Setzt das Modell eine konkrete Bearbeitung überzeugend um und erhält dabei die Person? Keine dieser Eigenschaften beweist automatisch die beiden anderen.

Bei **Noct Q** beschreibt der Autor modifizierte Transformergewichte und ausdrücklich Erwachsenenfähigkeit. Er bestätigt auch Bildbearbeitung mit denselben Dateien. Das konkrete Verfahren und ein Vergleich zur Gesichtserhaltung werden nicht offengelegt. Deshalb ist „modifizierter Ableger“ belegt; ein neues Training mit offengelegten Daten ist es nicht. [Noctalunas Originalkarte](https://huggingface.co/Noctaluna/Noct-Q-Uncensored-Qwen-Image-2.1?not-for-all-audiences=true)

Ein Gegenbeispiel liefert AtomicChat: Dort wurde der Textencoder verändert, nicht der Bildgenerator. Die eigene Untersuchung fand bei 45 sensiblen Bildprompts keinen veränderten Erfolg gegenüber dem Originalencoder. Auch diese Untersuchung ist ein Autorentest, kein allgemeiner Nachweis für jede Eingabe. Ein verändertes Chat-Verweigerungsverhalten ist folglich keine ausreichende Begründung für einen Wechsel des Fotoeditors. [AtomicChat: Methode und Messwerte](https://huggingface.co/AtomicChat/Qwen-Image-2.1-Turbo-Uncensored-GGUF)

## Fotoempfehlung: Noct Q V4 Base als nächster Vergleich

Die vorhandene FP16-Datei umfasst **14.230.280.400 Bytes**. Ihr Header enthält F16-Gewichte. Die Größe stimmt exakt mit der vom Publisher angebotenen V4.0-Base-FP16-Datei überein; Veröffentlichung laut Versionsmetadaten: **30. September 2026**. Das ist eine belastbare Zuordnung, aber ohne Hashvergleich kein Beweis vollständiger Byteidentität. [Originale Versionsmetadaten](https://civitai.com/api/v1/model-versions/3372040)

Qwen Image 2.1 ist grundsätzlich ein gemeinsames Generierungs- und Editmodell mit einem 7B-Bildgenerator. Der Hersteller beschreibt Referenzbilder und lokale Änderungen sowie Erhalt von Personen- und Produktidentität. Das belegt den vorgesehenen Funktionsumfang der Basis, nicht automatisch die Identitätstreue des Noct-Ablegers. [Qwen: Originalmodell und Speicheroptimierung](https://huggingface.co/Qwen/Qwen-Image-2.1)

Für MORPH fehlt dafür derzeit die passende Bedienung: **„Bild mit Qwen erstellen“ hat keine Fotoeingabe.** Der frühere erfolgreiche 512×512-Render mit Noct war Text-zu-Bild. Er belegt weder die neue Editfunktion noch die Qualität eines bearbeiteten Personenfotos. KREA besitzt bereits ein eigenes Editprofil.

Die native ComfyUI-Editvorlage verbindet das Referenzfoto mit dem Qwen-2.1-Encoder und der zugehörigen VAE-Konditionierung. Der Sampler muss das zum Editnode gehörende Latent verwenden. Ein beliebiges leeres Latent anderer Größe kann die Ausrichtung verändern. [Offizieller Editablauf](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1), [Nodebeschreibung](https://github.com/Comfy-Org/docs/blob/main/built-in-nodes/TextEncodeQwenImage21.mdx)

Für einen ersten Vergleich sind die bereits vorhandenen FP16-Gewichte, der vorhandene quantisierte Encoder und die vorhandene VAE ausreichend vorbereitet; ein zusätzlicher Modelldownload ist keine Voraussetzung. Die vorhandenen Gewichte summieren sich auf rund 24,26 GB. RAM-Auslagerung ist damit für die 16-GB-Karte einzuplanen. Eine konkrete Editlaufzeit oder maximale Auflösung auf diesem Rechner ist noch nicht gemessen.

Später kann **Noct V4 INT8 ConvRot mit rund 7,3 GB** eine Speicheroption sein. Der Autor empfiehlt sie für kleinere Karten. Das ist eine andere Speicherung der Gewichte und kein belegtes Upgrade für Gesichtstreue. Erst ein konkreter Speicher- oder Laufzeitengpass begründet hier einen weiteren Download. Die Modellkarte weist auf die Qwen Research License und nichtkommerzielle Nutzung hin. [Noct-Dateien und Lizenzhinweis](https://huggingface.co/Noctaluna/Noct-Q-Uncensored-Qwen-Image-2.1?not-for-all-audiences=true)

## Vorhandene Alternative: KREA 2 Edit SNOFS Q5

Für diesen konkreten Aufbau existiert bereits lokale Lauf-Evidenz: zweimal erfolgreiche Shirt-Farbänderung bei 768×768, acht Schritten und CFG 1. Dabei wurde das Gesicht sichtbar neu interpretiert. Referenzstärke 4 zeigte im einzelnen Vergleich keinen erkennbaren Vorteil. Die zweite Laufzeit war durch andere Cache-/Ladebedingungen kein sauberer Geschwindigkeitsvergleich.

Die Original-Identity-Edit-LoRA ist ein inoffizieller, auf SFW-Daten trainierter Editor. Der Autor nennt Grenzen bei markanten Gesichtsproportionen, zwei Personen und rein lokalen Änderungen. SNOFS und Identity Edit sind deshalb getrennte Beiträge zum verwendeten Merge; der Name verspricht keine perfekte Personenerhaltung. [Identity Edit: Originalautor und Grenzen](https://huggingface.co/conradlocke/krea2-identity-edit)

Die Editnodes führen das Foto sowohl als VAE-Referenz als auch über Qwen3-VL zu. Der Autor empfiehlt Turbo für viele Änderungen; große Entfernungen benötigen häufig RAW und andere Guidance. Das ist eine Einschränkung der Turbo-Arbeitsweise und keine Aufforderung, jetzt weitere Gewichte zu laden. [Originalnodes](https://github.com/lbouaraba/comfyui-krea2edit)

Das zusätzlich vorhandene **SNOFS Krea2 Turbo v1.4** mit 12.829.186.855 Bytes ist laut Autor INT8 ConvRot. Der lokale Header bestätigt quantisierte I8/U8-Gewichte mit BF16/F32-Anteilen. Es ist ein weiterer Generierungscheckpoint und kein Austausch für den getesteten Editgraphen. [Publisher-Metadaten](https://civitai.com/api/v1/models/2416142)

Die nachvollziehbaren bisherigen KREA-Ergebnisse und Integrationsgrenzen stehen zusätzlich im [lokalen Ergebnisbericht](E:/MORPH-Studio/reports/krea-ui-20261015/Ergebnis.md).

## Videoempfehlung: vorhandenes Wan2.2-Remix I2V zuerst bewerten

Der Originalautor dokumentiert zusätzliche NSFW-LoRAs und Bewegungstraining. Das ist für den gewünschten Inhalt aussagekräftiger als ein bloßer Textencoder-Tausch. Deine vorhandene Version ist **I2V v2.0**; die aktuell belegte Autorversion ist **I2V v3.0**, mit angekündigten Verbesserungen an Konsistenz und Stabilität. Ein unabhängiger Vergleich auf deinen Fotos fehlt. [Originalkarte und Änderungsprotokoll](https://huggingface.co/FX-FeiHou/wan2.2-Remix/blob/main/README.md)

Vorhanden sind beide FP8-Diffusionsdateien zu je **14.291.272.136 Bytes**, der empfohlene NSFW-UMT5-XXL-Encoder mit **6.735.887.993 Bytes** und die Wan-2.1-VAE mit **253.815.318 Bytes**. Zusammen: **35.572.247.583 Bytes**. Der Header des High-Modells bestätigt FP8 E4M3. High und Low bezeichnen die beiden Rauschphasen. [Autor-Dateimetadaten](https://huggingface.co/api/models/FX-FeiHou/wan2.2-Remix?blobs=true)

Der vorhandene MORPH-API-Workflow verwendet das vollständige Paar mit Blockauslagerung, Bildkonditionierung, acht Schritten und einer Umschaltung nach vier Schritten. Gespeicherte Ausgangswerte: 512×512 und 81 Frames. Im Anschluss gibt es getrennte Videoausgabe, Bildzwischenrechnung und Upscaling. Höhere Ausgabe-FPS durch Zwischenbilder sind keine zusätzliche vom Videomodell verstandene Bewegung.

16 GB sind für diesen Ablauf grundsätzlich plausibel, aber nicht durch die Dateigröße bewiesen. Comfy dokumentiert Windows-Tests mit zwei Wan-14B-Modellen in FP8/FP16, RTX 5060 und 32/64 GB RAM. Der Test lag bei **320×320 und 81 Frames**. Das belegt die technische Wirkung dynamischer Auslagerung, keine Remix-Laufzeit bei 512 oder 720p auf einer RTX 4080. [Comfy: Dynamic VRAM](https://blog.comfy.org/p/dynamic-vram-in-comfyui-saving-local)

Die häufig zitierte **8-GB-Angabe** der nativen Wan-Anleitung betrifft das **5B-Modell**, nicht pauschal das 14B-High/Low-Paar. Zudem verwendet die native 14B-I2V-Familie die Wan-2.1-VAE; das 5B-VAE ist nicht austauschbar. [Offizielle Wan2.2-Anleitung](https://docs.comfy.org/tutorials/video/wan/wan2_2)

Ein zusätzlich aufbewahrtes v3.0-Paar würde rund **28,58 GB** kosten. Vor einem solchen Download ist es sinnvoller, erst v2.0 an einem kurzen Clip auf Bewegung, Gesichtserhaltung und Speicherbedarf zu bewerten. Für beide Aufgaben sollte jeweils ein Modellablauf laufen. In dieser Recherche wurde kein Video erzeugt.

## Weitere geprüfte Kandidaten und warum sie zurückstehen

| Kandidat | Quellenbefund | Entscheidung für dieses System |
|---|---|---|
| FireRed Image Edit 1.1 | Offizieller Fokus auf Identität und Editqualität; kein belastbares Versprechen als unzensiertes Modell | Als allgemeiner Editor interessant; der pausierte Download löst nicht nachweislich die jetzige Inhaltsanforderung |
| Qwen Edit Rapid AIO | Autor unterscheidet NSFW/SFW und empfiehlt v19 eher für Editkonsistenz, v23 eher für Prompttreue | Vergleichskandidat; kein belegter Vorrang gegenüber den vorhandenen Dateien |
| ChrisColeTech Qwen Edit Uncensored v1.1 | Aktueller Dateibaum enthält FP8-Safetensors, keinen verifizierten v1.1-GGUF; Diffusionsfile rund 20,44 GB | Widersprüchliche Bereitstellungsangaben, zusätzlich hoher Platz- und Auslagerungsbedarf |
| FLUX.2 Klein | Generierung und Edit möglich; konkrete Speicherwerte hängen stark von Variante und Quantisierung ab | 4B wäre die leichtere Familie; kein Nachweis einer überlegenen unzensierten Fotobearbeitung |
| Ponpoke Klein „uncensored“ | Verändert den Qwen3-Textencoder; Autor nennt fehlendes Bildwissen als eigene Grenze | Kein ausreichender Grund für einen weiteren Stack nur wegen des Namens |
| LTX-2.3 Uncensored v1.4 | Dokumentierter Erwachseneninhalte-Merge, Bild-zu-Video und Audio; kleinstes geprüftes Paket rund 25,61 GB | Experimentelle spätere Ton-/Videooption; vollständiger 16-GB-Ablauf hier ungetestet |
| HunyuanVideo 1.5 / Rapid AIO | Tencent nennt 14 GB mit Auslagerung in Linux; Rapid-AIO-Autor beendet Pflege | Kein überzeugender Vorteil für den jetzigen Windows-/Inhaltszweck |
| Z-Image Turbo | Gut belegte kompakte Generierung; dediziertes Editmodell im offiziellen Modellzoo weiterhin als noch zu veröffentlichen bezeichnet | Generierungsleistung allein beantwortet die Anforderung Fotobearbeitung nicht |

Die FireRed-Karte beschreibt 20B und Bildbearbeitung. Die beworbene schnelle Ausführung nutzt 30 GB VRAM; das ist kein RTX-4080-Benchmark. [FireRed Originalquelle](https://huggingface.co/FireRedTeam/FireRed-Image-Edit-1.1)

Beim Rapid-AIO sind neuere Versionsnummern ausdrücklich nicht automatisch die Wahl für konsistente Edits. [Phr00ts Originalkarte](https://huggingface.co/Phr00t/Qwen-Image-Edit-Rapid-AIO?not-for-all-audiences=true)

Beim ChrisColeTech-v1.1 widersprechen sich README und aktuell gelistete Dateien. Der Dateibaum enthält Diffusion **20.436.214.320 Bytes**, Encoder **8.293.097.832 Bytes** und VAE **253.806.246 Bytes**. Die ältere Version bietet Q4_K_M mit **11.657.701.984 Bytes**, räumt aber selbst Edit-Schwächen ein. [v1.1-Dateibaum](https://huggingface.co/api/models/ChrisColeTech/qwen-image-edit-uncensored-v1.1-GGUF/tree/main?recursive=true&expand=false), [ältere Originalkarte](https://huggingface.co/ChrisColeTech/qwen-image-edit-uncensored-GGUF/raw/main/README.md)

Black Forest Labs nennt je nach Seite und Messaufbau verschiedene Speicherwerte. Die Produktseite listet für Klein 9B bereits mehr als 16 GB; Quantisierung und Auslagerung wären nötig. Daraus folgt kein verlässlicher Qualitätsvorteil für diesen Zweck. Der vorhandene **qwen_3_8b_fp8mixed** gehört zur FLUX-2-Klein-9B-Familie; er ersetzt weder KREAs Qwen3-VL-4B noch den Qwen-Image-2.1-Encoder. [BFL Variantenvergleich](https://bfl.ai/models/flux-2-klein), [Ponpoke: veränderte Komponente und Grenzen](https://huggingface.co/ponpoke/flux2-klein-9b-uncensored-text-encoder)

LTX erfordert neben dem Diffusionsmodell weitere Encoder-/Projektions- und VAE-Dateien. Das geprüfte Q4-v1.4-Paket kostet rund 25,61 GB, ohne hier eine gemessene 16-GB-Laufgarantie zu liefern. [Autorquelle und Pakete](https://huggingface.co/ChrisColeTech/LTX-2.3-uncensored-v1.4-FP8/blob/main/README.md), [Original LTX-2.3](https://huggingface.co/Lightricks/LTX-2.3)

Hunyuan- und Z-Image-Einordnung: [Tencent-Systemanforderungen](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5#-system-requirements), [Rapid-AIO-Autorhinweis](https://huggingface.co/Phr00t/HunyuanVideo-1.5-Rapid-AIO), [Tongyi-MAI-Modellzoo](https://github.com/Tongyi-MAI/Z-Image)

## Konkrete nächste Stufe, noch nicht ausgeführt

1. Das vorhandene Noct-Modell mit einem eigenen Foto-Editprofil zugänglich machen; KREA und vorhandene Bilder bewahren.
2. Nach gesonderter Freigabe dieselbe harmlose Änderung an demselben synthetischen Personenbild mit Noct und KREA vergleichen: Gesicht, unbearbeitete Regionen, Auflösung, Gesamtlaufzeit und Speicherbedarf erfassen. Ein Erfolg der Änderung allein reicht nicht als Identitätsnachweis.
3. Anschließend einen kurzen Wan-v2.0-Clip mit festgelegter Auflösung und Framezahl bewerten. Danach erst entscheiden, ob eine andere Quantisierung oder Version einen konkreten Engpass löst.

Diese Reihenfolge benötigt zunächst **keinen zusätzlichen Download von Modellgewichten**. Kein Kandidat hat in dieser Recherche einen neuen Qualitätstest bestanden; bestehende Laufbelege und neu recherchierte Autorenangaben sind ausdrücklich getrennt. Die laufende operative Pause bleibt bestehen.
