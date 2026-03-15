#!/usr/bin/env python
# -*- coding: utf-8 -*-


import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import psutil
import os
import sys
import time
import threading
import queue
import json
import logging
from logging.handlers import RotatingFileHandler
import ctypes
from datetime import datetime

# ==================== 监控程序自身日志配置 ====================
DEBUG_LEVEL = 2  # 默认二级（1=错误，2=信息，3=调试）
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "monitor.log")

logger = logging.getLogger("Monitor")
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=3, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def log(level, msg):
    """自定义日志函数，按等级过滤"""
    if level <= DEBUG_LEVEL:
        if level == 1:
            logger.error(msg)
        elif level == 2:
            logger.info(msg)
        elif level == 3:
            logger.debug(msg)

# ==================== 日志文件监控器 ====================
class LogMonitor:
    """实时监控指定日志文件的线程类（增强版：自动重连）"""
    def __init__(self, log_path, log_queue, name):
        self.log_path = log_path
        self.log_queue = log_queue
        self.name = name
        self.file = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()
        log(3, f"LogMonitor 启动监控 {name}: {log_path}")

    def _monitor(self):
        """循环读取新行，文件不存在则等待，断开后重连"""
        while not self.stop_event.is_set():
            # 等待文件创建
            if not os.path.exists(self.log_path):
                log(3, f"等待日志文件创建: {self.log_path}")
                time.sleep(2)
                continue

            try:
                # 尝试打开文件
                if self.file is None:
                    self.file = open(self.log_path, 'r', encoding='utf-8')
                    self.file.seek(0, 2)  # 移动到末尾
                    log(2, f"开始监控日志文件: {self.log_path}")
            except Exception as e:
                log(1, f"打开日志文件失败 {self.log_path}: {e}")
                time.sleep(2)
                continue

            try:
                line = self.file.readline()
                if line:
                    self.log_queue.put((self.name, line.strip()))
                else:
                    time.sleep(0.5)
            except Exception as e:
                log(1, f"读取日志文件出错 {self.log_path}: {e}")
                # 关闭文件，下次循环重新打开
                if self.file:
                    self.file.close()
                    self.file = None
                time.sleep(1)

        # 退出前关闭文件
        if self.file:
            self.file.close()
            log(3, f"停止监控日志文件: {self.log_path}")

    def stop(self):
        self.stop_event.set()

# ==================== 主应用程序 ====================
class MonitorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("监控器")
        self.root.geometry("950x700")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        # 尝试隐藏控制台（如果打包为exe）
        if sys.platform == "win32" and hasattr(sys, 'frozen'):
            whnd = ctypes.windll.kernel32.GetConsoleWindow()
            if whnd:
                ctypes.windll.user32.ShowWindow(whnd, 0)

        # 系统托盘（可选）
        self.tray_icon = None
        self.setup_tray()

        # 监控的进程信息（支持中文进程名）
        self.target_processes = {
            "倒计时.exe": "主程序",
            "djs.exe": "主程序",      # 保留可能的英文名
            "djs.py": "主程序",
            "autostart.exe": "自启动程序",
            "autostart.pyw": "自启动程序"
        }
        self.process_status = {}  # pid -> (display_name, exe_name, start_time, status)

        # 日志队列，用于线程间通信
        self.log_queue = queue.Queue()

        # 界面布局
        self.create_widgets()

        # 启动进程监控线程
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        # 启动日志监控线程
        base_dir = os.path.dirname(os.path.abspath(__file__))
        main_log = os.path.join(base_dir, "data", "LOG.txt")
        autostart_log = os.path.join(base_dir, "zlog.txt")  # 根目录下的 zlog.txt
        log(2, f"主程序日志路径: {main_log}")
        log(2, f"自启动程序日志路径: {autostart_log}")
        self.log_monitors = [
            LogMonitor(main_log, self.log_queue, "主程序"),
            LogMonitor(autostart_log, self.log_queue, "自启动程序")
        ]

        # 定时更新界面
        self.update_interval = 100  # 毫秒
        self.update_gui()

        self.root.mainloop()

    def setup_tray(self):
        """创建系统托盘图标（需要 pystray 和 Pillow）"""
        try:
            import pystray
            from PIL import Image, ImageDraw
            image = Image.new('RGB', (64, 64), color='#3498db')
            draw = ImageDraw.Draw(image)
            draw.text((10, 20), "监控", fill='white')
            menu = pystray.Menu(
                pystray.MenuItem("显示", self.show_window),
                pystray.MenuItem("退出", self.quit_app)
            )
            self.tray_icon = pystray.Icon("monitor", image, "进程监控", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except ImportError:
            log(2, "pystray未安装，系统托盘功能不可用")

    def create_widgets(self):
        """构建GUI界面"""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 进程监控区域
        proc_frame = ttk.LabelFrame(main_frame, text="进程状态 (可多选)", padding=5)
        proc_frame.pack(fill=tk.X, pady=5)

        # 创建Treeview，支持多选
        columns = ("pid", "display_name", "exe_name", "status", "start_time")
        self.tree = ttk.Treeview(proc_frame, columns=columns, show="headings", height=5, selectmode='extended')
        self.tree.heading("pid", text="PID")
        self.tree.heading("display_name", text="程序名")
        self.tree.heading("exe_name", text="可执行文件")
        self.tree.heading("status", text="状态")
        self.tree.heading("start_time", text="启动时间")
        self.tree.column("pid", width=60)
        self.tree.column("display_name", width=100)
        self.tree.column("exe_name", width=120)
        self.tree.column("status", width=80)
        self.tree.column("start_time", width=160)
        self.tree.pack(fill=tk.X)

        # 绑定点击事件，用于锁定选中功能
        self.tree.bind('<Button-1>', self.on_tree_click)

        # 进程控制按钮框架
        ctrl_proc_frame = ttk.Frame(proc_frame)
        ctrl_proc_frame.pack(fill=tk.X, pady=5)

        # 锁定选中复选框
        self.lock_selection_var = tk.BooleanVar(value=False)
        lock_cb = ttk.Checkbutton(ctrl_proc_frame, text="锁定选中", variable=self.lock_selection_var)
        lock_cb.pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_proc_frame, text="终止选中", command=self.terminate_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_proc_frame, text="暂停选中", command=self.suspend_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_proc_frame, text="恢复选中", command=self.resume_selected).pack(side=tk.LEFT, padx=5)

        # 日志监控区域（使用 Notebook 分页）
        log_notebook = ttk.Notebook(main_frame)
        log_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # 主程序日志页
        self.main_log_text = scrolledtext.ScrolledText(log_notebook, wrap=tk.WORD, height=12)
        log_notebook.add(self.main_log_text, text="主程序日志")

        # 自启动程序日志页
        self.auto_log_text = scrolledtext.ScrolledText(log_notebook, wrap=tk.WORD, height=12)
        log_notebook.add(self.auto_log_text, text="自启动程序日志")

        # 控制栏
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ctrl_frame, text="调试等级:").pack(side=tk.LEFT, padx=5)
        self.debug_level_var = tk.IntVar(value=DEBUG_LEVEL)
        debug_combo = ttk.Combobox(ctrl_frame, textvariable=self.debug_level_var,
                                   values=[1,2,3], state="readonly", width=5)
        debug_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="应用等级", command=self.set_debug_level).pack(side=tk.LEFT, padx=5)

        ttk.Label(ctrl_frame, text="日志过滤:").pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(ctrl_frame, textvariable=self.filter_var,
                                    values=["全部", "ERROR", "INFO", "DEBUG"], state="readonly", width=10)
        filter_combo.pack(side=tk.LEFT, padx=5)

        # 调试命令选择与发送
        ttk.Label(ctrl_frame, text="调试命令:").pack(side=tk.LEFT, padx=5)
        self.cmd_var = tk.StringVar()
        cmd_combo = ttk.Combobox(ctrl_frame, textvariable=self.cmd_var,
                                 values=["0:关闭调试", "1:调试等级1", "2:调试等级2", "3:调试等级3",
                                         "111:禁用所有插件", "222:禁用插件并重启", "333:重启主程序",
                                         "444:终止主程序", "555:重置并重启", "666:隐藏所有窗口",
                                         "777:模拟错误"], state="readonly", width=20)
        cmd_combo.pack(side=tk.LEFT, padx=5)
        cmd_combo.current(0)

        ttk.Button(ctrl_frame, text="发送调试命令", command=self.send_debug_command).pack(side=tk.LEFT, padx=5)

        # 帮助按钮
        ttk.Button(ctrl_frame, text="调试命令帮助", command=self.show_help).pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="清空日志", command=self.clear_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="刷新进程", command=self.refresh_process).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="退出", command=self.quit_app).pack(side=tk.RIGHT, padx=5)

    def on_tree_click(self, event):
        """处理 Treeview 点击事件，用于实现锁定选中功能"""
        if self.lock_selection_var.get():
            # 锁定状态下，点击空白区域（没有选中项）时，阻止默认的取消选择行为
            item = self.tree.identify_row(event.y)
            if not item:  # 点击空白处
                return "break"  # 返回 "break" 阻止默认事件

    def show_help(self):
        """打开调试命令帮助窗口"""
        help_win = tk.Toplevel(self.root)
        help_win.title("调试命令帮助")
        help_win.geometry("450x400")
        help_win.resizable(False, False)

        text = scrolledtext.ScrolledText(help_win, wrap=tk.WORD, font=("微软雅黑", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        help_content = """可发送的调试命令及含义：

0  : 关闭主程序的调试模式（set_debug_level 0）
1  : 主程序调试模式等级为1（仅错误）
2  : 主程序调试模式等级为2（错误+信息）
3  : 主程序调试模式等级为3（错误+信息+调试）
111: 禁用所有插件
222: 禁用所有插件并重新启动主程序
333: 重新启动主程序
444: 终止主程序进程
555: 重置主程序设置为初始状态并重新启动
666: 隐藏所有倒计时窗口
777: 模拟发生错误并记录日志

使用方法：在上方“调试命令”下拉框中选择对应项，点击“发送调试命令”即可。
"""
        text.insert(tk.END, help_content)
        text.config(state=tk.DISABLED)

        ttk.Button(help_win, text="关闭", command=help_win.destroy).pack(pady=5)

    def monitor_loop(self):
        """定期检查进程状态"""
        while True:
            self.check_processes()
            time.sleep(2)  # 每2秒检查一次

    def check_processes(self):
        """扫描进程，更新 self.process_status，包括状态"""
        current = {}
        for proc in psutil.process_iter(['pid', 'name', 'create_time', 'status']):
            try:
                name = proc.info['name']
                if name in self.target_processes:
                    pid = proc.info['pid']
                    create_time = proc.info['create_time']
                    if create_time:
                        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(create_time))
                    else:
                        start_time = "未知"
                    display_name = self.target_processes[name]
                    status = proc.info['status']
                    # 将状态转换为更友好的显示
                    if status == psutil.STATUS_RUNNING:
                        status_display = "运行中"
                    elif status == psutil.STATUS_STOPPED:
                        status_display = "已暂停"
                    elif status == psutil.STATUS_SLEEPING:
                        status_display = "休眠"
                    elif status == psutil.STATUS_DISK_SLEEP:
                        status_display = "磁盘休眠"
                    elif status == psutil.STATUS_ZOMBIE:
                        status_display = "僵尸"
                    elif status == psutil.STATUS_DEAD:
                        status_display = "已终止"
                    else:
                        status_display = status.capitalize()
                    current[pid] = (display_name, name, start_time, status_display)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 检测新进程和消失进程
        current_pids = set(current.keys())
        old_pids = set(self.process_status.keys())

        new_pids = current_pids - old_pids
        lost_pids = old_pids - current_pids

        for pid in new_pids:
            display_name, exe_name, start, status_display = current[pid]
            log(2, f"检测到新进程: {display_name} ({exe_name}, PID: {pid}) 启动时间: {start} 状态: {status_display}")
            self.process_status[pid] = (display_name, exe_name, start, status_display)

        for pid in lost_pids:
            display_name, exe_name, start, status_display = self.process_status[pid]
            log(2, f"进程已退出: {display_name} ({exe_name}, PID: {pid})")
            del self.process_status[pid]

        # 更新已有进程的状态（可能变化）
        for pid in (old_pids & current_pids):
            if pid in current:
                _, _, _, new_status = current[pid]
                old = self.process_status[pid]
                if old[3] != new_status:
                    # 状态发生变化，更新
                    display_name, exe_name, start, _ = old
                    self.process_status[pid] = (display_name, exe_name, start, new_status)
                    log(3, f"进程状态变化: {display_name} (PID:{pid}) {old[3]} -> {new_status}")

        # 更新界面
        self.root.after(0, self.update_process_tree)

    def update_process_tree(self):
        """刷新进程列表"""
        # 获取当前选中项的PID集合，以便保持选中（如果锁定状态）
        selected_pids = set()
        for item in self.tree.selection():
            values = self.tree.item(item, 'values')
            if values:
                selected_pids.add(int(values[0]))

        # 清空并重新插入
        for item in self.tree.get_children():
            self.tree.delete(item)

        for pid, (display_name, exe_name, start, status_display) in self.process_status.items():
            item_id = self.tree.insert("", tk.END, values=(pid, display_name, exe_name, status_display, start))
            # 如果该PID之前被选中，则重新选中
            if pid in selected_pids:
                self.tree.selection_add(item_id)

    def get_selected_pids(self):
        """获取当前在进程列表中选中的所有 PID"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请至少选择一个进程")
            return []
        pids = []
        for item in selected:
            values = self.tree.item(item, 'values')
            if values:
                pids.append(int(values[0]))
        return pids

    def terminate_selected(self):
        """终止所有选中的进程"""
        pids = self.get_selected_pids()
        if not pids:
            return
        if not messagebox.askyesno("确认", f"确定要终止选中的 {len(pids)} 个进程吗？"):
            return
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                log(2, f"已发送终止信号给 PID {pid}")
            except Exception as e:
                log(1, f"终止进程 PID {pid} 失败: {e}")
                messagebox.showerror("错误", f"终止 PID {pid} 失败: {e}")
        self.check_processes()
        messagebox.showinfo("完成", "已发送终止信号给所有选中的进程。")

    def suspend_selected(self):
        """暂停所有选中的进程"""
        pids = self.get_selected_pids()
        if not pids:
            return
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.suspend()
                log(2, f"已暂停 PID {pid}")
            except Exception as e:
                log(1, f"暂停进程 PID {pid} 失败: {e}")
                messagebox.showerror("错误", f"暂停 PID {pid} 失败: {e}")
        self.check_processes()
        messagebox.showinfo("完成", "已暂停所有选中的进程。")

    def resume_selected(self):
        """恢复所有选中的进程"""
        pids = self.get_selected_pids()
        if not pids:
            return
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.resume()
                log(2, f"已恢复 PID {pid}")
            except Exception as e:
                log(1, f"恢复进程 PID {pid} 失败: {e}")
                messagebox.showerror("错误", f"恢复 PID {pid} 失败: {e}")
        self.check_processes()
        messagebox.showinfo("完成", "已恢复所有选中的进程。")

    def send_debug_command(self):
        """根据下拉框选择发送调试命令（JSON格式）"""
        cmd_text = self.cmd_var.get()
        if not cmd_text:
            messagebox.showwarning("警告", "请选择一个调试命令")
            return

        # 解析命令代码（冒号前的数字）
        try:
            code = cmd_text.split(':')[0].strip()
        except:
            messagebox.showerror("错误", "命令格式错误")
            return

        # 构建命令字典
        cmd_dict = None
        if code == "0":
            cmd_dict = {"command": "set_debug_level", "level": 0}
        elif code == "1":
            cmd_dict = {"command": "set_debug_level", "level": 1}
        elif code == "2":
            cmd_dict = {"command": "set_debug_level", "level": 2}
        elif code == "3":
            cmd_dict = {"command": "set_debug_level", "level": 3}
        elif code == "111":
            cmd_dict = {"command": "disable_all_plugins"}  # 需要主程序支持
        elif code == "222":
            cmd_dict = {"command": "disable_all_plugins_and_restart"}
        elif code == "333":
            cmd_dict = {"command": "restart"}
        elif code == "444":
            cmd_dict = {"command": "terminate"}
        elif code == "555":
            cmd_dict = {"command": "reset_and_restart"}
        elif code == "666":
            cmd_dict = {"command": "hide_all_windows"}
        elif code == "777":
            cmd_dict = {"command": "simulate_error"}
        else:
            messagebox.showerror("错误", "未知命令代码")
            return

        # 写入命令文件
        cmd_file = os.path.join(log_dir, "debug_command.txt")
        try:
            with open(cmd_file, 'w', encoding='utf-8') as f:
                json.dump(cmd_dict, f, ensure_ascii=False, indent=2)
            log(2, f"已发送调试命令: {cmd_dict}")
            messagebox.showinfo("成功", f"调试命令已发送:\n{cmd_dict}")
        except Exception as e:
            log(1, f"发送调试命令失败: {e}")
            messagebox.showerror("错误", f"发送失败: {e}")

    def update_gui(self):
        """从队列获取日志并更新对应文本框"""
        try:
            while True:
                source, line = self.log_queue.get_nowait()
                # 根据过滤等级决定是否显示
                filter_level = self.filter_var.get()
                if filter_level != "全部":
                    if f"[{filter_level}]" not in line:
                        continue
                # 添加到对应文本框
                if source == "主程序":
                    self.main_log_text.insert(tk.END, line + "\n")
                    self.main_log_text.see(tk.END)
                else:
                    self.auto_log_text.insert(tk.END, line + "\n")
                    self.auto_log_text.see(tk.END)
                log(3, f"[{source}] {line}")
        except queue.Empty:
            pass
        finally:
            self.root.after(self.update_interval, self.update_gui)

    def set_debug_level(self):
        """修改监控程序自身的调试等级"""
        global DEBUG_LEVEL
        new_level = self.debug_level_var.get()
        if new_level != DEBUG_LEVEL:
            DEBUG_LEVEL = new_level
            log(2, f"监控程序调试等级已设置为 {DEBUG_LEVEL}")

    def clear_logs(self):
        """清空两个日志文本框"""
        self.main_log_text.delete(1.0, tk.END)
        self.auto_log_text.delete(1.0, tk.END)

    def refresh_process(self):
        """手动刷新进程状态"""
        self.check_processes()

    def show_window(self):
        self.root.deiconify()

    def hide_window(self):
        self.root.withdraw()
        if self.tray_icon:
            self.tray_icon.notify("监控器仍在后台运行", "进程监控")

    def quit_app(self):
        """退出应用程序"""
        # 停止所有日志监控线程
        for lm in self.log_monitors:
            lm.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

# ==================== 启动入口 ====================
if __name__ == "__main__":
    MonitorApp()