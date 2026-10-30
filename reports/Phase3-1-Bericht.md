# MORPH Studio – Phase 3, Punkt 1

Stand: 8. Oktober 2026. Referenzverfahren eingerichtet und technisch geprüft; Gesichtserhaltung nicht abgenommen. Phase 3 insgesamt offen, Gesamtstand 11/40.

## Ergebnis

Das vorhandene native FLUX.1-Kontext-Verfahren verarbeitet ein synthetisches Erwachsenenporträt als echte Referenz. Die gewünschte Shirtfarbe wechselt von Rot zu Kobaltblau. Der Mann bleibt visuell ähnlich und wiedererkennbar, aber die strenge Gesichtserhaltungsprüfung besteht nicht: Haut, Bart, Haarzeichnung und Bildausschnitt verändern sich deutlich. Technischer Lauf-Erfolg, Farbwechsel und Identitätserhaltung sind getrennte Ergebnisse.

Ein separater Prüfagent hat beide Originalbilder unabhängig angesehen und bestätigt: Farbwechsel bestanden; strenge Gesichtserhaltungs-Abnahme nicht bestanden. Einzelbewertungen stehen in phase3-visual-review.json. Es gibt keine biometrische Identitätsbestätigung oder allgemeine Zuverlässigkeitsaussage.

## Einmalige Läufe

| Lauf | Parameter | ComfyUI-Laufzeit | Auftragskennung |
|---|---|---|---|
| SDXL-Referenz | 1024², Seed 31001, 30 Schritte, CFG 6,5, DPM++ 2M/Karras | 22,13 s | 0276541e-7ac9-45ef-9adb-cbd7ea0d4ad0 |
| Kontext-Farbwechsel | 1024², Seed 31002, 20 Schritte, CFG 1, Guidance 2,5, Euler/simple, denoise 1 | 62,50 s | ab287eb3-ccc4-4f8e-8ace-cf2919cc92ac |

Laufzeiten aus dem eigenen Dienstlog einschließlich Laden; Beobachtung samt API-Abfrage 24,07 s / 64,16 s. Beide PNGs geprüft: 1024×1024, nichtleer, jeweilige Erfolgshistorie und SHA256 dokumentiert. Vollständige Sampling-Schritte im Log. Keine Wiederholung, keine Parametersuche, keine Neuinstallation. Neue Laufsteuerung phase3-run.py sperrt automatische Wiederholung mit bereits vorhandenem Auftragsbeleg; ein unterbrochener Auftrag verlangt Prüfung seines Ausgangs.

Referenz: output/Phase3/Referenz_Erwachsener_00001_.png. Verlustfreie, hashgleiche Eingabe: input/Phase3-Referenz-Erwachsener.png. Ausgabe: output/Phase3/Kontext_Identitaet_Hemdfarbe_00001_.png. Die Referenz ist ein einzelner frontal sichtbarer synthetischer Erwachsener; voller Bart statt kurzer Stoppeln ist eine SDXL-Promptabweichung, aber kein Ausschluss für diesen Vergleich.

## Visuelle Bewertung

| Merkmal | Bewertung |
|---|---|
| Shirtfarbe | Rot zu Kobaltblau bestanden |
| Gesichtsform, Augen/Brauen, Nase, Mund/Kiefer, Ohren | leicht verändert |
| Haaransatz/Frisur, Bart, Haut | deutlich verändert |
| Alterseindruck, Ausdruck | leicht verändert |
| Kopfpose, grauer Hintergrund | erhalten |
| Bildausschnitt | deutlich verändert: kleinerer/höherer Kopf, mehr Oberkörper |
| Licht | leicht verändert: stärkere Kontraste und Glanzpunkte |

Auch Kragenform, Stoffstruktur und Schulterwirkung ändern sich. Die Haut wirkt gröber und geröteter, Falten und Bartkontraste werden verstärkt. Das vorab festgelegte Kriterium verlangt alle sichtbaren Identitätsmerkmale erhalten; leichte Änderungen sind deshalb ebenfalls keine volle Abnahme. Der Referenzfluss über VAEEncode/ReferenceLatent ist eingerichtet, enthält aber keine Maske oder pixelgenaue Gesichtssperre.

phase3-comparison.png zeigt beide vollständigen Bilder gleich groß nebeneinander. phase3-face-comparison.png zeigt denselben Gesichtsausschnitt ohne geometrische Ausrichtung oder Skalierung. Originalbilder bleiben unverändert. Eingaben/Ausgaben sind gemäß bestehender .gitignore-Regel nicht in Git gesichert; die Vergleichsbilder unter reports sind neue synthetische Prüfnachweise.

## Projektstand

Fortsetzen-Check erneut ausgeführt. Die neuen Vorbereitungsdateien erklären die Abweichungen vom alten Snapshot. Eigener Dienst über das vorhandene start-morph.ps1 gestartet: nur 127.0.0.1:8188, offline, alle steuerbaren Projektpfade unter V:\MORPH-Studio. Listener dem MORPH-Python-Prozess zugeordnet. Warteschlange vor und nach beiden Läufen leer. Dienst bleibt erreichbar; Modellcache nach Abschluss freigegeben. Keine Prozesse anderer Projekte angefasst.

PROJECT_STATE.json wird auf Phase 3 in Arbeit mit ausschließlich Punkt 1 abgeschlossen fortgeschrieben. Der historische Phase-2-Commit bleibt erhalten; PAUSE_STATE.md und PAUSE_SNAPSHOT.json bleiben unverändert. Keine neue Pause angeordnet, keine Commits, kein Remote, keine Resets. Phase 3 Punkte 2–5 und allgemeine Gesichtserhaltungs-Abnahme bleiben offen.

## Nächster Schritt

Phase 3, Punkt 2: weitere gezielt unterschiedliche Gesichtserhaltungsfälle zunächst planen; dieses Beispiel nicht automatisch wiederholen.

Nachweise: phase3-run-reference.json, phase3-run-edit.json, phase3-receipt-reference.json, phase3-receipt-edit.json, phase3-reference-visual-gate.json, phase3-visual-review.json sowie logs/phase3-comfyui-stderr.log.