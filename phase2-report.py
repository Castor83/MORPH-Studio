import json, shutil, subprocess, urllib.request
from pathlib import Path
ROOT=Path(r'E:\MORPH-Studio')
PYTHON=ROOT/'ComfyUI_windows_portable'/'python_embeded'/'python.exe'
models=json.loads((ROOT/'reports'/'phase2-model-manifest.json').read_text(encoding='utf-8-sig'))
for model in models:
    file=Path(model['destination'])
    assert file.stat().st_size==model['bytes'],file
    model['verified']=True
tests={name:json.loads((ROOT/'reports'/('phase2-test-'+name+'.json')).read_text()) for name in ['sdxl','kontext','variation']}
visual=json.loads((ROOT/'reports'/'phase2-visual-review.json').read_text(encoding='utf-8-sig'))
assert all(t['technical_passed'] for t in tests.values())
assert visual['sdxl_photographic'] and visual['blue_edit_passed'] and visual['green_edit_passed'],visual
check=subprocess.run([str(PYTHON),'-s','-m','pip','check'],capture_output=True,text=True)
(ROOT/'reports'/'phase2-dependency-check.txt').write_text(check.stdout+check.stderr,encoding='utf-8')
assert check.returncode==0,check.stdout+check.stderr
with urllib.request.urlopen('http://127.0.0.1:8188/system_stats') as response: stats=json.load(response)
assert '--offline' in stats['system']['argv']
(ROOT/'reports'/'phase2-system-stats.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
sizes={d.name:sum(f.stat().st_size for f in d.rglob('*') if f.is_file()) for d in ROOT.iterdir() if d.is_dir()}
total=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
free=shutil.disk_usage(ROOT).free
storage=dict(project_bytes=total,free_bytes=free,phase2_models_bytes=sum(m['bytes'] for m in models),folders=sizes)
(ROOT/'reports'/'phase2-storage.json').write_text(json.dumps(storage,indent=2),encoding='utf-8')
gib=lambda number:f'{number/1024**3:.2f}'.replace('.',',')
def duration(test):
    messages=test['status']['messages']
    start=next(v[1]['timestamp'] for v in messages if v[0]=='execution_start')
    end=next(v[1]['timestamp'] for v in messages if v[0]=='execution_success')
    return (end-start)/1000
report=r'''# MORPH Studio v1.0 – Phase 2

Stand: 8. Oktober 2026. Phase 2: 5/5 abgeschlossen; Gesamtplan: 10/40.

| Punkt | Ergebnis und Nachweis |
|---|---|
| 1. Fotorealistisches Bildmodell | SDXL Base 1.0 vom Hersteller Stability AI installiert, ohne optionalen Refiner. Neuer 1024×1024-Fototest mit 30 Schritten, CFG 6,5, DPM++ 2M/Karras, Seed 42 bestanden und visuell beurteilt. |
| 2. Speicheroptimierter Editor | FLUX.1 Kontext Dev FP8 scaled mit FP8-T5, CLIP-L und VAE installiert. Native ComfyUI-Nodes; keine zusätzlichen Erweiterungen oder globalen Paket-/Treiberänderungen. Dynamic VRAM übernimmt Laden und Auslagern bei Bedarf. |
| 3. Vorhandene Bilder als Eingabe | Das bereits erzeugte Phase-1-Bild wurde nach input/Phase2-Eingabe-rote-Tasse.png kopiert und mit LoadImage als echte Referenz für beide Editiertests geladen. |
| 4. Textbasierte Änderungen | Anweisung Rot→Blau bei 1024² und Rot→Grün bei 768² durchgeführt. Technischer Lauf-Erfolg und visuelle Prüfung separat dokumentiert. |
| 5. Einstellungen | Zwei in ComfyUI gespeicherte Workflows mit editierbaren Prompts, Breite/Höhe, Seed, Schrittzahl, Sampler, Scheduler und Guidance. 1024²/20 Schritte/Seed 42 sowie 768²/24 Schritte/Seed 84 für Kontext praktisch geprüft. |

## Modelle und Speicher

'''
report+=f'Zusätzliche Modellgewichte für Phase 2: {gib(storage["phase2_models_bytes"])} GiB. Gesamter MORPH-Ordner: {gib(total)} GiB. Auf E: frei: {gib(free)} GiB. Dateien und Größe direkt gemessen; laufwerksweite Änderungen sind kein zuverlässiges Maß der Installation.\n\n'
report+='| Datei | GiB | Herausgeber-Prüfsumme |\n|---|---:|---|\n'
for model in models:
    report+=f'| {Path(model["destination"]).name} | {gib(model["bytes"])} | SHA-256 geprüft |\n'
report+=r'''
Alle Dateien wurden aus den offiziellen bzw. von der offiziellen ComfyUI-Anleitung verlinkten Repositories heruntergeladen, auf einen konkreten Repository-Stand gebunden und vor Einordnung anhand Größe und SHA-256 geprüft. URLs, Versionen, Sollgrößen und Hashes: reports/phase2-model-manifest.json. Keine doppelten Modellkopien. Die Installation und steuerbaren Temp-/Cache-Dateien bleiben unter E:\MORPH-Studio; Forge wurde nicht verändert.

## Echte Testläufe

| Test | Ausgabe | ComfyUI-Laufzeit | GPU max. gemessen | ComfyUI-RAM max. gemessen |
|---|---|---:|---:|---:|
'''
for key,label in [('sdxl','Neues SDXL-Fotobild'),('kontext','Kontext: Rot → Blau'),('variation','Kontext: Rot → Grün, andere Einstellungen')]:
    t=tests[key]
    image=t['images'][0]
    report+=f'| {label} | {image["size"][0]} × {image["size"][1]} | {duration(t):.2f} s | {t["peak_gpu_used_mib"]/1024:.2f} GiB | {gib(t["peak_server_rss_bytes"])} GiB |\n'
report+=r'''
GPU-Werte betreffen das gesamte Gerät einschließlich Desktop und anderer laufender Programme; etwa im Sekundentakt gemessen, damit kein garantierter absoluter Spitzenwert. RAM-Werte sind der Windows-Arbeitssatz des ComfyUI-Prozesses, nicht die gesamte reservierte Speichermenge. Der erste Lauf eines Modells umfasst Laden/Initialisierung. CPU- und GPU-Speicher blieben im beobachteten Bereich; kein Out-of-Memory-Fehler.

JSON-Tests prüfen Erfolgsmeldung, vorhandene PNG-Datei, tatsächliche Auflösung und nichtleeren Bildinhalt. Sie beweisen allein keine semantisch richtige Bearbeitung. Die gespeicherten Farbanteile sind Messwerte ohne pauschale Qualitätsaussage. Visuelle Abnahme separat: phase2-visual-review.json. Beide gespeicherten Workflows wurden zusätzlich über die Browseroberfläche geladen und ausgeführt; diese identischen Wiederholungen nutzten bereits berechnete Ergebnisse. Der separate Variationslauf hat neue Sampling-Schritte tatsächlich ausgeführt.

'''
report+='Visuelle Ergebnisse: '+visual['summary']+'\n\n'
report+=r'''## Bedienung

Oberfläche http://127.0.0.1:8188. Unter Workflows gegebenenfalls Refresh wählen:

- Phase2-1-Fotobild-SDXL: neue Bilder aus Text. Breite/Höhe im Ausgabegröße-Node, Seed/Schritte/Sampling im KSampler.
- Phase2-2-Bildbearbeitung-Kontext: eigenes Bild im Eingabebild-Node laden, englische Änderung im Text-Node eingeben. Ausgabegröße 1024×1024 als Standard. Anweisungsstärke im FluxGuidance-Node, Seed/Schritte/Sampling im KSampler. CFG 1,0 und denoise 1,0 für diesen getesteten Workflow belassen.

Als Ausgabeformat ist verlustfreies PNG eingerichtet. Qualitätssteuerung erfolgt durch Auflösung, Schrittzahl und Sampling, ohne irreführenden pauschalen Qualitätsregler. Eine höhere Schrittzahl bedeutet mehr Rechenzeit, aber keine garantierte bessere Bearbeitung. Empfehlungen und konkrete Beispiele stehen in Phase2-Bedienung.md im Projektordner.

Eigene Bilder werden lokal gelesen; keine Uploads zu Cloud-Diensten. Der aktuelle Eingabepfad und alle Ausgaben liegen unter input bzw. output/Phase2. Die Workflows liegen zusätzlich unter workflows und user/default/workflows. Ein gegebenenfalls bereits geöffnetes Browserfenster muss nach neuen Modellen neu geladen werden, damit seine Modellauswahl aktualisiert ist.

## Grenzen und offene Probleme

Keine blockierenden Probleme für Phase 2. Gesichtserhaltung, genaue Masken/Inpainting, Video und die vereinfachte MORPH-Bedienoberfläche sind noch nicht abgenommen und gehören zu späteren Phasen. Die geprüften Beispielbilder belegen keine zuverlässige Bearbeitung beliebiger Personen, Hintergründe oder komplexer Anweisungen. Kontext kann nicht angeforderte Details verändern; pixelgenaue Erhaltung ist nicht garantiert. Englisch ist für diesen Kontext-Workflow die dokumentierte Sprache.

SDXL Base verwendet CreativeML Open RAIL++-M. FLUX.1 Kontext Dev verwendet die FLUX.1 dev Non-Commercial License v1.1.1: Modellbetrieb hier für private nichtkommerzielle Tests/Hobbyzwecke; für kommerziellen Betrieb separate Lizenz prüfen oder einen anders lizenzierten Editor wählen. Die Lizenz verlangt vor Weitergabe/Anzeige eine Prüfung auf rechtswidrige oder rechtsverletzende Inhalte bzw. geeignete Filter; die lokalen Tassen-Testbilder wurden visuell geprüft. Die grundsätzliche Nutzungserlaubnis für Outputs hebt die Betriebsbeschränkung nicht auf. Qwen Image Edit unter Apache 2.0 ist eine spätere Alternative, benötigt in der offiziellen FP8-Fassung aber deutlich mehr Modell-/Encoderspeicher.

Offline-Modus und nur 127.0.0.1 bleiben aktiv. Die Modelle wurden lokal ohne Cloud-Konto oder Cloud-Rechenleistung ausgeführt. Nach den Tests wurde der GPU-Modellcache im eigenen ComfyUI-Dienst freigegeben; die Oberfläche bleibt erreichbar. Der nächste Lauf kann deshalb erneut Ladezeit benötigen. Ein Test mit physisch getrenntem Internet ist weiterhin nicht durchgeführt. Windows-eigene Logs/Browser-/Auslagerungsdateien wurden nicht umgestellt.

## Quellen und Nachweise

- SDXL-Modellkarte: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
- Kontext-Modellpaket: https://huggingface.co/Comfy-Org/flux1-kontext-dev_ComfyUI
- Offizieller nativer Workflow: https://docs.comfy.org/tutorials/flux/flux-1-kontext-dev
- Kontext-Lizenz: https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev/blob/main/LICENSE.md
- SDXL-Lizenz: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md
- reports/phase2-test-sdxl.json, phase2-test-kontext.json, phase2-test-variation.json: Workflow, Parameter, Historie, Messungen und Bildprüfsummen.
- reports/phase2-model-manifest.json, phase2-storage.json, phase2-system-stats.json, phase2-dependency-check.txt, phase2-visual-review.json.
- logs/comfyui-stderr.log: Modellladen, CUDA und vollständige Sampling-Läufe.

Nächster Schritt: Phase 3 – Referenzverfahren und Gesichtserhaltung an kontrollierten Vorher-Nachher-Beispielen prüfen.
'''
(ROOT/'reports'/'Phase2-Bericht.md').write_text(report,encoding='utf-8')
print(json.dumps(storage,indent=2))
