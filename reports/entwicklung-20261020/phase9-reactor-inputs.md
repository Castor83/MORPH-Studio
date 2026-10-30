# Phase9: vorhandenes synthetisches ReActor-Bildpaar

Stand: 20.10.2026. Ausschließlich lesende Prüfung; kein Upload, ReActor-/Modelllauf, Download, Dienstaufruf oder neues Bild. Bestehende Originaldateien unverändert. Der geprüfte Harness bleibt eingefroren.

## Entscheidung und Reichweite

**PASS für die technische Eignung als begrenzte ReActor-Regression:** vorhandene synthetische Referenz als Quellgesicht und ihre vorhandene Kontext-Bearbeitungsvariante als Zielbild verwenden. Beide wurden in diesem Review aktuell geöffnet und visuell angesehen: je ein frontal gut sichtbarer Erwachsener ohne Gesichtsverdeckung; Augen, Nase und Mund erkennbar. Eine tatsächliche Erkennung/Verarbeitung durch InsightFace/ReActor bleibt bis zum angekündigten Einzeltest **UNVERIFIED**.

**Begrenzung:** Die beiden Bilder zeigen Varianten derselben künstlichen Figur. Der Test kann die bestehende technische Bildpaar-/Upload-/Face-Detection-/Swap-/Outputfunktion und den Erhalt der übrigen Zielszene prüfen. Er nimmt keinen Transfer zwischen klar verschiedenen Identitäten ab, beweist keine biometrische Identität und keine allgemeine Bildqualität.

## Exakte Rollen und aktuelle Dateien

| Rolle in MORPH | Aktueller absoluter Pfad | Aktuell gelesene SHA-256 |
| --- | --- | --- |
| `source` – Quellgesicht | `E:\MORPH-Studio\input\Phase3-Referenz-Erwachsener.png` | `322448ad502dfc180e3abd0064a29e92acf31704c640b286b71c34353436ad1f` |
| `target` – zu bearbeitende Zielszene | `E:\MORPH-Studio\output\Phase3\Kontext_Identitaet_Hemdfarbe_00001_.png` | `19e2024ad5850e07e929f86d746089a5a6fbc04875c4e19bf0c57086b3b636d5` |

Beide Bilder sind 1024×1024. Die Quelle trägt ein rotes Shirt und hat glattere Haut/Haar-/Bartdarstellung; die Zielvariante ein blaues Shirt, andere Gesichtstextur und einen etwas weiteren Ausschnitt. Das ist eine sichtbare Bilddifferenz innerhalb derselben synthetischen Figur und keine bewiesene unterschiedliche Identität. Zielshirt, grauer Hintergrund und Ausschnitt können außerhalb der bearbeiteten Gesichtsregion separat auf Erhaltung geprüft werden. Das Zielbild muss als neue Eingabekopie über die bestehende Upload-API übernommen werden; das Original im Outputverzeichnis darf nicht überschrieben werden.

Wichtiger Negativbefund: `E:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\input\MORPH-KREA2-synthetic-portrait-20261015.png` ist aktuell byteidentisch mit der roten Phase3-Referenz (SHA-256 wie oben). Diese beiden Kopien ergeben kein unterschiedliches Quell-/Zielpaar.

## Herkunftsbelege

- `E:\MORPH-Studio\reports\Phase3-1-Bericht.md`: dokumentiert synthetisches Erwachsenenporträt, einmalige SDXL-Referenzerzeugung und einmalige Kontext-Farbänderung. Historische Läufe, keine heutige Wiederholung. Pfade im älteren Bericht stammen teils noch von V:; die oben genannten E:-Dateien wurden jetzt tatsächlich gefunden und gelesen.
- `E:\MORPH-Studio\reports\phase3-run-reference.json`: enthält den künstlichen Portraitauftrag („fictional 40-year-old adult man“) und den historischen Generierungsbeleg. Herkunft belegt synthetischen Ursprung; das Alter ist Promptvorgabe und keine visuelle Altersmessung.
- `E:\MORPH-Studio\reports\phase3-reference-visual-gate.json`: dokumentiert damalige Eignung des einzelnen Erwachsenenporträts und dieselbe Referenz-SHA-256.
- `E:\MORPH-Studio\reports\KREA2-Edit-20261015\Ergebnis.md`: bestätigt die Weiterverwendung der synthetischen Phase3-Vorlage und den Verzicht auf private Fotos in jenem KREA-Test.
- `E:\MORPH-Studio\reports\reactor-lmstudio\first-face-swap.json` und `first-face-swap-review.json`: nur als historische technische ReActor-Belege gelesen. Die darin genannten privaten Quell-/Zielbilder wurden weder geöffnet noch für die neue Abnahme ausgewählt; ihre Pfade werden hier nicht übernommen.

## Genau nächster Schritt

Root schließt zuerst die beidseitige GPU-Gate-Prüfung und die vorgesehenen Commits ab. Später den einzelnen ReActor-Regressionslauf mit diesem Paar konkret ankündigen, vorhandene ReActor-Katalogdefaults/Komponenten verwenden, Quell-/Zielzuordnung über neue eigene Uploadquittungen sichern und genau einen eigenen Auftrag über die bestehende MORPH-API einreichen. Keine Installation und kein Fallback mit privaten Bildern. Erfolg, Erkennungsfehler, sichtbare Gesichtsänderung und Erhalt der übrigen Zielszene getrennt als PASS/FAIL/UNVERIFIED protokollieren; bei Fehler kein automatischer neuer Submit.
