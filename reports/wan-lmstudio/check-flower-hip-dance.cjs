'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
const folder = 'D:/MORPH-Studio/reports/wan-lmstudio';
const receipt = JSON.parse(fs.readFileSync(path.join(folder,'flower-hip-dance.json'),'utf8'));
if (!receipt.success || receipt.status !== 'completed' || receipt.outputs?.output_count !== 3) throw Error('Completed new flower-shop hip dance job required; no render or retry performed.');
const binaries = 'C:/Users/USER/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.1-full_build/bin';
const ffmpeg = path.join(binaries,'ffmpeg.exe'), ffprobe = path.join(binaries,'ffprobe.exe');
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const report = {at:new Date().toISOString(), prompt_id:receipt.prompt_id, files:[], success:false, visualReviewPending:true};
for (const output of receipt.outputs.outputs) {
  const file = path.resolve(output.path), allowed = path.resolve('D:/MORPH-Studio/output/LMStudio') + path.sep;
  if (!file.toLowerCase().startsWith(allowed.toLowerCase()) || !output.filename.startsWith('Blumenladen-Huefttanz-')) throw Error('Unexpected output path; source files untouched.');
  const probe = spawnSync(ffprobe,['-v','error','-show_streams','-show_format','-of','json',file],{encoding:'utf8',windowsHide:true});
  if (probe.status !== 0) throw Error('Video probe failed: ' + probe.stderr);
  const metadata = JSON.parse(probe.stdout), video = metadata.streams.find(s=>s.codec_type==='video');
  if (!video || video.codec_name !== 'h264') throw Error('Expected H264 video stream.');
  const decode = spawnSync(ffmpeg,['-hide_banner','-v','error','-i',file,'-f','null','NUL'],{encoding:'utf8',windowsHide:true});
  const checked = {path:file,sha256:sha(file),bytes:fs.statSync(file).size,
    codec:video.codec_name,width:video.width,height:video.height,frames:Number(video.nb_frames),
    fps:video.avg_frame_rate,duration:Number(metadata.format.duration),
    audioStreams:metadata.streams.filter(s=>s.codec_type==='audio').length,
    fullDecodeExitCode:decode.status,fullDecodeErrors:decode.stderr};
  report.files.push(checked);
  if (decode.status !== 0 || decode.stderr.trim()) throw Error('Full video decode reported errors.');
}
const original = receipt.outputs.outputs.find(o=>o.node_id==='226');
const preview = path.join(folder,'flower-hip-dance-contact-sheet.png');
if (fs.existsSync(preview)) throw Error('Review preview already exists; do not overwrite.');
const selected = [0,10,20,30,40,50,60,70,80,90,100,112];
const selector = selected.map(n=>'eq(n\\,'+n+')').join('+');
const extract = spawnSync(ffmpeg,['-hide_banner','-v','error','-i',original.path,
  '-vf','select='+selector+',scale=256:-1,tile=4x3','-frames:v','1','-update','1',preview],{encoding:'utf8',windowsHide:true});
if (extract.status !== 0 || !fs.existsSync(preview)) throw Error('Frame preview failed: '+extract.stderr);
report.contactSheet={path:preview,source:original.path,frames:selected,timesSeconds:selected.map(n=>n/16)};
report.sourceUnchanged=receipt.attachment.originalHash===receipt.attachment.originalHashAfter&&sha(receipt.source)===receipt.attachment.originalHash;
report.success=report.sourceUnchanged&&report.files.length===3;
report.finishedAt=new Date().toISOString();
fs.writeFileSync(path.join(folder,'flower-hip-dance-media-check.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
if(!report.success)process.exitCode=1;
