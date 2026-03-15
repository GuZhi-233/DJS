#!/usr/bin/env python
# -*- coding: utf-8 -*-



import os
import sys
import time
import subprocess
import argparse
import socket
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ---------- 基础路径 ----------
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)          # 打包后 exe 所在目录
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录

MAIN_APP = os.path.join(BASE_DIR, "倒计时.exe")
LOG_FILE = os.path.join(BASE_DIR, "zlog.txt")

# ---------- 日志配置 ----------
logger = logging.getLogger("AutoStart")
logger.setLevel(logging.DEBUG)

# 文件处理器（按大小轮转）
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# 可选：控制台输出（调试用，默认关闭）
# console = logging.StreamHandler()
# console.setLevel(logging.DEBUG)
# console.setFormatter(formatter)
# logger.addHandler(console)

def log(level, msg):
    """简易日志封装（兼容原有调用）"""
    if level == 1:
        logger.error(msg)
    elif level == 2:
        logger.info(msg)
    elif level == 3:
        logger.debug(msg)
    else:
        logger.info(msg)

# ---------- 系统就绪检测 ----------
def wait_for_system_ready(delay=30, wait_network=False, network_target="8.8.8.8", network_timeout=5):
    """
    等待系统准备就绪
    :param delay: 基础等待时间（秒）
    :param wait_network: 是否等待网络连通
    :param network_target: 网络连通测试的目标地址（IP或域名）
    :param network_timeout: 网络测试超时（秒）
    """
    log(2, f"开始等待系统准备就绪，基础延迟 {delay} 秒，等待网络: {wait_network}")

    # 1. 基础延迟（让系统完成大部分启动任务）
    if delay > 0:
        log(2, f"等待 {delay} 秒基础延迟...")
        time.sleep(delay)

    # 2. 可选：等待网络连通
    if wait_network:
        log(2, f"检测网络连通性（目标: {network_target}）...")
        start = time.time()
        while time.time() - start < 60:  # 最多等待 60 秒
            try:
                # 尝试 DNS 解析（如果是域名）或直接连接
                socket.gethostbyname(network_target)
                # 简单 ping 式检测（使用 socket 连接测试）
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(network_timeout)
                result = sock.connect_ex((network_target, 80))  # 尝试连接 HTTP 端口
                sock.close()
                if result == 0:
                    log(2, "网络已连通")
                    break
            except Exception:
                pass
            log(3, "网络尚未就绪，等待 2 秒后重试...")
            time.sleep(2)
        else:
            log(1, "等待网络超时，继续启动主程序")

    # 3. 检测桌面是否已加载（Windows 下检查 explorer.exe 进程）
    if sys.platform == "win32":
        log(2, "检查桌面进程 explorer.exe...")
        for _ in range(10):  # 最多等待 10 次（20秒）
            try:
                output = subprocess.check_output(
                    'tasklist /FI "IMAGENAME eq explorer.exe"',
                    shell=True, text=True
                )
                if "explorer.exe" in output:
                    log(2, "桌面进程已存在")
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            log(1, "未检测到 explorer.exe，可能系统尚未完全登录")

    log(2, "系统就绪检测完成")

# ---------- 启动主程序 ----------
def start_main_app():
    """启动倒计时主程序"""
    if not os.path.exists(MAIN_APP):
        log(1, f"主程序不存在: {MAIN_APP}")
        return False

    try:
        # Windows 下隐藏启动窗口
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # 隐藏主窗口（主程序自己会创建窗口）
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creationflags = subprocess.CREATE_NO_WINDOW  # 不创建控制台窗口

        # 启动主程序
        proc = subprocess.Popen(
            [MAIN_APP],
            startupinfo=startupinfo,
            creationflags=creationflags,
            close_fds=True  # 避免继承不必要的句柄
        )
        log(2, f"主程序启动成功，PID: {proc.pid}")
        return True
    except Exception as e:
        log(1, f"启动主程序失败: {e}")
        return False

# ---------- 主函数 ----------
def main():
    parser = argparse.ArgumentParser(description="倒计时自启动辅助程序")
    parser.add_argument(
        "--delay", type=int, default=30,
        help="启动前的基础延迟时间（秒），默认 30 秒"
    )
    parser.add_argument(
        "--wait-network", action="store_true",
        help="等待网络连通后再启动（默认不等待）"
    )
    parser.add_argument(
        "--network-target", type=str, default="8.8.8.8",
        help="网络连通测试目标（IP或域名），默认 8.8.8.8"
    )
    parser.add_argument(
        "--now", action="store_true",
        help="立即启动，忽略所有等待条件"
    )
    args = parser.parse_args()

    log(2, "=== 自启动程序开始运行 ===")
    log(2, f"当前工作目录: {os.getcwd()}")
    log(2, f"程序所在目录: {BASE_DIR}")
    log(2, f"Python 版本: {sys.version}")

    # 如果指定 --now，立即启动
    if args.now:
        log(2, "立即启动模式，跳过等待")
    else:
        # 等待系统就绪
        wait_for_system_ready(
            delay=args.delay,
            wait_network=args.wait_network,
            network_target=args.network_target
        )

    # 启动主程序（最多重试 3 次）
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        log(2, f"尝试启动主程序 (第 {attempt} 次)")
        if start_main_app():
            break
        elif attempt < max_retries:
            log(2, "等待 2 秒后重试...")
            time.sleep(2)
    else:
        log(1, "主程序启动失败，已达到最大重试次数")

    log(2, "=== 自启动程序退出 ===")

if __name__ == "__main__":
    main()