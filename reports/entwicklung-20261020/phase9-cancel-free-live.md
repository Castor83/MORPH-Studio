# Eigener Abbruch und bewusste Freigabe

## Abbruch

Ein zusätzlicher KREA-Auftrag mit acht Schritten, Seed2026102004, vom blauen Parent bewusst gestartet. Job `ddd0892a-792a-4407-b217-4ec6879c92dd` nach genau einem Submit anhand seiner bestätigten Kennung gezielt über `/api/jobs/{id}/cancel` abgebrochen. Terminale History `cancelled`, `cancel_test_result=PASS`, Exit0. Kein globaler Interrupt, kein fremder Auftrag, kein automatischer Retry. Bestehende Versionen werden im finalen DB-/Projektabgleich erneut nur gelesen. Ein spezifischer Abbruch mitten in einem Samplingschritt wird hieraus nicht abgeleitet.

Originalbeleg `phase9-live/cancel-20261020T185249166430Z.json`.

## Freigabe

Separat angekündigt und genau einmal ausgeführt. Serverseitige Freigabe allowed=true, eigene verwaltete Comfy-Instanz, keine ungelösten Jobs/leere Queue. Antwort `accepted=true, completed=false` korrekt als asynchron erhalten. Spätere echte Ressourcenlesung um18:53:45UTC:1.446.641.664Bytes GPU-Speicher genutzt,15.724.314.624Bytes frei von17.170.956.288Bytes. Dies belegt den nachfolgenden Speicherwert, keine allgemeine Aussage, dass sämtliche Prozess-/Modellressourcen vollständig verschwunden wären (`model_state=unknown`). Comfy wurde nicht beendet.

Beleg `phase9-live/free-20261020T185333530191Z.json`, ACTION_RETURNED/Exit0. Nächster Schritt: einmaliger technischer ReActor-Regressionslauf mit dem belegten synthetischen Paar, keine weiteren Installationen oder Modellvergleiche.
