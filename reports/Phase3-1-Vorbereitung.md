# Phase 3, Punkt 1: kontrollierter Referenztest vorbereitet

Stand: 8. Oktober 2026. Status: vorbereitet, nicht ausgeführt. Gesamtstand weiterhin 10/40; keine Gesichtserhaltungs-Abnahme.

## Wiederaufnahme

Snapshot 20261008T023331Z-d23e497c geprüft. MORPH-Fortsetzen-Check.cmd erfolgreich (Exit 0). main bleibt auf 4f1a9a2467de1dde4d28f38a2f1249468e152b23; kein Remote eingerichtet, keine gestagten Änderungen. Bestehende Änderungen entsprechen dem Snapshot: README/.gitignore mit Pausenprotokoll-Ergänzungen sowie sechs neue Protokoll-/Nachweisdateien. Die Änderungen wurden gelesen und erhalten. Check meldet keine Datei-/Modellabweichungen; große Modelle nur nach Größe/Zeitstempel, nicht neu gehasht. Frei: 48,63 GiB.

Mein Zugriff sieht den damaligen ComfyUI-Dienst nicht. Direkte Abfrage von 127.0.0.1:8188/queue wurde mit Verbindungsverweigerung beantwortet. Die Warteschlange ist deshalb nicht als leer verifiziert; {} im Fortsetzen-Check ist kein Leer-Nachweis. Kein Dienst gestartet oder gestoppt.

## Vorbereitung

Vier neue Workflows unter workflows: Phase3-1-Erwachsenenportraet-SDXL und Phase3-1-Identitaet-Kontext, jeweils grafisch und als API-JSON. Abgeleitet aus den vorhandenen Phase-2-Workflows; keine neue Laufzeit, Modelle oder Erweiterungen. Feste Seeds 31001/31002; Parameter und Bewertung im phase3-identity-test-plan.json.

Zuerst ein fiktiver 40-jähriger erwachsener Mann als zentriertes Schulterporträt mit rotem Shirt vor grauem Hintergrund. Nach visueller Eignungsprüfung wird die erzeugte PNG verlustfrei nach input/Phase3-Referenz-Erwachsener.png kopiert. Dieser Pfad ist derzeit bewusst noch nicht vorhanden. Der Kontext-Workflow ist vor dieser Eingabe nicht ausführbar.

Ein einziger Kontext-Test soll ausschließlich die Shirtfarbe zu Kobaltblau ändern. Gesicht, Alter, Ausdruck, Haaransatz, Bart, Pose und Umgebung sollen erhalten bleiben. Identität und erfolgreiche Farbänderung werden getrennt beurteilt; technische Erfolgsmeldungen allein reichen nicht. Visuelle Merkmale werden mit erhalten / leicht verändert / deutlich verändert / nicht beurteilbar protokolliert. Keine automatische Wiederholung oder Parametersuche bei einem schlechten Ergebnis.

## Prüfung und Grenzen

Neue JSON-Dateien und Verbindungen statisch prüfen, grafische Parameter mit API-Versionen vergleichen. Kein API-Validierungslauf mit aktiver ComfyUI und keine visuellen Ergebnisse vorhanden. Ein später erfolgreiches Einzelbeispiel wäre ein begrenzter Machbarkeitstest, keine allgemeine Garantie. Phase 3 bleibt offen. PROJECT_STATE.json bleibt die dokumentierte Phase-2-Grundlage; das gespeicherte Pausenpaar bleibt als historischer Snapshot erhalten.

## Nächster Schritt

Den eigenen ComfyUI-Dienst starten, Listenerzuordnung und leere Warteschlange prüfen und das vorbereitete synthetische Erwachsenenporträt einmal erzeugen und visuell prüfen.