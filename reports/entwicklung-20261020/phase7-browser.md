# Phase 6/7 – gemeinsame isolierte Browserprüfung

20.10.2026. phase7_browser_fixture.py nutzte Port8767, temporäre Datenbank, winzige synthetische Modellheader und einen ausdrücklich als SIMULATION bezeichneten Sprach-/Rechendienst. Kein echtes Ollama, ComfyUI, Modell oder GPU-Speicher wurde verändert.

- Originalformularprompt auf „SIMULATION ORIGINAL: Rote Tasse auf Holz.“ gesetzt, separaten Auftrag „SIMULATION: Nur die Tasse blau färben.“ eingegeben und einen simulierten Vorschlag angefordert.
- Originalauftrag und Formularbeleg waren getrennt von der Antwort sichtbar. Vergleich enthielt ausschließlich Promptänderung und Seed42→9. Nach expliziter Einzelübernahme änderte sich das Formular; Originalbeleg und Auftrag blieben unverändert. Ergebnis:1Vorschlag,0Bildsubmissions,0Speicherfreigaben.
- Ressourcen zeigten simulierte12/16GiB VRAM, Gerätequelle, Messzeit und unbekannte geladene Modellnamen. Genau ein ausdrücklicher Freigabeklick ergab1Freigabeanforderung, keine Bildsubmission. UI bestätigte ausschließlich „Freigabe angefordert“ und zeigte den neuen simulierten Messwert2/16GiB; kein behaupteter Entladeabschluss.
- Ressourcen-API im Fixture offline geschaltet und ausdrücklich aktualisiert: Werte/Messzeit unbekannt, Freigabe deaktiviert, normaler Bildstart weiterhin aktiviert. Originalbeleg weiter vorhanden, keine Browserwarnungen/-fehler. Belege phase7-browser-before-offline.json und phase7-browser-after-offline.json.
- Screenshots: phase6-original-browser.png und phase7-ressourcen-browser.png. Bild-/Sprachmodellausgaben und Speicherwerte bleiben Simulation, kein Nachweis echter Modellqualität, nativer Windows-Handleprüfung oder realen Entladens.

Testdienst über eigenen Stopendpunkt beendet; Execsession53212 exit0. BrowserTab geschlossen. Keine eigenen Testprozesse verbleiben bekannt. Unabhängige Phase7-Reviews von Backend und Frontend ohne offene P1/P2 nach Korrektur des Listenerwechselbefunds. Logs: Backend15/15,neueGuard4/4,alteGuard34/34,angrenzend46/46,Frontend78/78. Echte Abnahme weiterhin Phase9.
