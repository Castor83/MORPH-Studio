'use strict';
const fs = require('node:fs');
const folder = 'D:/MORPH-Studio/reports/wan-lmstudio/';
const destination = folder+'check-flower-hip-dance.cjs';
if(fs.existsSync(destination))throw Error('Review script already exists; do not overwrite.');
let script=fs.readFileSync(folder+'check-cat-dance.cjs','utf8');
function replaceOnce(before,after){if(script.split(before).length!==2)throw Error('Unexpected review source fragment: '+before.slice(0,60));script=script.replace(before,after);}
replaceOnce('cat-dance.json','flower-hip-dance.json');
replaceOnce('Completed new dance job required; no render or retry performed.','Completed new flower-shop hip dance job required; no render or retry performed.');
replaceOnce("startsWith('Katze-Tanz-')","startsWith('Blumenladen-Huefttanz-')");
replaceOnce('cat-dance-contact-sheet.png','flower-hip-dance-contact-sheet.png');
replaceOnce('const selected = [0,11,23,34,46,57,69,80]','const selected = [0,10,20,30,40,50,60,70,80,90,100,112]');
replaceOnce('scale=384:384,tile=4x2','scale=256:-1,tile=4x3');
replaceOnce('timesSeconds:selected.map(n=>n/23)','timesSeconds:selected.map(n=>n/16)');
replaceOnce('cat-dance-media-check.json','flower-hip-dance-media-check.json');
fs.writeFileSync(destination,script);
console.log(JSON.stringify({prepared:destination,submitted:false}));
