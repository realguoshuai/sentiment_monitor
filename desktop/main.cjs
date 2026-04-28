const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const path = require('path');

const isDev = process.env.SM_DESKTOP_DEV === '1';
const repoRoot = path.resolve(__dirname, '..');
const backendDir = path.join(repoRoot, 'backend');
const isPackaged = app.isPackaged;
const packagedResourcesDir = process.resourcesPath;
const windowIconFile = isPackaged
  ? path.join(process.resourcesPath, 'icon.png')
  : path.join(__dirname, 'assets', 'icon.png');
const frontendDistDir = isPackaged
  ? path.join(packagedResourcesDir, 'frontend-dist')
  : path.join(repoRoot, 'frontend', 'dist');
const frontendDistFile = path.join(frontendDistDir, 'index.html');
const packagedBackendExe = isPackaged
  ? path.join(packagedResourcesDir, 'backend', 'SentimentMonitor.exe')
  : path.join(repoRoot, 'backend', 'dist', 'SentimentMonitor-runtime', 'SentimentMonitor.exe');
const packagedSeedDb = isPackaged
  ? path.join(packagedResourcesDir, 'backend', 'db.sqlite3')
  : path.join(repoRoot, 'backend', 'db.sqlite3');
const backendUrl = process.env.SM_BACKEND_URL || 'http://127.0.0.1:8000';
const frontendDevUrl = process.env.SM_DESKTOP_URL || 'http://127.0.0.1:5173';

let mainWindow = null;
let backendProcess = null;
let runtimePaths = null;
let desktopLogFile = null;

app.setName('Sentiment Monitor');

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!mainWindow) {
      return;
    }
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.show();
    mainWindow.focus();
  });
}

function getDesktopLogFile() {
  if (desktopLogFile) {
    return desktopLogFile;
  }

  let baseDir = null;
  try {
    if (app.isReady()) {
      baseDir = app.getPath('userData');
    }
  } catch (error) {
    // Fall back below; early startup logging should never crash the app.
  }

  baseDir =
    baseDir ||
    path.join(process.env.APPDATA || process.env.LOCALAPPDATA || process.cwd(), 'Sentiment Monitor');

  const logDir = path.join(baseDir, 'logs');
  fs.mkdirSync(logDir, { recursive: true });
  desktopLogFile = path.join(logDir, 'desktop-main.log');
  return desktopLogFile;
}

function formatError(error) {
  if (error && error.stack) {
    return error.stack;
  }
  return String(error);
}

function logDesktop(message, error) {
  try {
    const details = error ? `\n${formatError(error)}` : '';
    fs.appendFileSync(
      getDesktopLogFile(),
      `[${new Date().toISOString()}] ${message}${details}\n`,
      'utf8',
    );
  } catch (logError) {
    // Logging is diagnostic only.
  }
}

function writeProcessStream(stream, message) {
  try {
    stream.write(message);
  } catch (error) {
    logDesktop('Failed to write process stream', error);
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function uniquePaths(paths) {
  return [...new Set(paths)];
}

function getFrontendDistCandidates() {
  if (!isPackaged) {
    return [path.join(repoRoot, 'frontend', 'dist')];
  }

  return uniquePaths([
    path.join(__dirname, 'frontend-dist'),
    path.join(packagedResourcesDir, 'frontend-dist'),
    path.join(path.dirname(process.execPath), 'resources', 'frontend-dist'),
  ]);
}

function resolveFrontendDist() {
  const candidates = getFrontendDistCandidates();
  for (const candidate of candidates) {
    const indexFile = path.join(candidate, 'index.html');
    if (fs.existsSync(indexFile)) {
      return {
        exists: true,
        dir: candidate,
        file: indexFile,
        candidates,
      };
    }
  }

  const fallbackDir = candidates[0] || frontendDistDir;
  return {
    exists: false,
    dir: fallbackDir,
    file: path.join(fallbackDir, 'index.html'),
    candidates,
  };
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

function resolveBackendLaunch() {
  if (!isDev && fs.existsSync(packagedBackendExe)) {
    return {
      command: packagedBackendExe,
      args: [],
      cwd: path.dirname(packagedBackendExe),
    };
  }

  const { command, prefixArgs } = resolvePythonCommand();
  return {
    command,
    args: [
      ...prefixArgs,
      '-m',
      'uvicorn',
      'sentiment_monitor.asgi:application',
      '--host',
      '127.0.0.1',
      '--port',
      '8000',
    ],
    cwd: backendDir,
  };
}

function ensureRuntimePaths() {
  const userDataDir = app.getPath('userData');
  const runtimeDir = path.join(userDataDir, 'backend-runtime');
  const cacheDir = path.join(runtimeDir, 'cache_data');
  const dbPath = path.join(runtimeDir, 'db.sqlite3');

  fs.mkdirSync(runtimeDir, { recursive: true });
  fs.mkdirSync(cacheDir, { recursive: true });

  if (isPackaged && fs.existsSync(packagedSeedDb) && !fs.existsSync(dbPath)) {
    fs.copyFileSync(packagedSeedDb, dbPath);
  }

  return {
    userDataDir,
    runtimeDir,
    cacheDir,
    dbPath,
  };
}

function waitForUrl(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;

  return new Promise((resolve, reject) => {
    const attempt = () => {
      const request = http.get(url, (response) => {
        response.resume();
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve();
          return;
        }

        if (Date.now() >= deadline) {
          reject(new Error(`Timed out waiting for ${url}: last status ${response.statusCode}`));
          return;
        }

        setTimeout(attempt, 500);
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

function spawnBackend() {
  const launch = resolveBackendLaunch();
  logDesktop(
    [
      `Starting backend: ${launch.command} ${launch.args.join(' ')}`.trim(),
      `cwd=${launch.cwd}`,
      `runtime=${runtimePaths ? runtimePaths.runtimeDir : backendDir}`,
      `db=${runtimePaths ? runtimePaths.dbPath : path.join(backendDir, 'db.sqlite3')}`,
      `cache=${runtimePaths ? runtimePaths.cacheDir : path.join(backendDir, 'cache_data')}`,
    ].join('\n'),
  );

  backendProcess = spawn(launch.command, launch.args, {
    cwd: launch.cwd,
    env: {
      ...process.env,
      ENABLE_STARTUP_WARM: isDev ? (process.env.ENABLE_STARTUP_WARM || '1') : '0',
      SENTIMENT_MONITOR_DESKTOP: '1',
      DJANGO_DEBUG: isDev ? 'True' : 'False',
      SENTIMENT_MONITOR_HOME: runtimePaths ? runtimePaths.runtimeDir : backendDir,
      DJANGO_DB_PATH: runtimePaths ? runtimePaths.dbPath : path.join(backendDir, 'db.sqlite3'),
      DJANGO_CACHE_DIR: runtimePaths ? runtimePaths.cacheDir : path.join(backendDir, 'cache_data'),
    },
    stdio: 'pipe',
    windowsHide: true,
  });

  backendProcess.stdout.on('data', (chunk) => {
    const message = `[desktop-backend] ${chunk}`;
    logDesktop(message.trimEnd());
    writeProcessStream(process.stdout, message);
  });

  backendProcess.stderr.on('data', (chunk) => {
    const message = `[desktop-backend] ${chunk}`;
    logDesktop(message.trimEnd());
    writeProcessStream(process.stderr, message);
  });

  backendProcess.on('error', (error) => {
    logDesktop('Backend process failed to start', error);
    backendProcess = null;
  });

  backendProcess.on('exit', (code, signal) => {
    backendProcess = null;
    logDesktop(`Backend exited with code=${code} signal=${signal}`);
    if (!app.isQuitting) {
      writeProcessStream(process.stderr, `[desktop-backend] exited with code ${code} signal ${signal}\n`);
    }
  });
}

function waitForBackendStartup(url, timeoutMs = 30000) {
  const child = backendProcess;
  if (!child) {
    return Promise.reject(new Error('Backend process was not started'));
  }

  return new Promise((resolve, reject) => {
    let settled = false;

    const cleanup = () => {
      child.off('exit', onExit);
      child.off('error', onError);
    };

    const settle = (callback, value) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      callback(value);
    };

    const onExit = (code, signal) => {
      settle(
        reject,
        new Error(`Backend exited before it became ready (code=${code}, signal=${signal})`),
      );
    };

    const onError = (error) => {
      settle(reject, error);
    };

    child.once('exit', onExit);
    child.once('error', onError);

    waitForUrl(url, timeoutMs).then(
      () => settle(resolve),
      (error) => settle(reject, error),
    );
  });
}

function createMainWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    return mainWindow;
  }

  mainWindow = new BrowserWindow({
    width: 1500,
    height: 960,
    minWidth: 1200,
    minHeight: 760,
    title: 'Sentiment Monitor',
    icon: fs.existsSync(windowIconFile) ? windowIconFile : undefined,
    backgroundColor: '#f5f7fb',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    logDesktop(`[frontend-console:${level}] ${message} (${sourceId}:${line})`);
  });
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    logDesktop(`Frontend failed to load ${validatedURL}: ${errorCode} ${errorDescription}`);
  });
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    logDesktop(`Renderer process gone: ${JSON.stringify(details)}`);
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

async function showStartupWindow() {
  const window = createMainWindow();
  const message = [
    '<html><body style="margin:0;font-family:Segoe UI,Arial;background:#f5f7fb;color:#0f172a;">',
    '<div style="height:100vh;display:flex;align-items:center;justify-content:center;">',
    '<div style="text-align:center;">',
    '<h2 style="margin:0 0 12px;font-size:22px;">Sentiment Monitor</h2>',
    '<p style="margin:0;color:#64748b;">Starting local analysis service...</p>',
    '</div></div></body></html>',
  ].join('');
  await window.loadURL(`data:text/html,${encodeURIComponent(message)}`);
}

async function loadAppWindow() {
  const window = createMainWindow();

  if (isDev) {
    await window.loadURL(frontendDevUrl);
    window.webContents.openDevTools({ mode: 'detach' });
    return;
  }

  const frontendDist = resolveFrontendDist();
  if (!frontendDist.exists) {
    const checkedFiles = frontendDist.candidates
      .map((candidate) => path.join(candidate, 'index.html'))
      .join('\n');

    const message = [
      '<html><body style="font-family:Segoe UI;padding:32px;background:#f8fafc;color:#0f172a;">',
      '<h2>Frontend build not found</h2>',
      '<p>The packaged frontend files are missing. Rebuild the desktop package with <code>npm run dist</code>.</p>',
      `<pre style="white-space:pre-wrap;background:#e2e8f0;padding:16px;border-radius:8px;">${escapeHtml(checkedFiles)}</pre>`,
      '</body></html>',
    ].join('');
    await window.loadURL(`data:text/html,${encodeURIComponent(message)}`);
    return;
  }

  await window.loadFile(frontendDist.file);
}

async function bootstrap() {
  runtimePaths = ensureRuntimePaths();
  const frontendDist = resolveFrontendDist();
  logDesktop(
    [
      `Bootstrapping desktop app packaged=${isPackaged} dev=${isDev}`,
      `resources=${packagedResourcesDir}`,
      `frontend=${frontendDist.file} exists=${frontendDist.exists}`,
      `frontendCandidates=${frontendDist.candidates
        .map((candidate) => path.join(candidate, 'index.html'))
        .join(';')}`,
      `backend=${packagedBackendExe} exists=${fs.existsSync(packagedBackendExe)}`,
      `seedDb=${packagedSeedDb} exists=${fs.existsSync(packagedSeedDb)}`,
      `userData=${runtimePaths.userDataDir}`,
    ].join('\n'),
  );

  if (!isDev) {
    await showStartupWindow();
    spawnBackend();
    waitForBackendStartup(`${backendUrl}/api/stocks/`, 60000)
      .then(() => {
        logDesktop(`Backend ready at ${backendUrl}`);
      })
      .catch((error) => {
        logDesktop('Backend startup failed', error);
        if (mainWindow && !mainWindow.isDestroyed()) {
          dialog.showErrorBox('Backend startup failed', String(error.message || error));
        }
      });
  }

  await loadAppWindow();
  logDesktop('Desktop window loaded');
}

app.isQuitting = false;

function handleFatalStartupError(error) {
  logDesktop('Fatal desktop startup error', error);
  try {
    dialog.showErrorBox('Sentiment Monitor failed to start', String(error.message || error));
  } catch (dialogError) {
    logDesktop('Failed to show startup error dialog', dialogError);
  }
  app.quit();
}

process.on('uncaughtException', handleFatalStartupError);
process.on('unhandledRejection', handleFatalStartupError);

if (gotSingleInstanceLock) {
  app.whenReady().then(bootstrap).catch(handleFatalStartupError);
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
  killProcessTree(backendProcess);
});

app.on('activate', async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await loadAppWindow();
  }
});
