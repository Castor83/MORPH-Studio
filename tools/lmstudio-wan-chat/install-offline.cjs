'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');

const source = 'E:/MORPH-Studio/tools/lmstudio-wan-chat';
const target = 'V:/LMStudio/.lmstudio/extensions/plugins/morph/bilder-und-videos';
const bundled = 'V:/LMStudio/.lmstudio/extensions/plugins/lmstudio/rag-v1';
const esbuild = 'V:/LMStudio/.lmstudio/.internal/utils/esbuild.exe';
const reportPath = 'E:/MORPH-Studio/reports/wan-lmstudio/native-offline-install.json';
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const report = {
  at: new Date().toISOString(), source, target,
  mode: 'manual-local-completion-after-host-npm-certificate-failure',
  downloadedDependencies: false, tlsSettingsChanged: false, files: [],
};
try {
  const manifest = JSON.parse(fs.readFileSync(path.join(source, 'manifest.json'), 'utf8'));
  if (manifest.owner !== 'morph' || manifest.name !== 'bilder-und-videos' || manifest.runner !== 'node') {
    throw new Error('Expected own native Node plugin only.');
  }
  fs.mkdirSync(target, {recursive: true});
  for (const name of ['manifest.json', 'package.json', '.lmsignore', 'src']) {
    fs.cpSync(path.join(source, name), path.join(target, name), {recursive: true});
  }
  fs.cpSync(path.join(source, 'node_modules'), path.join(target, 'node_modules'), {recursive: true});
  const boot = path.join(target, '.lmstudio');
  fs.mkdirSync(boot, {recursive: true});
  const bootstrapSource = path.join(bundled, '.lmstudio/entry.ts');
  const entry = path.join(boot, 'entry.ts');
  fs.copyFileSync(bootstrapSource, entry);
  report.bootstrap = {source: bootstrapSource, sha256: hash(entry), unchanged: hash(entry) === hash(bootstrapSource)};
  const result = spawnSync(esbuild, [entry, '--platform=node', '--target=node18.16.0', '--sourcemap=inline',
    '--tree-shaking=true', '--bundle', '--packages=external', '--define:process.env.NODE_ENV="production"',
    '--outfile=' + path.join(boot, 'production.js')], {cwd: target, encoding: 'utf8', windowsHide: true});
  report.build = {exitCode: result.status, stderr: result.stderr, error: result.error?.message};
  if (result.status !== 0) throw new Error('Local plugin build failed: ' + result.stderr);
  const receipt = {
    by: 'node-plugin-installer-v1', at: Date.now(), completedBy: 'morph-offline-installer-v1',
    completionMode: 'cached-dependencies-and-local-build',
    hostNpmInstallerSucceeded: false,
  };
  fs.writeFileSync(path.join(target, 'install-state.json'), JSON.stringify(receipt, null, 2) + '\n');
  for (const name of ['manifest.json', 'package.json', 'src/index.ts', 'src/promptPreprocessor.mjs', 'src/toolsProxy.mjs', 'src/mcpTransport.mjs']) {
    report.files.push({name, sourceHash: hash(path.join(source, name)), installedHash: hash(path.join(target, name))});
  }
  report.sourceMatchesInstalled = report.files.every(file => file.sourceHash === file.installedHash);
  report.installedSdkVersion = JSON.parse(fs.readFileSync(path.join(target, 'node_modules/@lmstudio/sdk/package.json'), 'utf8')).version;
  report.production = {path: path.join(boot, 'production.js'), sha256: hash(path.join(boot, 'production.js'))};
  report.receiptReadBack = JSON.parse(fs.readFileSync(path.join(target, 'install-state.json'), 'utf8'));
  report.success = report.sourceMatchesInstalled && report.bootstrap.unchanged;
} catch (error) {
  report.success = false; report.error = error.message; process.exitCode = 1;
}
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
