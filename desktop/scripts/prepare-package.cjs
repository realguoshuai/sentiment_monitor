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

function checkDepsInSpec() {
  const reqPath = path.join(repoRoot, 'backend', 'requirements.txt');
  const specPath = path.join(repoRoot, 'backend', 'desktop_backend.spec');

  if (!fs.existsSync(reqPath) || !fs.existsSync(specPath)) return;

  const reqContent = fs.readFileSync(reqPath, 'utf-8');
  const specContent = fs.readFileSync(specPath, 'utf-8');

  // 提取 requirements.txt 中的包名（去版本号、去注释）
  const reqPackages = reqContent
    .split('\n')
    .map(l => l.trim().split(/[>=<!\[]/)[0].trim().toLowerCase().replace(/-/g, '_'))
    .filter(l => l && !l.startsWith('#'));

  // 提取 spec 中的包名
  const specPackages = specContent
    .match(/'([a-z_]+)'/g)
    ?.map(s => s.replace(/'/g, '').toLowerCase()) || [];

  // 只检查不在 spec 中的包（会被 PyInstaller 主包自动依赖的跳过）
  const autoDeps = new Set(['django', 'djangorestframework', 'django_cors_headers',
    'requests', 'python_dateutil', 'pandas', 'numpy', 'beautifulsoup4']);
  const missing = reqPackages.filter(pkg => !specPackages.includes(pkg) && !autoDeps.has(pkg));

  if (missing.length > 0) {
    console.error(`[desktop-package] ERROR: These packages are in requirements.txt but NOT in desktop_backend.spec:`);
    missing.forEach(m => console.error(`  - ${m}`));
    console.error(`[desktop-package] They will be missing from the packaged exe!`);
    console.error(`[desktop-package] Add them to desktop_backend.spec hiddenimports.`);
    process.exit(1);
  }
}

function ensureFile(filePath, hint) {
  if (!fs.existsSync(filePath)) {
    console.error(`[desktop-package] Missing required file: ${filePath}`);
    console.error(`[desktop-package] ${hint}`);
    process.exit(1);
  }
}

// 隐私保护：打包产物中绝不允许出现本机数据库 / 缓存 / 环境变量文件。
// 这些文件可能包含真实持仓、自选股等私人数据，禁止随 exe 分发。
const PRIVATE_FILE_PATTERN = /(\.sqlite3(-journal|-wal|-shm)?|\.db|\.env)$/i;
const PRIVATE_DIR_NAMES = new Set(['cache_data', 'logs']);

function stripPrivateData(dir, removed) {
  if (!fs.existsSync(dir)) return removed;

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const target = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (PRIVATE_DIR_NAMES.has(entry.name.toLowerCase())) {
        fs.rmSync(target, { recursive: true, force: true });
        removed.push(target);
        continue;
      }
      stripPrivateData(target, removed);
      continue;
    }

    if (PRIVATE_FILE_PATTERN.test(entry.name)) {
      fs.rmSync(target, { force: true });
      removed.push(target);
    }
  }

  return removed;
}

function scrubBackendRuntime() {
  const runtimeDir = path.join(repoRoot, 'backend', 'dist', 'SentimentMonitor-runtime');
  const removed = stripPrivateData(runtimeDir, []);

  if (removed.length > 0) {
    console.log('[desktop-package] Removed private files from packaging payload:');
    removed.forEach((item) => console.log(`  - ${path.relative(repoRoot, item)}`));
  } else {
    console.log('[desktop-package] Packaging payload contains no private database/cache files.');
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

checkDepsInSpec();
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
scrubBackendRuntime();

console.log('[desktop-package] Frontend dist and backend executable are ready.');
