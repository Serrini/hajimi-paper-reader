const { app, BrowserWindow, shell, ipcMain, dialog } = require('electron');
const path = require('path');
const { startBackend, stopBackend, waitForBackend } = require('./utils/backend');

// 是否是开发模式（未打包时，除非指定 FORCE_PROD）
const isDev = !app.isPackaged && !process.env.FORCE_PROD;

let mainWindow = null;

function getResourcePath(...segments) {
  if (isDev || process.env.FORCE_PROD) {
    // 开发模式或强制拉起本地资源测试：资源在项目根目录
    return path.join(__dirname, '..', ...segments);
  } else {
    // 打包后：资源在 process.resourcesPath（extraResources）
    return path.join(process.resourcesPath, ...segments);
  }
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    title: 'iMem Studio',
    // icon: getResourcePath('electron', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false, // 等后端就绪后再显示
    backgroundColor: '#1a1a1a',
  });

  // 在外部浏览器打开所有 target=_blank 链接
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

async function showSplashOrLoad() {
  // 先显示一个加载状态
  if (mainWindow) {
    mainWindow.loadFile(path.join(__dirname, 'loading.html'));
    mainWindow.show();
  }
}

async function loadApp() {
  if (!mainWindow) return;

  if (isDev) {
    // 开发模式：加载 React Dev Server
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    // 生产模式：加载打包后的前端静态文件
    const indexPath = getResourcePath('frontend', 'build', 'index.html');
    mainWindow.loadFile(indexPath);
  }
}

app.whenReady().then(async () => {
  await createWindow();
  await showSplashOrLoad();

  if (!isDev) {
    // 生产模式：启动 Python 后端
    const backendExe = process.env.FORCE_PROD 
        ? getResourcePath('backend', 'dist', 'imem_studio', 'imem_studio.exe')
        : getResourcePath('backend', process.platform === 'win32' ? 'imem_studio.exe' : 'imem_studio');
    console.log('[Electron] 正在启动后端:', backendExe);

    try {
      await startBackend(backendExe);
      console.log('[Electron] 后端启动中，等待就绪...');
      await waitForBackend('http://127.0.0.1:8000/health', 30);
      console.log('[Electron] 后端已就绪');
    } catch (err) {
      console.error('[Electron] 后端启动失败:', err);
      dialog.showErrorBox(
        '启动失败',
        `后端服务无法启动，请检查应用完整性。\n错误：${err.message}`
      );
      app.quit();
      return;
    }
  }

  await loadApp();
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow().then(loadApp);
  }
});

app.on('before-quit', () => {
  stopBackend();
});
