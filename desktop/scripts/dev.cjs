const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const path = require('path');

const repoRoot = path.resolve(__dirname, '..', '..');
const backendDir = path.join(repoRoot, 'backend');
const frontendDir = path.join(repoRoot, 'frontend');
const desktopDir = path.join(repoRoot, 'desktop');
const frontendUrl = 'http://127.0.0.1:5173';
const backendHealthUrl = 'http://127.0.0.1:8000/api/stocks/';

let backendProcess = null;
let frontendProcess = null;
let electronProcess = null;
let shuttingDown = false;

function spawnCommand(command, args, options) {
  const shouldUseShell = process.platform === 'win32' && /\.(cmd|bat)$/i.test(command);
  return spawn(command, args, {
    ...options,
    shell: shouldUseShell,
  });
}

function resolvePythonCommand() {
  const customPython = process.env.SM_BACKEND_PYTHON;
  if (customPython) {
    return { command: customPython, prefixArgs: [] };
  }

  const windowsVenvPython = path.join(backendDir, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(windowsVenvPython)) {
    return { command: windowsVenvPython, prefixArgs: [] };
  }

  const unixVenvPython = path.join(backendDir, 'venv', 'bin', 'python');
  if (fs.existsSync(unixVenvPython)) {
    return { command: unixVenvPython, prefixArgs: [] };
  }

  if (process.platform === 'win32') {
    return { command: 'py', prefixArgs: ['-3'] };
  }

  return { command: 'python3', prefixArgs: [] };
}

function waitForUrl(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;

  return new Promise((resolve, reject) => {
    const attempt = () => {
      const request = http.get(url, (response) => {
        response.resume();
        resolve();
      });

      request.on('error', () => {
        if (Date.now() >= deadline) {
          reject(new Error(`Timed out waiting for ${url}`));
          return;
        }
        setTimeout(attempt, 500);
      });

      request.setTimeout(2000, () => {
        request.destroy(new Error(`Timeout waiting for ${url}`));
      });
    };

    attempt();
  });
}

function killProcessTree(child) {
  if (!child || child.exitCode !== null) {
    return;
  }

  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], {
      stdio: 'ignore',
      windowsHide: true,
    });
    return;
  }

  try {
    process.kill(-child.pid, 'SIGTERM');
  } catch (error) {
    // Ignore cleanup failures on exit.
  }
}

function resolveElectronBinary() {
  if (process.platform === 'win32') {
    const windowsBinary = path.join(desktopDir, 'node_modules', 'electron', 'dist', 'electron.exe');
    if (fs.existsSync(windowsBinary)) {
      return windowsBinary;
    }
  }

  const binaryName = process.platform === 'win32' ? 'electron.cmd' : 'electron';
  const localBin = path.join(desktopDir, 'node_modules', '.bin', binaryName);
  if (fs.existsSync(localBin)) {
    return localBin;
  }

  throw new Error('Electron dependency is missing. Run "npm install" inside desktop/.');
}

async function start() {
  const { command, prefixArgs } = resolvePythonCommand();
  backendProcess = spawn(
    command,
    [
      ...prefixArgs,
      '-m',
      'uvicorn',
      'sentiment_monitor.asgi:application',
      '--host',
      '127.0.0.1',
      '--port',
      '8000',
    ],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        ENABLE_STARTUP_WARM: '1',
        SENTIMENT_MONITOR_DESKTOP: '1',
      },
      stdio: 'inherit',
      windowsHide: false,
    },
  );

  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  frontendProcess = spawnCommand(
    npmCommand,
    ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
    {
      cwd: frontendDir,
      env: process.env,
      stdio: 'inherit',
      windowsHide: false,
    },
  );

  await Promise.all([
    waitForUrl(backendHealthUrl, 60000),
    waitForUrl(frontendUrl, 60000),
  ]);

  const electronBinary = resolveElectronBinary();
  electronProcess = spawnCommand(electronBinary, ['.'], {
    cwd: desktopDir,
    env: {
      ...process.env,
      SM_DESKTOP_DEV: '1',
      SM_DESKTOP_URL: frontendUrl,
      SM_BACKEND_URL: 'http://127.0.0.1:8000',
    },
    stdio: 'inherit',
    windowsHide: false,
  });

  electronProcess.on('exit', (code) => {
    if (!shuttingDown) {
      console.log(`[desktop] Electron exited with code ${code}`);
    }
    shutdown(code || 0);
  });
}

function shutdown(exitCode = 0) {
  if (shuttingDown) {
    return;
  }

  shuttingDown = true;
  killProcessTree(electronProcess);
  killProcessTree(frontendProcess);
  killProcessTree(backendProcess);
  process.exit(exitCode);
}

process.on('SIGINT', () => shutdown(0));
process.on('SIGTERM', () => shutdown(0));

start().catch((error) => {
  console.error(`[desktop] ${error.message}`);
  shutdown(1);
});
