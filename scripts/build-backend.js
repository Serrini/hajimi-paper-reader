const fs = require('fs');
const path = require('path');
const { backendDir, ensureBackendVenv, getVenvTool, run } = require('./common');

function resolveExecutable(preferredPath, fallbackName, missingMessage) {
  if (fs.existsSync(preferredPath)) {
    return preferredPath;
  }

  if (fallbackName) {
    return fallbackName;
  }

  console.error(missingMessage);
  process.exit(1);
}

function main() {
  const venvPython = ensureBackendVenv();
  const obfuscatedOutputName = `obfuscated_${new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '_')}`;
  const obfuscatedPath = path.join(backendDir, 'dist', obfuscatedOutputName);
  const pyinstaller = resolveExecutable(
    getVenvTool('pyinstaller'),
    null,
    'PyInstaller was not found in the backend virtual environment. Run `npm install` at the repo root first.'
  );

  console.log('Obfuscating backend sources...');
  run(venvPython, ['obfuscate_cross_platform.py'], {
    cwd: backendDir,
    env: {
      OBFUSCATED_OUTPUT_NAME: obfuscatedOutputName
    }
  });

  const specFile = path.join(backendDir, 'imem_studio.spec');
  console.log('Packaging backend binary with PyInstaller...');
  run(pyinstaller, [specFile, '--clean', '--noconfirm'], {
    cwd: backendDir,
    env: {
      OBFUSCATED_PATH: obfuscatedPath
    }
  });
}

main();
