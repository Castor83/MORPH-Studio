# Abschlussprüfung des GPU-Koordinationsblocks

Stand 20.10.2026. **PASS im belegten Quell-/Fixtureumfang; reale Modell-/Bildabnahme weiterhin UNVERIFIED.**

Die Backend- und UI-Implementierung stammen von getrennten Agenten. Ihre
unabhängigen Gegenreviews fanden zusätzliche konkrete Fehler. Root hat die
letzten Korrekturen selbst gegen die vorliegenden roten/grünen Fälle und den
aktuellen Quellstand geprüft, nachdem die Agenten vom Dienst wegen Nutzungslimit
beendet wurden. Die älteren Agentenreviewdateien bleiben als historische
Dateistände erhalten; deren offene Befunde werden durch diesen Zusatz eingeordnet.

- Der API-Abwesenheitsbeleg nach bewusstem Unload verwirft defekte oder
  widersprüchliche Modellnamen nicht mehr still. Ungültiges api/ps lässt die
  dauerhafte Unknown-Sperre bestehen. Eine tatsächlich gültige leere Liste
  bleibt zulässig. Enger Nachtrag: 41/41 Fälle in
  `phase9-gate-backend-invalid-ps-green.log`, nach dokumentiertem RED.
- Alte Statusantworten und Fehler können neuere Sprachzustände nicht ersetzen.
  Die UI pollt beobachtetes Remote-Busy/Unknown weiter und erneuert beim
  bestätigten Freiwerden die Modellliste ausschließlich lesend. Bestätigte
  eigene Modellmutationen aktualisieren ihre Instanzliste trotz alter
  Busy-Anzeige. Finaler fokussierter UI-Beleg: 84/84 PASS.
- Gegenseitige nicht wartende Sprach-/Bildsperren, idempotente Bildquittungen,
  exakte manuelle Unknown-Freigabe, Endpunktbindung und Settings-Sperren wurden
  gegen Implementierung und vorhandene Regressionen abgeglichen. Kein
  automatischer Unload, Cloud-Fallback, Modellwechsel oder globaler Interrupt.

## Einmalige gesamte Regression

Alle drei Prozesse endeten mit Exit 0. Keine echte GPU-/Modellaktion.

| Prüfung | Ergebnis | Beleg |
|---|---|---|
| Backend, unittest discovery unter ui/tests | 285/285 PASS, 276.196 s | phase9-final-backend.log |
| Frontend, Node alle ui/tests/*.test.mjs | 107/107 PASS, 265.2108 ms | phase9-final-frontend.log |
| Starter, unittest discovery tools/lmstudio-wan-chat/tests | 38/38 PASS, 1.370 s | phase9-final-starter.log |

Root hat die zehn finalen geänderten Quell-/Testdateien gegen
`phase9-gate-backend-final-hashes.json` und `phase9-gate-ui-final-hashes.json`
abgeglichen; sie sind unverändert. `git diff --check` wird vor selektivem Commit
auf genau diese Dateien angewandt. Es wurde keine bereits abgeschlossene
Modellprüfung wiederholt. Die gesamte Regression ist nach diesen unveränderten
Quellen kein weiteres Mal nur für den Chatwechsel auszuführen.

## Grenzen und nächster Schritt

Direkte fremde Ollama-/Comfy-Clients und manuelle externe Dateiänderungen liegen
außerhalb des MORPH-Prozesslocks. Residenzmessungen sind keine allgemeine
Speicher- oder Qualitätsgarantie. Das bestehende Datenbankbackup vor Livebetrieb
ist vorhanden; die produktive VersionStore-Migration wurde noch nicht gestartet.

Der separate ReActor-Einzelaktionshelfer liegt offline mit acht grünen Fällen
vor, war beim Agentenabbruch aber noch nicht vollständig als Abschlussblock
gesichert. Root hat seinen Transport-/Quittungs-/Ausgabepfad gelesen. Vor
Verwendung Stand und Belegbindung kurz finalisieren und separat committen.
Danach den vorhandenen NoBrowser-Start und die ausdrücklich angekündigte
einzelne reale Abnahme gemäß dem vollständigen Übergabeplan ausführen.
