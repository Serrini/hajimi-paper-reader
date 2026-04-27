/**
 * frontend/src/config.ts
 * 统一的 API 配置入口，自动适配 Electron 和浏览器开发两种环境
 */

// Electron preload 通过 contextBridge 暴露了 window.electronAPI
declare global {
  interface Window {
    electronAPI?: {
      isElectron: boolean;
      getVersion: () => Promise<string>;
    };
  }
}

/**
 * 是否运行在 Electron 壳内
 */
export const isElectron = (): boolean => {
  return !!(window.electronAPI?.isElectron);
};

/**
 * API Base URL
 * - Electron 生产模式：Python 进程监听 localhost:8000
 * - 浏览器开发模式：读取 REACT_APP_API_BASE 环境变量，默认 localhost:8000
 */
export const API_BASE_URL = (() => {
  if (isElectron()) {
    return 'http://127.0.0.1:8000/api';
  }
  return process.env.REACT_APP_API_BASE_URL ?? 'http://localhost:8000/api';
})();

export default API_BASE_URL;
