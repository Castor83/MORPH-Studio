# KREA 2 SNOFS: Referenzstärke 1 gegen 4

Stand: 15. Oktober 2026. **Der einzelne Vergleichslauf ist technisch erfolgreich; Stärke 4 verbessert die Gesichtserhaltung in diesem Bildpaar nicht erkennbar.** Das dunkelblaue Shirt gelingt bei beiden Werten.

## Bildvergleich

| Synthetische Vorlage | Referenzstärke 1 | Referenzstärke 4 |
|---|---|---|
| ![Vorlage](../../input/Phase3-Referenz-Erwachsener.png) | ![Stärke 1](../../output/KREA2-Tests/20261015/SNOFS_shirt_blue_00001_.png) | ![Stärke 4](../../output/KREA2-Tests/20261015-Ref4/SNOFS_shirt_blue_ref4_00001_.png) |

Die unabhängige Sichtprüfung und die eigene Sichtung stimmen überein: Gesicht, Haare, Bart, frontale Pose, grauer Hintergrund und Ausschnitt der beiden Ausgaben sind nahezu gleich. Die gegenüber der Vorlage neu gezeichneten Gesichts-, Haut- und Bartdetails bestehen bei Stärke 4 weiterhin. Kleine Unterschiede betreffen vor allem Kragen und Shirtkonturen; der Kragen ist bei Stärke 4 mittig etwas tiefer beziehungsweise kantiger. Keine auffälligen Doppelgesichter oder groben Formfehler.

Aus diesem Paar ergibt sich kein überzeugender Vorteil für Stärke 4. Die bisherige Fassung mit Stärke 1 bleibt erhalten. Das ist eine Sichtbewertung eines einzelnen synthetischen Erwachsenenporträts mit einem festen Seed, keine biometrische Prüfung oder allgemeine Aussage zur Identitätserhaltung.

## Kontrollierter Vergleich

Der Nutzer hat ausdrücklich genau diesen zusätzlichen Vergleich freigegeben. Gegenüber dem ersten Lauf wurde ausschließlich `Krea2EditModelPatch.ref_boost` von **1 auf 4** geändert. Der Ausgabepräfix wurde zusätzlich geändert, damit das neue Bild separat gespeichert wird.

Unverändert: SNOFS-Q5_1-GGUF, vollständiger Qwen3-VL-FP8-Textencoder, Qwen-Image-VAE, keine zusätzliche Identity-LoRA, identische synthetische Eingabe und englische Anweisung, Seed 20261015 fest, 768 × 768, Batch 1, 8 Schritte, CFG 1, Euler/simple, Denoise 1, Grounding 768, `fit`, `ref_boost_a=1`. Die 18 UI-/API-Verbindungen wurden erneut unabhängig geprüft; Sampler und `target_latent` nutzen denselben leeren Latent.

| Nachweis | Ergebnis |
|---|---|
| Prompt-ID | 7973c278-cdd0-4b5b-84f7-696d6cf890ff |
| Ausführung | execution_success; completed=true; keine Node-Validierungsfehler |
| Ausgabe | eine dekodierbare RGB-PNG, 768 × 768 |
| Laufdauer | 24,82 Sekunden laut ComfyUI; 24,818 Sekunden aus Ausführungstimestamps |
| Modellparameter im PNG | stimmen mit der freigegebenen API-Datei überein; serverseitiger LoadImage-Fingerabdruck ausgenommen |
| Erhalt der Ausgangsdateien | Baseline-Workflow, API, Ergebnis und synthetische Eingabe gegen vorher erfasste SHA256 geprüft: unverändert |

Der zweite Lauf nutzte bereits zwischengespeicherte Loader-, Textencoder-, VAE-, Eingabe- und Grounding-Ergebnisse. Seine kürzere Laufzeit gegenüber dem ersten Lauf mit 93,44 Sekunden ist deshalb **kein Beleg, dass Referenzstärke 4 schneller ist**. Es wurde genau ein zusätzlicher Prompt eingereiht und keine weitere Variante berechnet.

## Dateien und Dienst

- [Neuer grafischer Workflow](../../workflows/KREA2-SNOFS-Edit-Ref4-20261015.json), [API-Fassung](../../workflows/KREA2-SNOFS-Edit-Ref4-20261015-api.json)
- [Neues Ergebnis](../../output/KREA2-Tests/20261015-Ref4/SNOFS_shirt_blue_ref4_00001_.png), [erster Testbericht](../KREA2-Edit-20261015/Ergebnis.md)
- [Vorbereitung und exakte Unterschiede](preparation.json), [eingereichter Auftrag](submitted-request.json), [Einreichungsbeleg](submission-receipt.json)
- [Ausführungshistorie](execution-history.json), [Ausgabeverifikation](output-verification.json), [Vergleichsnachweis](comparison-result.json), [unabhängige Sichtbewertung](visual-review.json)

Der Vergleich verwendet die bereits laufende lokale Testinstanz **http://127.0.0.1:8189**. Der neue Workflow liegt zusätzlich in deren gespeichertem Workflow-Menü. Kein Dienstneustart, kein Download, keine Paket-/Loaderänderung, keine Löschung, kein Git-Commit oder Push. Die ursprünglichen Workflow-Dateien und Ergebnisse bleiben erhalten. Die Abschlussprüfung der Warteschlange ist in `final-check.json` dokumentiert.
