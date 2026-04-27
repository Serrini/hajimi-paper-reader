const fs = require('fs');
const path = require('path');
const {
  backendDir,
  electronDir,
  frontendDir,
  ensureBackendVenv,
  getVenvTool,
  isWindows,
  run
} = require('./common');

const backendOnly = process.argv.includes('--backend-only');

function ensureNodeDeps() {
  if (backendOnly) {
    return;
  }

  console.log('Installing frontend dependencies...');
  run('npm', ['install'], { cwd: frontendDir });

  console.log('Installing Electron dependencies...');
  run('npm', ['install'], { cwd: electronDir });
}

function ensureBackendDeps() {
  const venvPython = ensureBackendVenv();
  const pipPath = getVenvTool('pip');
  const requirementsPath = path.join(backendDir, 'requirements.txt');
  const stampPath = path.join(backendDir, '.deps-installed');
  const pythonEnv = {
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8'
  };
  const requirementsMtime = fs.statSync(requirementsPath).mtimeMs;
  const stampMtime = fs.existsSync(stampPath) ? fs.statSync(stampPath).mtimeMs : 0;

  if (stampMtime >= requirementsMtime) {
    console.log('Backend Python dependencies are already up to date.');
    return;
  }

  console.log('Installing backend Python dependencies...');
  run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip'], {
    cwd: backendDir,
    env: pythonEnv
  });

  if (fs.existsSync(pipPath)) {
    run(pipPath, ['install', '-r', 'requirements.txt'], {
      cwd: backendDir,
      env: pythonEnv
    });
  } else {
    run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements.txt'], {
      cwd: backendDir,
      env: pythonEnv
    });
  }

  fs.writeFileSync(
    stampPath,
    `deps installed on ${new Date().toISOString()} (${isWindows() ? 'windows' : process.platform})\n`,
    'utf8'
  );
}

ensureNodeDeps();
ensureBackendDeps();
