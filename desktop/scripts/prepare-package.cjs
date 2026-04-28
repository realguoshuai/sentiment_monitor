const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..', '..');
const frontendDir = path.join(repoRoot, 'frontend');
const desktopDir = path.join(repoRoot, 'desktop');
const frontendDistIndex = path.join(frontendDir, 'dist', 'index.html');
const desktopFrontendDist = path.join(desktopDir, 'frontend-dist');
const desktopFrontendDistIndex = path.join(desktopFrontendDist, 'index.html');
const backendExe = path.join(repoRoot, 'backend', 'dist', 'SentimentMonitor-runtime', 'SentimentMonitor.exe');

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: 'inherit',
    shell: process.platform === 'win32' && /\.(cmd|bat)$/i.test(command),
  });

  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

function ensureFile(filePath, hint) {
  if (!fs.existsSync(filePath)) {
    console.error(`[desktop-package] Missing required file: ${filePath}`);
    console.error(`[desktop-package] ${hint}`);
    process.exit(1);
  }
}

function copyDirectory(sourceDir, targetDir) {
  const resolvedTarget = path.resolve(targetDir);
  const resolvedDesktopDir = path.resolve(desktopDir);

  if (!resolvedTarget.startsWith(resolvedDesktopDir + path.sep)) {
    throw new Error(`Refusing to replace directory outside desktop/: ${targetDir}`);
  }

  fs.rmSync(targetDir, { recursive: true, force: true });
  fs.cpSync(sourceDir, targetDir, { recursive: true });
}

run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build:backend'], desktopDir);
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build'], frontendDir);
ensureFile(frontendDistIndex, 'Frontend build failed or dist output is missing.');
copyDirectory(path.join(frontendDir, 'dist'), desktopFrontendDist);
ensureFile(
  desktopFrontendDistIndex,
  'Failed to copy frontend dist into the desktop package staging directory.',
);
ensureFile(
  backendExe,
  'Backend exe build failed, then rerun desktop packaging.',
);

console.log('[desktop-package] Frontend dist and backend executable are ready.');
