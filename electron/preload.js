// preload.js — 在渲染进程加载前执行的脚本
// contextIsolation=true 下通过 contextBridge 安全暴露 API

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // 标识当前是 Electron 环境（前端可用来判断 API base）
  isElectron: true,
  // 获取应用版本
  getVersion: () => ipcRenderer.invoke('get-version'),
});
