const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..', '..');
const backendDir = path.join(repoRoot, 'backend');
const specFile = path.join(backendDir, 'desktop_backend.spec');
const backendExe = path.join(backendDir, 'dist', 'SentimentMonitor-runtime', 'SentimentMonitor.exe');

function resolvePyInstaller() {
  const custom = process.env.SM_PYINSTALLER;
  if (custom) {
    return custom;
  }

  const windowsPyInstaller = path.join(backendDir, 'venv', 'Scripts', 'pyinstaller.exe');
  if (fs.existsSync(windowsPyInstaller)) {
    return windowsPyInstaller;
  }

  const unixPyInstaller = path.join(backendDir, 'venv', 'bin', 'pyinstaller');
  if (fs.existsSync(unixPyInstaller)) {
    return unixPyInstaller;
  }

  throw new Error('PyInstaller is missing. Install it into backend/venv first.');
}

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

function main() {
  const pyInstaller = resolvePyInstaller();
  run(pyInstaller, ['--noconfirm', specFile], backendDir);

  if (!fs.existsSync(backendExe)) {
    console.error(`[desktop-package] Missing built backend exe: ${backendExe}`);
    process.exit(1);
  }

  console.log(`[desktop-package] Backend exe is ready: ${backendExe}`);
}

main();
