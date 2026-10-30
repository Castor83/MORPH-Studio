'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
const source = 'D:/MORPH-Studio/tools/lmstudio-wan-chat';
const target = 'V:/LMStudio/.lmstudio/extensions/plugins/morph/bilder-und-videos';
const reportPath = 'D:/MORPH-Studio/reports/wan-lmstudio/repair-install.json';
if (fs.existsSync(reportPath)) throw Error('Repair receipt exists; do not overwrite or reinstall automatically.');
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const backup = 'D:/MORPH-Studio/reports/wan-lmstudio/repair-backup-' + stamp;
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const configPath = 'V:/LMStudio/.lmstudio/mcp.json';
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const legacy = config.mcpServers?.['Wan-ComfyUI'];
if (!legacy || legacy.command !== 'D:\\MORPH-Studio\\ComfyUI_windows_portable\\python_embeded\\python.exe' ||
    !legacy.args?.includes('D:\\MORPH-Studio\\tools\\lmstudio-wan-chat\\start_mcp.py')) {
  throw Error('The exact owned legacy MCP entry was not recognized; config left unchanged.');
}
const manifest = JSON.parse(fs.readFileSync(path.join(target, 'manifest.json'), 'utf8'));
if (manifest.owner !== 'morph' || manifest.name !== 'bilder-und-videos' || manifest.runner !== 'node') throw Error('Owned installed plugin expected.');
const report = {at:new Date().toISOString(), mode:'minimal-local-plugin-repair', success:false,
  backup, plugin:'morph/bilder-und-videos', downloadedDependencies:false,
  changedModelSettings:false, stoppedServices:false, files:[]};
try {
  fs.mkdirSync(backup, {recursive:true});
  for (const relative of ['src/mcpTransport.mjs', 'src/toolsProxy.mjs', '.lmstudio/production.js']) {
    const from = path.join(target, relative), dest = path.join(backup, relative);
    fs.mkdirSync(path.dirname(dest), {recursive:true}); fs.copyFileSync(from, dest);
  }
  for (const relative of ['src/mcpTransport.mjs', 'src/toolsProxy.mjs']) {
    fs.copyFileSync(path.join(source, relative), path.join(target, relative));
    report.files.push({relative, sourceHash:sha(path.join(source, relative)), installedHash:sha(path.join(target, relative))});
  }
  const built = spawnSync('V:/LMStudio/.lmstudio/.internal/utils/esbuild.exe', [
    path.join(target, '.lmstudio/entry.ts'), '--platform=node', '--target=node18.16.0', '--sourcemap=inline',
    '--tree-shaking=true', '--bundle', '--packages=external', '--define:process.env.NODE_ENV="production"',
    '--outfile=' + path.join(target, '.lmstudio/production.js')
  ], {cwd:target, encoding:'utf8', windowsHide:true});
  report.build = {exitCode:built.status, stderr:built.stderr, error:built.error?.message};
  if (built.status !== 0) throw Error('Local build failed; legacy MCP configuration left intact.');
  const configBackup = configPath + '.morph-repair-' + stamp + '.bak';
  fs.copyFileSync(configPath, configBackup);
  const otherEntriesBefore = JSON.stringify(Object.fromEntries(Object.entries(config.mcpServers).filter(([key]) => key !== 'Wan-ComfyUI')));
  delete config.mcpServers['Wan-ComfyUI'];
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n');
  const reread = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  report.legacyEntryRemoved = 'Wan-ComfyUI'; report.configBackup = configBackup;
  report.otherMcpEntriesPreserved = JSON.stringify(reread.mcpServers) === otherEntriesBefore;
  report.productionHash = sha(path.join(target, '.lmstudio/production.js'));
  report.wrapper = {path:path.join(source, 'start_mcp.py'), sha256:sha(path.join(source, 'start_mcp.py'))};
  report.success = report.files.every(f => f.sourceHash === f.installedHash) && report.otherMcpEntriesPreserved;
  if (!report.success) throw Error('Install verification failed.');
} catch (error) { report.error = error.message; process.exitCode = 1; }
report.finishedAt = new Date().toISOString();
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
