# MORPH Studio – Bedienung der Bild-Workflows

## Starten und einen Workflow öffnen

1. Wenn ComfyUI bereits läuft, direkt mit Schritt 2 fortfahren. Sonst `E:\MORPH-Studio\MORPH-Start.cmd` starten und das gestartete Fenster während der Arbeit geöffnet lassen.
2. [ComfyUI auf diesem PC](http://127.0.0.1:8188) öffnen.
3. Im Workflow-Menü einen der beiden gespeicherten Workflows öffnen. Falls er dort nicht angeboten wird, die entsprechende Datei aus `E:\MORPH-Studio\workflows` in das Browserfenster ziehen:

| Datei | Zweck |
|---|---|
| `Phase2-1-Fotobild-SDXL.json` | Ein neues Bild aus einer Textbeschreibung erzeugen. |
| `Phase2-2-Bildbearbeitung-Kontext.json` | Ein vorhandenes Bild mit einer Textanweisung bearbeiten. |

Zum Starten auf **Queue / Ausführen** klicken oder **Strg + Eingabe** drücken. Der erste Lauf nach einem Modellwechsel kann länger dauern, weil das Modell zunächst geladen wird. Während eines laufenden Bildes nicht mehrfach auf Ausführen klicken: Jeder Klick kann einen weiteren Auftrag einreihen.

## Ein neues Fotobild erzeugen

Im SDXL-Workflow steht die gewünschte Bildbeschreibung im oberen Knoten **Text / Bearbeitungsanweisung**. Der zweite Textknoten enthält Dinge, die vermieden werden sollen, beispielsweise Unschärfe oder ein Wasserzeichen. Beide Texte können geändert werden.

Der vorbereitete Workflow beschreibt eine rote Keramiktasse auf einem Holztisch am Fenster. Für die ersten eigenen Bilder zunächst nur den positiven Beschreibungstext ändern und die übrigen Einstellungen beibehalten.

## Ein vorhandenes Bild bearbeiten

Im Kontext-Workflow unter **1 · Eingabebild wählen** das gewünschte Bild auswählen oder über den Upload-Knopf ein Bild vom PC laden. Danach im Knoten **Text / Bearbeitungsanweisung** genau beschreiben, was geändert werden soll und welche Merkmale erhalten bleiben sollen.

Die offizielle Kontext-Anleitung verlangt englische Anweisungen. Zwei kopierbare Beispiele für ein Eingabebild mit einer roten Tasse:

**Tasse blau färben:**

```text
Change the red ceramic mug to a glossy cobalt blue ceramic mug. Keep the shape of the mug, its handle, the camera angle, the window, lighting, wooden table and background unchanged. Maintain a realistic photograph.
```

**Tasse grün färben:**

```text
Change the red ceramic mug to a glossy emerald green ceramic mug. Keep the mug shape, handle, table, window, lighting and composition unchanged. Maintain a realistic photograph.
```

Diese Anweisungen passen zu einer roten Tasse. Für andere Eingabebilder den Gegenstand und die zu erhaltenden Merkmale entsprechend ersetzen. Eine einzelne Änderung pro Lauf lässt sich leichter prüfen. Die Aufforderung, bestimmte Bereiche beizubehalten, ist keine Garantie unveränderter Pixel; das Ergebnis immer mit dem Eingabebild vergleichen.

## Größe und Einstellungen

Im Knoten **Ausgabegröße** Breite und Höhe ändern. **1024 × 1024** ist die vorbereitete Standardgröße. **768 × 768** ist als kleinere Variante vorgesehen und erzeugt weniger Bildpunkte. Bei Kontext wird das Referenzbild zuvor automatisch auf eine passende Modellgröße gebracht; die Ausgabegröße wird separat eingestellt.

| Einstellung | Bedeutung und Bedienung |
|---|---|
| **Seed** | Startwert des Zufalls. Mit identischem Seed und identischen übrigen Einstellungen lassen sich Varianten besser vergleichen. Ein anderer Seed erzeugt eine andere Variante. Der zusätzliche Schalter **fixed** hält den Seed nach einem Lauf fest. Gleiche Seeds allein garantieren keine identischen Bilder über unterschiedliche Softwareversionen hinweg. |
| **Steps / Schritte** | Anzahl der Berechnungsschritte. Mehr Schritte brauchen mehr Zeit und verbessern das Ergebnis nicht automatisch. Zunächst die vorbereiteten Werte verwenden. |
| **Sampler / Sampling** | Verfahren für die schrittweise Bildberechnung. SDXL verwendet **dpmpp_2m**, Kontext **euler**. Zunächst beibehalten. |
| **Scheduler** | Verteilt die Berechnungsschritte über den Rauschverlauf. Vorbereitet sind **karras** für SDXL und **simple** für Kontext. |
| **CFG** | Bei SDXL bestimmt dieser Wert, wie stark der Text die Berechnung beeinflusst. Im Kontext-Workflow bleibt **CFG = 1,0**; dessen separate Anweisungsstärke wird über **FluxGuidance** eingestellt. |
| **FluxGuidance / Anweisungsstärke** | Kontext-spezifische Stärke der Textanweisung. Vorbereitet ist **2,5**. Höhere Werte sind keine Zusage besserer Erhaltung oder Qualität. |
| **Denoise** | Umfang der schrittweisen Berechnung. In beiden vorbereiteten Workflows **1,0** lassen. Kontext erhält das Eingabebild über einen eigenen Referenzpfad; eine Senkung dieses Werts ist hier kein geprüfter Regler zum Erhalten des Originals. |

## Geprüfte Testfälle und Prüfstand

Alle drei folgenden Testfälle wurden erfolgreich lokal berechnet und anschließend visuell geprüft. Das SDXL-Bild ist fotografisch plausibel; die Kontext-Tasse wurde tatsächlich blau beziehungsweise grün. Die übrigen Bildteile bleiben wiedererkennbar, wurden aber teilweise verändert. Technischer Erfolg und inhaltliche Bildbewertung sind deshalb im Phase-2-Bericht getrennt dokumentiert.

| Testfall | Ausgabe | Seed | Schritte | Sampler / Scheduler | CFG | FluxGuidance | Gemessene ComfyUI-Laufzeit |
|---|---:|---:|---:|---|---:|---:|---:|
| SDXL-Fotobild | 1024 × 1024 | 42 | 30 | dpmpp_2m / karras | 6,5 | – | 8,92 s |
| Kontext: blaue Tasse | 1024 × 1024 | 42 | 20 | euler / simple | 1,0 | 2,5 | 41,28 s |
| Kontext: grüne Variante | 768 × 768 | 84 | 24 | euler / simple | 1,0 | 2,5 | 26,10 s |

Die beiden gespeicherten Workflows öffnen mit den Standardwerten der ersten beziehungsweise zweiten Tabellenzeile. Für die grüne Variante im Kontext-Workflow den zweiten Beispieltext einsetzen sowie Größe, Seed und Schritte wie in der dritten Zeile ändern.

Auch die native Kontext-Verkabelung und die Zuordnung der FP8-Modelldateien zur offiziellen ComfyUI-Vorlage sind geprüft. Die Speicherbeobachtungen stehen im Phase-2-Bericht. Andere Größen, Sampler, Scheduler, CFG-Werte, Guidance-Werte, Schrittzahlen und größere Bildserien sind hier nicht als getestet ausgewiesen. Die Laufzeiten sind Einzelmessungen: Die kleinere Variante lief mit bereits geladenem Modell und änderte außerdem Seed und Schrittzahl. Die Werte erlauben deshalb keinen direkten Geschwindigkeitsvergleich der Auflösungen.

Die blaue Bearbeitung verändert zusätzliche Glanzstreifen, Holzstruktur und die Lage von Tasse und Tischkante etwas. Bei der grünen Variante verschieben sich Tasse und Fensterpfosten sichtbar stärker nach rechts; die Tasse und Tischkante liegen außerdem tiefer im Bild. Beide Farbänderungen sind gelungen, die Anweisung zur vollständigen Erhaltung des restlichen Bildes wurde jedoch nur näherungsweise erfüllt. Die Prüfungen belegen die drei konkreten Beispiele, keine allgemeine Qualitätsgarantie.

Ein technisch erfolgreicher Lauf bedeutet, dass ComfyUI ein lesbares Bild in der verlangten Größe gespeichert hat. Für die inhaltliche Abnahme zusätzlich prüfen: Ist die Tasse wirklich in der gewünschten Farbe? Sind Form und Henkel erhalten? Passen Tisch, Fenster, Perspektive und Beleuchtung noch zum Eingabebild?

## Bilder finden und lokal arbeiten

Neue Bilder liegen unter **`E:\MORPH-Studio\output\Phase2`**. Die Dateinamen beginnen beim SDXL-Workflow mit `SDXL_Fotobild`, beim Kontext-Workflow mit `Kontext_Edit`; vorbereitete Varianten verwenden `Kontext_Variation`. ComfyUI ergänzt eine laufende Nummer.

Die Bildberechnung erfolgt auf diesem PC mit lokal gespeicherten Modellen. Die Adresse `127.0.0.1` bezeichnet den eigenen PC. Für diese Workflows wird kein Cloud-Bilddienst benötigt. Downloads sind nur zur Einrichtung beziehungsweise für spätere bewusst vorgenommene Ergänzungen nötig. Ob der komplette Ablauf bei physisch getrenntem Internet geprüft wurde, wird im Abschlussbericht gesondert angegeben.

## Kontext-Lizenz und Quellen

**FLUX.1 Kontext Dev ist für private, nichtkommerzielle und nichtproduktive Nutzung lizenziert.** Kommerzieller oder produktiver Modellbetrieb benötigt eine passende zusätzliche Lizenz von Black Forest Labs. Die grundsätzliche Erlaubnis, erzeugte Bilder auch kommerziell zu verwenden, hebt diese Betriebsbeschränkung nicht auf. Vor einer Weitergabe müssen Outputs nach den Lizenzbedingungen auf rechtswidrige oder rechtsverletzende Inhalte geprüft werden, sofern keine entsprechenden Filter eingesetzt werden. SDXL hat eine andere Lizenz mit eigenen Nutzungsbeschränkungen.

- [Offizielle ComfyUI-Anleitung für den lokalen Kontext-Workflow und englische Anweisungen](https://docs.comfy.org/tutorials/flux/flux-1-kontext-dev)
- [Offizielle Kontext-Workflow-Vorlage](https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/flux_kontext_dev_basic.json)
- [FLUX.1 Kontext Dev: Modellkarte](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev)
- [FLUX.1 Dev Non-Commercial License](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev/blob/main/LICENSE.md)
- [SDXL Base 1.0: Modellkarte](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
- [SDXL: CreativeML Open RAIL++-M License](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/raw/main/LICENSE.md)
