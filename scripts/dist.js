const { electronDir, frontendDir, run } = require('./common');

function resolveTargetFlag() {
  if (process.argv.includes('--win')) {
    return '--win';
  }

  if (process.argv.includes('--mac')) {
    return '--mac';
  }

  if (process.argv.includes('--linux')) {
    return '--linux';
  }

  if (process.platform === 'win32') {
    return '--win';
  }

  if (process.platform === 'darwin') {
    return '--mac';
  }

  return '--linux';
}

function main() {
  const targetFlag = resolveTargetFlag();

  console.log(`Building installer for ${targetFlag.replace('--', '')}...`);
  run('npm', ['run', 'build'], {
    cwd: frontendDir,
    env: {
      BUILD_PATH: 'build-desktop'
    }
  });
  run('node', ['../scripts/build-backend.js'], { cwd: electronDir });
  run('npx', ['electron-builder', targetFlag, '--publish', 'never'], { cwd: electronDir });
}

main();
