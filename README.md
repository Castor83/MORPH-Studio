> Aktueller Exportumfang und Grenzen: [EXPORT.md](EXPORT.md). Der folgende Text stammt aus der lokalen Anwendungsdokumentation und enthaelt historische Statusangaben. Der aktuelle Export wird durch PUBLIC-FILES.txt und PUBLIC-SOURCE.json belegt.

# MORPH Studio v1.0

Lokale Windows-Installation unter E:\MORPH-Studio für RTX 4080 16 GB und 48 GB RAM. Phase 1 und Phase 2 sowie Phase 3 Punkt 1 (Referenzverfahren) sind abgeschlossen: 11 von 40 Aufgaben. Die strenge Gesichtserhaltung ist im ersten synthetischen Vergleich nicht bestanden; Nachweis reports/Phase3-1-Bericht.md.

## Bedienung

Wenn ComfyUI bereits läuft: http://127.0.0.1:8188 öffnen. Sonst MORPH-Start.cmd starten und das Fenster geöffnet lassen. MORPH-Stop.cmd beendet den eigenen Hintergrunddienst.

- Phase2-Bedienung.md erklärt die zwei gespeicherten Workflows und ihre Einstellungen.
- reports/Phase1-Bericht.md und reports/Phase2-Bericht.md dokumentieren Einrichtung, echte Tests, Speicherwerte und Grenzen.
- workflows enthält die grafischen Workflows und API-Versionen.

## Eigene MORPH-Oberfläche

`MORPH-Oberflaeche.cmd` öffnet die lokale Browseroberfläche mit sechs Workflows, passender Bildmodell-Auswahl einschließlich Qwen Image 2.1 / Noct Q und KREA 2 GGUF, Bildauswahl, optionaler Ollama-Sprachmodell-Verbindung und Ergebnisverlauf. Ollama läuft üblicherweise unter `http://127.0.0.1:11434`; LM Studio wird für diese Oberfläche nicht benötigt. Modellladen, Vorschläge und Berechnungen sind getrennte Bedienaktionen. Die kurze Anleitung steht in [ui/README.md](ui/README.md). Der Starter verwendet den tatsächlichen Projektpfad und startet ausschließlich die Oberfläche.

## Was Git sichert

Dieses Repository sichert Start-/Testskripte, Workflows, Bedienung, Testnachweise und ausschließlich die benannten synthetischen Tassen-Testbilder. Neue eigene Eingaben und Ausgaben werden standardmäßig ignoriert.

Die ComfyUI-Laufzeit, Python-Pakete, Modelle, Downloads, Cache, Temp-Dateien und Laufzeit-Benutzerdateien bleiben außerhalb von Git. Ein Checkout allein ist deshalb keine vollständige lauffähige Installation. Die offizielle ComfyUI-Version und Paketliste sind in reports dokumentiert; reports/phase2-model-manifest.json enthält Downloadquellen, Versionsstände, Größen und SHA-256-Prüfsummen der Phase-2-Modelle.

Alles arbeitet lokal; der Start beschränkt ComfyUI auf 127.0.0.1 und aktiviert den Offline-Modus. Forge und andere Projekte werden von den Skripten nicht eingerichtet oder verändert.

## Modellgrenzen

SDXL Base erzeugt neue Bilder, FLUX.1 Kontext Dev FP8 bearbeitet vorhandene Bilder mit englischen Anweisungen. Kontext kann zusätzlich Reflexionen, Bilddetails und Positionen verändern; pixelgenaue Erhaltung ist nicht garantiert.

Kontext Dev unterliegt der FLUX.1 dev Non-Commercial License. Für kommerziellen Modellbetrieb ist eine passende Lizenz oder ein anderer Editor erforderlich. Quellen und weitere Nutzungsbedingungen stehen im Phase-2-Bericht. Die Modelldateien werden in diesem Git-Repository nicht verteilt.

## Pause und Fortsetzung

Das Pausenprotokoll in PAUSENPROTOKOLL.md wird durch die ausdrückliche Anweisung „pause“ ausgelöst. Bei „weiter“ oder „fortsetzen“ wird der gespeicherte Stand kurz geprüft und am dokumentierten nächsten Schritt weitergearbeitet. MORPH-Fortsetzen-Check.cmd führt diesen Check ausschließlich lesend aus. PROJECT_STATE.json enthält den dokumentierten Projektfortschritt auf Grundlage von Phase 2; er ist keine aktive Pause.

AGENTS.md hält den Ablauf für künftige Arbeit fest. PAUSE_STATE.md, PAUSE_SNAPSHOT.json und pause-history werden erst bei einer angeordneten Pause angelegt und bleiben außerhalb von Git.
