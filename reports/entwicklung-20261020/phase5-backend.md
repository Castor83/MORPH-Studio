# Phase 5: Backend fuer gemalte Bildbereiche

Stand: 20.10.2026. Ausschliesslich lokale Entwicklung und synthetische CPU-/HTTP-Pruefungen; kein Modell geladen oder berechnet, kein produktiver Dienst gestartet oder neu gestartet, kein Commit.

## Implementierung

`POST /api/jobs` akzeptiert optional `edit_region: {mask_media_id, source_media_id, parent_version_id}`. Bereiche sind auf versionierte Eingaben der bestehenden Werkzeuge `kontext` und `krea2` begrenzt. Quellkennung und Elternversion muessen exakt zum restlichen Auftrag passen; der Quell-SHA256 muss zum unveraenderten Eltern-Snapshot passen.

Die Maske muss ein einzelnes deckendes PNG in L, RGB oder RGBA sein. RGB-Kanaele muessen gleich sein, ein Alphakanal muss voll deckend sein. Schwarz schuetzt, Weiss uebernimmt die generierte Ausgabe; Graustufen mischen. Die Maske muss mindestens einen von Schwarz verschiedenen Pixel enthalten und exakt dieselben Pixelmasse wie die Quelle besitzen. Dateien sind auf 64 MiB / 64 Millionen Pixel begrenzt. EXIF-gedrehte Quellen werden fuer die Bereichsfunktion mit einem Hinweis zur expliziten PNG-Normalisierung abgelehnt; normale Uploads bleiben unveraendert.

Ausgabebreite und -hoehe muessen dasselbe exakte Seitenverhaeltnis wie die Quelle haben (`width * source_height == height * source_width`). Dies vermeidet eine falsche Zuordnung durch KREAs proportional zentriertes Referenzraster. Unpassende Masse werden vor Dienstbereitstellung abgelehnt; der Server veraendert sie nicht stillschweigend.

Die bestehenden Sampler und Referenzknoten bleiben unveraendert. Der Graph erhaelt `LoadImageMask(channel=red)` und `ImageCompositeMasked(destination=urspruengliche LoadImage-Ausgabe, source=bisherige SaveImage-Eingabe, x=0, y=0, resize_source=true, mask=...)`. SaveImage speichert die Komposition in den Pixelmassen der Quelle. Der bestaetigte Uploadname des Rechendienstes wird fuer Bild und Maske eingesetzt.

Das ist eine abschliessende Bereichskomposition. Die Maske steuert die Generierung selbst nicht. Sie ist kein Nachweis fuer natives semantisches Inpainting, Gesichtserhaltung innerhalb des Bereichs oder nahtlose Uebergaenge. Ausserhalb von Nullmaskenwerten nimmt die Komposition die dekodierte Quelle; Identitaet der Originaldatei, Metadaten und eines erneuten Decodierens/Encodierens werden nicht zugesichert.

Quell-/Maskenkennung, Elternversion, SHA256, Pixelmasse und Maskengrenzen werden im Job und in Ergebnisversionsmetadaten eingefroren. Hashpruefungen vor und nach den Uploads erkennen waehrend des Dienstchecks geaenderte Dateien. Die Versions-Metadaten erhalten `edit_region` nur fuer tatsaechliche Bereichsauftraege; bestehende unmaskierte Versionsbelege behalten ihr kanonisches Format.

`ComfyClient.require_region_nodes()` prueft ausschliesslich `/object_info/LoadImageMask` und `/object_info/ImageCompositeMasked`: benoetigte Ein-/Ausgangstypen, Maskenanschluss und Rotkanal. Fehlende oder inkompatible Knoten verhindern Upload und Submission. Das prueft die Faehigkeit beim ausdruecklichen Berechnungsstart, fuehrt aber keinen Knoten aus.

## Belege

- Baseline der fuenf beruehrten vorhandenen Backenddateien samt SHA256: `phase5-backend-baseline/`.
- `phase5-backend-red.log`: neue Tests scheiterten vor der Implementierung an fehlender API/Knotenfaehigkeitspruefung (13 Tests, 18 Fehler einschliesslich Unterfaellen).
- `phase5-backend-green.log`: 13/13 neue Tests bestanden.
- `phase5-backend-route-green.log`: nach Erweiterung der statischen Modulfreigabe realer Test-HTTP-Zugriff auf `comparison.js` und `regions.js` sowie Bereichs-POST bestanden.
- `phase5-source-race-red.log`: eine nach Elternvalidierung geaenderte Quelle wurde zuvor faelschlich eingereicht.
- `phase5-source-race-green.log`: derselbe Fall wird vor Dienstbereitstellung abgelehnt; 1/1 bestanden.
- `phase5-backend-regression.log`: 58/58 angrenzende bestehende Tests bestanden (Katalog/Dateien, Auftraege, Comfy-HTTP, Server, Versionsauftraege/-speicher/-routen).

Neue Tests: `E:\MORPH-Studio\ui\tests\test_edit_region.py` (14 Faelle; der zusaetzliche Quellen-Race-Fall wurde gesondert gruen geprueft). Alle Bilder/Modelldateien sind synthetische Testdaten unter `temp/morph-ui-tests`; Modellfixtures wurden nicht geladen. HTTP-Tests nutzen wegwerfbare Testserver mit gefaelschtem Rechendienst.

## Quellen und gepruefter lokaler Code

- [Offizieller ComfyUI-Kompositor](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_mask.py): Formel `mask*source + (1-mask)*destination` und optionale Quellenanpassung.
- [Offizieller LoadImageMask-Code](https://github.com/Comfy-Org/ComfyUI/blob/master/nodes.py): Rotkanal direkt, Alphamaske mit anderer Polaritaet.
- [KREA-Edit-Projekt](https://github.com/lbouaraba/comfyui-krea2edit): bestehende Referenz-/Textkonditionierung.
- Lokal abgeglichen: `ComfyUI_windows_portable/ComfyUI/comfy_extras/nodes_mask.py`, `nodes.py`, `custom_nodes/comfyui-krea2edit-main/__init__.py`. Dessen optionales `ref_boost_mask` begrenzt Referenz-Aufmerksamkeitsverstaerkung und ersetzt keine Ausgabebereichsmaske. Keine Aenderung dieser Laufzeitdateien.

Browserabnahme, Gesamtpruefung nach weiteren Phasen und unabhaengige Review werden separat durch den Hauptchat dokumentiert. Diese Backendpruefung beweist keine echte Bildmodellqualitaet.

## Abschluss nach unabhängiger Prüfung

Ein weiterer P2 betraf effektives Alpha: Transparente Quellen verlieren im nativen RGB-Kompositionsweg ihre Transparenz; PNG-tRNS konnte die ursprüngliche Maskenprüfung umgehen. Root hat Quelle und Maske einschließlich tRNS auf vollständige Deckkraft geprüft und klare lokale Fehler vor Dienstaktionen ergänzt. Normale unmaskierte Aufträge bleiben zulässig. Drei neue Regressionen wurden zunächst rot nachgewiesen (phase5-alpha-red.log), anschließend vollständige aktuelle Bereichssuite17/17grün (phase5-alpha-green.log,48.349s). Unabhängiger Re-Review bestätigt Fix und keine weiteren konkreten Backendblocker. Browserbeleg steht in phase5-browser.md; keine native GPU-/Modellabnahme hier.
