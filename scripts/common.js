const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');
const frontendDir = path.join(rootDir, 'frontend');
const electronDir = path.join(rootDir, 'electron');

function isWindows() {
  return process.platform === 'win32';
}

function resolveCommand(command) {
  if (!isWindows()) {
    return command;
  }

  if (command === 'npm') {
    return 'npm.cmd';
  }

  if (command === 'npx') {
    return 'npx.cmd';
  }

  return command;
}

function run(command, args, options = {}) {
  const resolvedCommand = resolveCommand(command);
  const result = spawnSync(resolvedCommand, args, {
    cwd: options.cwd || rootDir,
    stdio: 'inherit',
    shell: isWindows(),
    env: { ...process.env, ...(options.env || {}) }
  });

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

function canRun(command, args) {
  const result = spawnSync(resolveCommand(command), args, {
    stdio: 'ignore',
    shell: isWindows()
  });

  return !result.error && result.status === 0;
}

function resolvePythonCommand() {
  const candidates = isWindows()
    ? [
        { command: 'py', args: ['-3', '--version'] },
        { command: 'python', args: ['--version'] }
      ]
    : [
        { command: 'python3', args: ['--version'] },
        { command: 'python', args: ['--version'] }
      ];

  for (const candidate of candidates) {
    if (canRun(candidate.command, candidate.args)) {
      return candidate.command;
    }
  }

  return null;
}

function getVenvDir() {
  return path.join(backendDir, isWindows() ? 'winvenv' : '.venv');
}

function getVenvPython() {
  return path.join(
    getVenvDir(),
    isWindows() ? 'Scripts' : 'bin',
    isWindows() ? 'python.exe' : 'python'
  );
}

function getVenvTool(toolName) {
  return path.join(
    getVenvDir(),
    isWindows() ? 'Scripts' : 'bin',
    isWindows() ? `${toolName}.exe` : toolName
  );
}

function ensureBackendVenv() {
  const pythonCommand = resolvePythonCommand();
  if (!pythonCommand) {
    console.error('Python 3 is required to set up the backend environment.');
    process.exit(1);
  }

  const venvPython = getVenvPython();
  if (!fs.existsSync(venvPython)) {
    console.log(`Creating backend virtual environment at ${getVenvDir()}...`);
    const createArgs = isWindows() ? ['-3', '-m', 'venv', getVenvDir()] : ['-m', 'venv', getVenvDir()];
    run(pythonCommand, createArgs, { cwd: backendDir });
  }

  return venvPython;
}

module.exports = {
  backendDir,
  electronDir,
  frontendDir,
  getVenvPython,
  getVenvTool,
  ensureBackendVenv,
  isWindows,
  rootDir,
  run
};
