# Echte maskierte KREA-Abnahme

## Original zu Dunkelblau

Ein Submit, Job `1be85194-c762-4e72-bf71-382fada68b2d`, Request/Prompt `bc74f740-30d9-40bf-b67d-b317a9270a3b`, eigener Comfy-Kaltstart PID107180. 768², acht Schritte, ref_boost1, Seed2026102001. Ergebnisversion `90b2879ff0685b3cb3ad1bc033f164b3`, Parent `8acb1ac88e6252e186b32e1efbbb57d5`; genau eine persistente Ergebnisversion und ein Output, terminale History completed, Exit0.

Frisch aus der API unabhängig exportiert, SHA256 gegen immutable Versionsmetadaten geprüft. Originalexport bytegleich zum ursprünglichen synthetischen Porträt. Endkomposition1024². Außerhalb der Binärmaske **0 geänderte Pixel, maximale Kanalabweichung0**. Innerhalb261822 geänderte Pixel von261825; mittleres RGB20.05/34.83/58.21. Visuell dunkelblaues Hemd, Gesicht/Haare/Hintergrund erhalten. Harte Maskengrenzen zeigen teils feine rote Ränder und Übergangsnähte; deshalb kein pauschales perfektes Qualitätsurteil. Maskierte technische Bearbeitung und Farbziel PASS für diesen Lauf.

52 gespeicherte Jobantworten binden genau denselben Job/Request/Prompt/Client. Echte KSampler-Zwischenstände2,3,4,6,7 von8 und Encoder-/VAE-/Maskenknoten, WSconnected. Periodische Snapshots sind keine vollständige Rohaufzeichnung sämtlicher WS-Pakete und keine lückenlose Spitzenmessung. Abschluss folgt aus History, nicht aus Prozentwert. Unabhängiger Lesecheck bestätigte diese begrenzte Bindung.

Originalbelege: `phase9-live/prepare-20261020T184154588458Z.json`, `phase9-live/edit1-20261020T184218991248Z.json`. Quantitativer Zwischenstand mit Exportpfaden: `phase9-live/project-export-analysis.json`; API-Projektabbild: `phase9-live/project-latest.json`. Letztere werden beim Hinzukommen neuer Versionen fortgeschrieben; der Commit erhält jeweils seinen Zeitpunkt. Export-PNGs bleiben lokal außerhalb des Quellcommits.

## Dunkelblau zu Dunkelgrün

Job `4cff128a-22ea-4ae5-ac96-a74962f3c7b4`, Seed2026102002, Parent90b2879ff0685b3cb3ad1bc033f164b3. Version `0f0e3ff895fb558f93e43e053eb4c9ff`, completed/Exit0. Derselbe Comfy-Prozess107180 ohne Doppelstart; Lauf nach Quittung rund29s. Echte KSampler-Zwischenstände bis7/8 beobachtet.

Unabhängiger Download aller bisher drei Versionen mit attachment-Header und exakt passendem SHA256. Außerhalb der Maske erneut0 geänderte Pixel/Delta0 zum Parent. Innen261815 geänderte Pixel, RGB30.61/46.78/36.98. Visuell dunkelgrün, unveränderte unmaskierte Bereiche; dieselben feinen Rand-/Nahtgrenzen. Farbziel und technische Weiterbearbeitung PASS. Wiederverwendbarer ausschließlich lesender Export-/Pixelhelfer `phase9_project_export_check.py`, keine Modellaktion.

## Violetter Zweig und echte Oberfläche

Job92985aae-5023-4def-8025-f8dd69c47d9d, Seed2026102003, Parent erneut90b2879ff0685b3cb3ad1bc033f164b3. Versiond15c37620d1d5eaab32f5a5e0296e071, completed/Exit0, rund43.6s nach Quittung. Weiterhin Comfy-PID107180. Export bestätigt: außerhalb der Maske0 geänderte Pixel/Delta0; innen261781 geändert, RGB73.33/43.25/108.74. Sichtbar violett.

**Qualitätsgrenze für alle drei:** Das Modell verändert innerhalb der Maske auch Kragenform und Textur. Farbziel PASS; reine Umfärbung bei identischem Schnitt nur PARTIAL. Gesicht/Haare/Hintergrund außerhalb der Maske bleiben exakt. Keine Nachberechnung zur Kaschierung und kein Parameter-/Modellmarathon.

Alle vier unabhängigen Versionen mit korrekten Eltern aus der API exportiert, Attachmentheader und SHA256 geprüft. Nach echtem Browserreload Projekt erneut geöffnet: vier Versionen mit erhaltenen Prompts/Parentbezeichnungen sichtbar. Ein automatisches Wiederöffnen des zuvor gewählten Projekts wurde nicht belegt; bewusste erneute Projektwahl funktioniert.

Reale Browserbedienung: Grün gegen Violett als beliebiges Paar;200% Zoom, Pfeiltastenverschiebung. Beide geladenen1024²-Bilder exakt dieselbe Transformation `translate(-5%,-5%) scale(2)`. Original links, Elternversion links, Ansichten tauschen und Alles zeigen jeweils korrekt; Reset beide `translate(0%,0%) scale(1)`. Kein Bildsubmit durch Vergleich. Beleg `phase9-live/browser-comparison-proof.json`, Screenshot `browser-four-versions.png` (lokal). Ein anfänglicher Locator wartete vor erneuter Projektwahl auf nicht vorhandene Karten; nach Lesen des sichtbaren Projektzustands bewusst geöffnet. Ein Klick auf ein veraltetes dynamisches AX-Ziel hatte keinen Effekt; anschließende sichtbare DOM-Zuordnung funktionierte.

Erneuter NoBrowser-Starter bei bereits aktivem Comfy: Exit0, unverändert UI103344/Comfy107180, kein Doppelstart. Echte UI zeigte gemessenen GPU-Speicher und sperrte nach Auftragsaktualisierung den Start während laufendem Folgeauftrag.

Noch offen: eigener kurzer Cancel und bewusste Speicherfreigabe, danach ReActor-Einzeltest.
