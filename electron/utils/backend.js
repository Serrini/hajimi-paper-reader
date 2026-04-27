const { execFile } = require('child_process');
const http = require('http');

let backendProcess = null;

/**
 * 启动 Python 后端可执行文件
 * @param {string} exePath - PyInstaller 打包的可执行文件路径
 */
function startBackend(exePath) {
  return new Promise((resolve, reject) => {
    if (backendProcess) {
      return resolve();
    }

    const env = {
      ...process.env,
      // 禁止 Python 输出缓冲，便于日志实时输出
      PYTHONUNBUFFERED: '1',
    };

    backendProcess = execFile(
      exePath,
      [], // 无额外参数，端口等通过 env 传递
      { env },
      (error) => {
        if (error && error.killed === false) {
          console.error('[Backend] 进程异常退出:', error.message);
        }
      }
    );

    backendProcess.stdout?.on('data', (data) => {
      console.log('[Backend stdout]', data.toString().trim());
    });

    backendProcess.stderr?.on('data', (data) => {
      console.error('[Backend stderr]', data.toString().trim());
    });

    backendProcess.on('spawn', () => {
      console.log('[Backend] 进程已启动，PID:', backendProcess.pid);
      resolve();
    });

    backendProcess.on('error', (err) => {
      console.error('[Backend] 启动失败:', err);
      reject(err);
    });
  });
}

/**
 * 等待后端 HTTP 就绪
 * @param {string} healthUrl - 健康检查 URL
 * @param {number} timeoutSec - 超时秒数
 */
function waitForBackend(healthUrl, timeoutSec = 30) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const interval = 500; // ms, 每 500ms 检查一次

    const check = () => {
      http.get(healthUrl, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          retry();
        }
        res.resume(); // 清空响应体
      }).on('error', () => {
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - start >= timeoutSec * 1000) {
        reject(new Error(`后端在 ${timeoutSec} 秒内未就绪`));
      } else {
        setTimeout(check, interval);
      }
    };

    check();
  });
}

/**
 * 停止后端进程
 */
function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    console.log('[Backend] 正在停止后端进程...');
    backendProcess.kill('SIGTERM');
    // Windows 上 SIGTERM 可能不生效，备用 SIGKILL
    setTimeout(() => {
      if (backendProcess && !backendProcess.killed) {
        backendProcess.kill('SIGKILL');
      }
    }, 3000);
    backendProcess = null;
  }
}

module.exports = { startBackend, stopBackend, waitForBackend };
