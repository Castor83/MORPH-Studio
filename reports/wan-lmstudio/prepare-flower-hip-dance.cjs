'use strict';
// Prepare a separate one-run script; old submitted jobs and source photo stay untouched.
const fs = require('node:fs');
const folder = 'D:/MORPH-Studio/reports/wan-lmstudio/';
const destination = folder + 'run-flower-hip-dance.cjs';
if (fs.existsSync(destination) || fs.existsSync(folder + 'flower-hip-dance.json')) throw Error('New dance script or receipt already exists; do not overwrite.');
let script = fs.readFileSync(folder + 'run-cat-dance.cjs', 'utf8');
function replaceOnce(before, after) {
  if (script.split(before).length !== 2) throw Error('Expected one known source fragment, found differently: ' + before.slice(0,60));
  script = script.replace(before, after);
}
replaceOnce('cat-dance.json', 'flower-hip-dance.json');
replaceOnce('Dance receipt already exists; do not submit again.', 'Flower hip dance receipt already exists; do not submit again.');
replaceOnce('C:/Users/USER/Desktop/rtzu/589682038_17903637102306091_4752592283070689792_n.jpg', 'C:/Users/USER/Desktop/rtzu/Screenshot 2025-03-03 162438.png');
replaceOnce('Short dance video from woman-and-cat photo with existing clothing preserved', 'Approximately seven seconds of dancing and circling hips from the flower-shop photo, existing clothing preserved');
replaceOnce('Erstelle aus diesem Foto ein kurzes Tanzvideo. Sie wiegt ihren Oberkörper sanft im Rhythmus und hält die Katze sicher. Bewahre ihre vorhandene Kleidung und die ruhige Kamera.', 'Erstelle aus diesem Foto ein etwa sieben Sekunden langes Tanzvideo. Sie tanzt mit sichtbar kreisenden Hüftbewegungen. Erhalte ihre graue Kleidung, die Stiefel, den Blumenladen und den Besen. Die Kamera bleibt ruhig und zeigt sie vollständig.');
replaceOnce("subfolder:'lmstudio/cat-dance'", "subfolder:'lmstudio/flower-hip-dance'");
replaceOnce('The woman gently dances with small rhythmic shoulder and upper-body movements, softly swaying side to side while holding the same gray cat securely. She smiles naturally towards the camera. Preserve her face, hair, exact existing clothing and the original room. The cat remains calm and safely supported, moving naturally with her. Small realistic movements. Calm static camera, stable lighting.', 'Full-body shot of the same woman dancing in the flower shop. She makes clearly visible smooth circular hip movements, moving her hips forward, right, backward and left in repeated natural circles, with small knee bends and gentle weight shifts. One hand holds the broom handle and the other rests on her waist. Preserve her face, long hair, gray long-sleeved turtleneck dress, dark leggings, boots and the flower-shop background. Her clothes remain fully on. Keep her whole body and feet visible. Static camera, stable lighting, continuous natural motion.');
replaceOnce('Frau mit Katze - sanfter Tanz mit vorhandener Kleidung', 'Blumenladen - Hueften kreisen beim Tanz - etwa sieben Sekunden');
replaceOnce(', nudity, removing clothing, torn clothing, unsafe handling of the cat', ', nudity, removing clothing, torn clothing, cropped feet, cropped head, body distortion, sliding feet, frozen body');
for (const part of ['Original','RIFE','Upscale']) replaceOnce('LMStudio/Katze-Tanz-' + part, 'LMStudio/Blumenladen-Huefttanz-' + part);
replaceOnce("'253.source_fps':graph['226'].inputs.frame_rate,", "'131.value':384,'130.value':592,'132.value':113,\n      '226.frame_rate':16,'253.source_fps':16,");
replaceOnce("width:512,height:512,frames:81,steps:8", "width:384,height:592,frames:113,steps:8");
replaceOnce("originalFps:graph['226'].inputs.frame_rate", "originalFps:params.overrides['226.frame_rate']");
replaceOnce('const until=Date.now()+1800000', 'const until=Date.now()+2400000');
replaceOnce("o.filename?.startsWith('Katze-Tanz-')", "o.filename?.startsWith('Blumenladen-Huefttanz-')");
replaceOnce('Expected three new existing dance outputs.', 'Expected three new existing flower-shop dance outputs.');
fs.writeFileSync(destination, script);
console.log(JSON.stringify({prepared:destination,sourcePhoto:'C:/Users/USER/Desktop/rtzu/Screenshot 2025-03-03 162438.png',
  width:384,height:592,frames:113,originalFps:16,expectedOriginalSeconds:113/16,expectedInterpolatedSeconds:Math.floor(113/16*30)/30,
  submitted:false}));
