"""
app_entry.py — PyInstaller 打包专用入口点

在打包模式下正确设置工作目录和数据路径后，启动 uvicorn。
"""
import sys
import os


def fix_frozen_paths():
    """修正 PyInstaller 打包后的路径问题"""
    if getattr(sys, 'frozen', False):
        # 可执行文件所在目录
        exe_dir = os.path.dirname(sys.executable)
        # 将 exe 目录添加到 sys.path，让后端代码能找到自己的模块
        if exe_dir not in sys.path:
            sys.path.insert(0, exe_dir)
        # 切换工作目录到可执行文件所在目录
        os.chdir(exe_dir)
        # 设置环境变量，告知 Config 使用 exe 旁边的数据目录
        os.environ.setdefault('DATA_DIR', os.path.join(exe_dir, 'data'))
    else:
        # 开发模式：切换到 backend/ 目录
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(backend_dir)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)


if __name__ == '__main__':
    fix_frozen_paths()

    import uvicorn
    from app import app

    uvicorn.run(
        app,
        host='127.0.0.1',
        port=8000,
        log_level='info',
        # 不使用 reload（打包后无源码）
        reload=False,
        # 只监听本地回环，不对外暴露
        access_log=True,
    )
