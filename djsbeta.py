import tkinter as tk
from tkinter import colorchooser, ttk, messagebox, font, scrolledtext, filedialog, simpledialog
from datetime import datetime, timedelta
import json
import os
import sys
import time
import ctypes
import platform
import random
import calendar
from PIL import Image, ImageTk, ImageOps, ImageEnhance
import webbrowser
import traceback
import subprocess
import inspect
import importlib.util
import threading
import re
import ast
import signal
import hashlib
from enum import IntFlag, auto
import chinese_calendar  # 新增：用于节假日判断

# ---------- 全局调试输出：强制立即刷新 ----------
def debug_print(*args, **kwargs):
    """向stderr打印并立即刷新"""
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()

# ---------- 全局异常钩子 ----------
def global_excepthook(exc_type, exc_value, exc_traceback):
    with open("crash.log", "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    debug_print("全局异常已捕获，详情请查看 crash.log")

sys.excepthook = global_excepthook

debug_print("=== 程序启动 ===")

DEBUG_MODE = 3
CONFIG_LOADED = False
LOG_FILE = ""
STATUS_MONITOR = False

# ---------- 国际化 ----------
LANG_CHINESE = "zh"
LANG_ENGLISH = "en"
CURRENT_LANG = LANG_CHINESE

_lang_data = {}

def tr(key):
    return _lang_data.get(CURRENT_LANG, {}).get(key, key)

# ---------- 日志系统 ----------
def log_message(message, level="INFO", stack_level=1):
    global DEBUG_MODE, LOG_FILE
    level_map = {"ERROR": 1, "WARNING": 1, "INFO": 2, "DEBUG": 3}
    msg_level = level_map.get(level, 2)
    if DEBUG_MODE < msg_level:
        return

    frame = inspect.currentframe().f_back
    while stack_level > 1 and frame:
        frame = frame.f_back
        stack_level -= 1
    if frame:
        func = frame.f_code.co_name
        filename = os.path.basename(frame.f_code.co_filename)
        lineno = frame.f_lineno
        caller = f"{filename}:{lineno} {func}()"
    else:
        caller = "unknown"

    current_dir = os.getcwd()
    data_dir = os.path.join(current_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    if not LOG_FILE:
        LOG_FILE = os.path.join(data_dir, "LOG.txt")
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("=== 倒计时调试日志 ===\n")
                f.write(f"日志创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"系统信息: {platform.platform()} | Python版本: {sys.version}\n")
                f.write(f"当前工作目录: {current_dir}\n")
                f.write(f"数据目录: {data_dir}\n\n")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{level}] [{caller}] {message}\n")
    if DEBUG_MODE >= 3:
        debug_print(f"[{timestamp}] [{level}] [{caller}] {message}")

def hide_console():
    if sys.platform == "win32" and hasattr(sys, 'frozen'):
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            ctypes.windll.user32.ShowWindow(whnd, 0)

def validate_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        year, month, day = map(int, date_str.split('-'))
        if month < 1 or month > 12 or day < 1 or day > calendar.monthrange(year, month)[1]:
            return False
        return True
    except ValueError:
        return False

def validate_time(time_str):
    try:
        if not time_str:
            return True
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False

# ---------- 修改后的 calculate_days：集成 chinese-calendar ----------
def calculate_days(target_date, target_time="00:00"):
    today = datetime.now()
    try:
        if not validate_date(target_date):
            return 0, 0, 0, 0, ""  # 增加返回节假日名称（今日或首个假日）
        if target_time and validate_time(target_time):
            target = datetime.strptime(f"{target_date} {target_time}", "%Y-%m-%d %H:%M")
        else:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        if target < today:
            return 0, 0, 0, 0, ""
        diff = target - today
        total_seconds = diff.total_seconds()
        days = int(total_seconds // (24 * 3600))
        hours = int((total_seconds % (24 * 3600)) // 3600)
        minutes = int((total_seconds % 3600) // 60)
        total_days = (target.date() - today.date()).days
        work_days = 0
        holiday_name = ""

        if total_days > 0:
            for i in range(total_days):
                current_date = today.date() + timedelta(days=i+1)
                if chinese_calendar.is_workday(current_date):
                    work_days += 1
                else:
                    on_holiday, name = chinese_calendar.get_holiday_detail(current_date)
                    if on_holiday and i == 0:
                        holiday_name = name

        return days, hours, minutes, work_days, holiday_name
    except ValueError:
        return 0, 0, 0, 0, ""

# ---------- 权限枚举 ----------
class PluginPermission(IntFlag):
    NONE = 0
    FILE_READ = auto()
    FILE_WRITE = auto()
    NETWORK = auto()
    COMMAND = auto()

# ---------- 主题系统 ----------
class Theme:
    def __init__(self, name="默认主题", is_dark=False,
                 bg_color="#f5f7fa", frame_bg="#ffffff", accent_color="#3498db",
                 text_color="#2c3e50", border_color="#d1d8e0",
                 font_family="微软雅黑", font_size=9,
                 window_round_radius=0,
                 window_brightness=1.0,
                 window_saturation=1.0):
        self.name = name
        self.is_dark = is_dark
        self.bg_color = bg_color
        self.frame_bg = frame_bg
        self.accent_color = accent_color
        self.text_color = text_color
        self.border_color = border_color
        self.font_family = font_family
        self.font_size = font_size
        self.window_round_radius = window_round_radius
        self.window_brightness = window_brightness
        self.window_saturation = window_saturation

    def to_dict(self):
        return {
            "name": self.name,
            "is_dark": self.is_dark,
            "bg_color": self.bg_color,
            "frame_bg": self.frame_bg,
            "accent_color": self.accent_color,
            "text_color": self.text_color,
            "border_color": self.border_color,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "window_round_radius": self.window_round_radius,
            "window_brightness": self.window_brightness,
            "window_saturation": self.window_saturation
        }

    @staticmethod
    def from_dict(data):
        return Theme(
            name=data.get("name", "默认主题"),
            is_dark=data.get("is_dark", False),
            bg_color=data.get("bg_color", "#f5f7fa"),
            frame_bg=data.get("frame_bg", "#ffffff"),
            accent_color=data.get("accent_color", "#3498db"),
            text_color=data.get("text_color", "#2c3e50"),
            border_color=data.get("border_color", "#d1d8e0"),
            font_family=data.get("font_family", "微软雅黑"),
            font_size=data.get("font_size", 9),
            window_round_radius=data.get("window_round_radius", 0),
            window_brightness=data.get("window_brightness", 1.0),
            window_saturation=data.get("window_saturation", 1.0)
        )

BUILTIN_THEMES = {
    "light": Theme("浅色模式", is_dark=False,
                   bg_color="#f5f7fa", frame_bg="#ffffff",
                   accent_color="#3498db", text_color="#2c3e50",
                   border_color="#d1d8e0", font_family="微软雅黑",
                   window_round_radius=0),
    "dark": Theme("深色模式", is_dark=True,
                  bg_color="#2c3e50", frame_bg="#34495e",
                  accent_color="#e67e22", text_color="#ecf0f1",
                  border_color="#7f8c8d", font_family="微软雅黑",
                  window_round_radius=0),
    "system_native": Theme("系统原生", is_dark=False,
                          bg_color="SystemWindow", frame_bg="SystemButtonFace",
                          accent_color="SystemHighlight", text_color="SystemWindowText",
                          border_color="SystemWindowFrame", font_family="TkDefaultFont",
                          window_round_radius=0)
}

# ---------- 审计条目 ----------
class AuditEntry:
    def __init__(self, plugin_name, operation, allowed, timestamp=None):
        self.plugin_name = plugin_name
        self.operation = operation
        self.allowed = allowed
        self.timestamp = timestamp or datetime.now()

    def to_dict(self):
        return {
            "plugin": self.plugin_name,
            "operation": self.operation,
            "allowed": self.allowed,
            "time": self.timestamp.isoformat()
        }

# ---------- 安全插件 API ----------
class PluginAPI:
    def __init__(self, app, plugin):
        self.app = app
        self.plugin = plugin

    def log(self, message, level="INFO"):
        self.plugin.log_plugin(message, level)

    def get_config(self, key=None):
        if key is None:
            return {
                "poem_level": self.app.poem_level,
                "global_font": self.app.global_font,
                "projects_count": len(self.app.projects)
            }
        return None

    def get_project(self, index):
        if 0 <= index < len(self.app.projects):
            proj = self.app.projects[index]
            return {
                "name": proj.name,
                "target_date": proj.target_date,
                "target_time": proj.target_time,
                "show_both": proj.show_both,
                "font_size": proj.font_size,
                "bg_color": proj.bg_color,
                "font_color": proj.font_color,
                "window_alpha": proj.window_alpha
            }
        return None

    def open_file(self, path, mode='r'):
        perm = PluginPermission.FILE_READ if 'r' in mode else PluginPermission.FILE_WRITE
        self.plugin.check_permission(perm, f"打开文件 {path} 模式 {mode}")
        return open(path, mode)

    def read_file(self, path):
        self.plugin.check_permission(PluginPermission.FILE_READ, f"读取文件 {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, path, content):
        self.plugin.check_permission(PluginPermission.FILE_WRITE, f"写入文件 {path}")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def socket_connect(self, host, port):
        self.plugin.check_permission(PluginPermission.NETWORK, f"连接 {host}:{port}")
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        return s

    def run_command(self, cmd):
        self.plugin.check_permission(PluginPermission.COMMAND, f"执行命令 {cmd}")
        import subprocess
        return subprocess.run(cmd, capture_output=True, text=True)

# ---------- 插件基类 ----------
class Plugin:
    def __init__(self, app):
        self.app = app
        self.api = PluginAPI(app, self)
        self.name = "Unnamed Plugin"
        self.version = "0.1"
        self.author = "Unknown"
        self.enabled = False
        self.log = []
        self.filename = None
        self._risk_level = 0
        self.limited = False
        self.permissions = PluginPermission.NONE
        self.requested_permissions = PluginPermission.NONE
        self.audit_log = []
        self.emergency_stop = False

    @property
    def risk_level(self):
        return self._risk_level

    @risk_level.setter
    def risk_level(self, value):
        self.api.log("试图修改风险等级，此操作无效", "WARNING")

    def on_load(self): pass
    def on_enable(self): pass
    def on_disable(self): pass
    def on_settings_open(self, parent): pass
    def on_window_create(self, window, project): pass
    def on_tick(self): pass
    def on_before_save_config(self): pass
    def on_after_save_config(self): pass
    def on_window_closed(self, window, project): pass
    def on_settings_closed(self): pass
    def on_poem_update(self, new_poem): pass
    def on_language_change(self, old_lang, new_lang): pass

    def log_plugin(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.append(f"[{timestamp}] [{level}] {message}")
        log_message(f"[Plugin:{self.name}] {message}", level, stack_level=2)

    def _apply_restrictions(self):
        if not self.limited:
            return
        module_name = self.__module__
        module = sys.modules.get(module_name)
        if not module:
            self.api.log("无法获取插件模块，限制可能无效", "WARNING")
            return
        if not hasattr(module, '_original_builtins'):
            module._original_builtins = module.__builtins__
        original_builtins = module.__builtins__
        if isinstance(original_builtins, dict):
            restricted_builtins = original_builtins.copy()
        else:
            restricted_builtins = {}
            for name in dir(original_builtins):
                if not name.startswith('__') or name in ('__build_class__', '__name__', '__doc__'):
                    try:
                        restricted_builtins[name] = getattr(original_builtins, name)
                    except AttributeError:
                        pass

        def restricted_open(*args, **kwargs):
            raise PermissionError("插件在限制模式下禁止文件操作")
        def restricted_eval(*args, **kwargs):
            raise PermissionError("插件在限制模式下禁止动态执行代码")
        def restricted_exec(*args, **kwargs):
            raise PermissionError("插件在限制模式下禁止动态执行代码")
        def restricted___import__(*args, **kwargs):
            name = args[0] if args else kwargs.get('name', '')
            if name in ('os', 'socket', 'subprocess', 'ctypes', 'requests', 'urllib',
                        'pickle', 'marshal', 'base64', 'ftplib', 'telnetlib', 'ssl'):
                raise PermissionError(f"插件在限制模式下禁止导入模块: {name}")
            if isinstance(original_builtins, dict):
                return original_builtins.get('__import__', __builtins__.__import__)(*args, **kwargs)
            else:
                return original_builtins.__import__(*args, **kwargs)

        restricted_builtins['open'] = restricted_open
        restricted_builtins['eval'] = restricted_eval
        restricted_builtins['exec'] = restricted_exec
        restricted_builtins['__import__'] = restricted___import__
        module.__builtins__ = restricted_builtins

        if 'os' in module.__dict__:
            module._original_os = module.os
            class RestrictedModule:
                def __getattr__(self, name):
                    raise PermissionError(f"插件在限制模式下禁止访问该模块")
            module.os = RestrictedModule()
        if 'socket' in module.__dict__:
            module._original_socket = module.socket
            module.socket = RestrictedModule()
        if 'subprocess' in module.__dict__:
            module._original_subprocess = module.subprocess
            module.subprocess = RestrictedModule()
        self.api.log("已应用限制模式：文件、网络、系统命令被禁止", "WARNING")

    def _remove_restrictions(self):
        module_name = self.__module__
        module = sys.modules.get(module_name)
        if not module:
            return
        if hasattr(module, '_original_builtins'):
            module.__builtins__ = module._original_builtins
            delattr(module, '_original_builtins')
        if hasattr(module, '_original_os'):
            if module._original_os is not None:
                module.os = module._original_os
            delattr(module, '_original_os')
        if hasattr(module, '_original_socket'):
            if module._original_socket is not None:
                module.socket = module._original_socket
            delattr(module, '_original_socket')
        if hasattr(module, '_original_subprocess'):
            if module._original_subprocess is not None:
                module.subprocess = module._original_subprocess
            delattr(module, '_original_subprocess')
        self.api.log("已移除限制模式", "WARNING")

    def check_permission(self, perm, operation_desc):
        if self.emergency_stop:
            raise RuntimeError("插件已被紧急停止")
        if perm in self.permissions:
            self._audit(operation_desc, allowed=True)
            return True
        else:
            if self.app.plugin_prompt_on_deny:
                allowed = self.app.ask_permission(self, perm, operation_desc)
                if allowed:
                    self.permissions |= perm
                    self._audit(operation_desc, allowed=True)
                    return True
            self._audit(operation_desc, allowed=False)
            raise PermissionError(f"插件缺少必要权限: {operation_desc}")

    def _audit(self, operation, allowed):
        entry = AuditEntry(self.name, operation, allowed)
        self.audit_log.append(entry)
        if len(self.audit_log) > 100:
            self.audit_log.pop(0)
        self.api.log(f"审计: {operation} -> {'允许' if allowed else '拒绝'}", "DEBUG")

# ---------- 静态代码分析器 ----------
class PluginAnalyzer:
    DANGEROUS_IMPORTS = {
        'os', 'subprocess', 'socket', 'ctypes', 'requests', 'urllib',
        'pickle', 'marshal', 'base64', 'ftplib', 'telnetlib', 'ssl'
    }
    DANGEROUS_CALLS = {
        'eval', 'exec', 'compile', 'globals', 'locals', '__import__',
        'open', 'file', 'input', 'raw_input'
    }

    @classmethod
    def analyze(cls, source_code):
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return 2, ["语法错误，无法解析"]
        risk = 0
        messages = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in cls.DANGEROUS_IMPORTS:
                        risk = max(risk, 2)
                        messages.append(f"禁止导入模块: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module.split('.')[0] if node.module else ''
                if module in cls.DANGEROUS_IMPORTS:
                    risk = max(risk, 2)
                    messages.append(f"禁止导入模块: {node.module}")
                else:
                    for alias in node.names:
                        if alias.name in cls.DANGEROUS_CALLS:
                            risk = max(risk, 2)
                            messages.append(f"禁止导入函数: {alias.name}")
            if isinstance(node, ast.Call) and hasattr(node.func, 'id'):
                if node.func.id in cls.DANGEROUS_CALLS:
                    risk = max(risk, 2)
                    messages.append(f"禁止调用函数: {node.func.id}()")
            elif isinstance(node, ast.Call) and hasattr(node.func, 'attr'):
                if hasattr(node.func, 'value') and hasattr(node.func.value, 'id'):
                    if node.func.value.id in ['os', 'subprocess', 'sys']:
                        risk = max(risk, 2)
                        messages.append(f"禁止调用 {node.func.value.id}.{node.func.attr}()")
            if isinstance(node, ast.Attribute):
                if node.attr in ['system', 'popen', 'call', 'run'] and hasattr(node.value, 'id'):
                    if node.value.id in ['os', 'subprocess']:
                        risk = max(risk, 2)
                        messages.append(f"禁止访问 {node.value.id}.{node.attr}")
        return risk, messages

# ---------- 插件管理器 ----------
class PluginManager:
    def __init__(self, app, load_immediately=True):
        self.app = app
        self.plugins = []
        self.plugin_dir = os.path.join(os.getcwd(), "plugins")
        os.makedirs(self.plugin_dir, exist_ok=True)
        self.plugin_security = {}
        self._plugin_risk = {}
        self.load_security_config()
        if load_immediately:
            self.load_plugins()

    def load_security_config(self):
        config_path = os.path.join(self.app.data_dir, "plugin_security.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.plugin_security = json.load(f)
            except:
                self.plugin_security = {}

    def save_security_config(self):
        config_path = os.path.join(self.app.data_dir, "plugin_security.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.plugin_security, f, indent=2)

    def compute_plugin_hash(self, filepath):
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def load_plugins(self):
        log_message("开始加载插件...", "INFO")
        sys.path.insert(0, self.plugin_dir)
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                filepath = os.path.join(self.plugin_dir, filename)
                plugin_hash = self.compute_plugin_hash(filepath)
                sec_info = self.plugin_security.get(filename, {})
                if sec_info.get('blacklisted', False):
                    log_message(f"插件 {filename} 已被列入黑名单，跳过加载", "WARNING")
                    continue
                saved_hash = sec_info.get('hash')
                if saved_hash and saved_hash != plugin_hash:
                    log_message(f"插件 {filename} 文件已改变，可能被篡改！", "WARNING")
                sec_info['hash'] = plugin_hash
                self.plugin_security[filename] = sec_info
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        source = f.read()
                except:
                    log_message(f"无法读取插件文件: {filename}", "ERROR")
                    continue
                risk, msgs = PluginAnalyzer.analyze(source)
                if risk > 0:
                    log_message(f"插件 {filename} 存在风险: {msgs}", "WARNING")
                try:
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    module = importlib.util.module_from_spec(spec)
                    module.__dict__['Plugin'] = Plugin
                    spec.loader.exec_module(module)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                            plugin_instance = attr(self.app)
                            plugin_instance.name = getattr(module, "__plugin_name__", plugin_instance.name)
                            plugin_instance.version = getattr(module, "__version__", plugin_instance.version)
                            plugin_instance.author = getattr(module, "__author__", plugin_instance.author)
                            plugin_instance.filename = filename
                            plugin_instance._risk_level = risk
                            self._plugin_risk[plugin_instance] = risk
                            plugin_instance.permissions = PluginPermission(sec_info.get('permissions', 0))
                            self.plugins.append(plugin_instance)
                            plugin_instance.on_load()
                            risk_msg = f"风险等级: {risk}" if risk > 0 else "安全"
                            log_message(f"插件加载成功: {plugin_instance.name} v{plugin_instance.version} [{risk_msg}]", "INFO")
                            break
                except Exception as e:
                    log_message(f"加载插件 {filename} 失败: {e}\n{traceback.format_exc()}", "ERROR")
        sys.path.pop(0)
        self.save_security_config()
        log_message(f"插件加载完成，共 {len(self.plugins)} 个", "INFO")

    def get_plugin_risk(self, plugin):
        return self._plugin_risk.get(plugin, 0)

    def enable_plugin(self, plugin, limited=None, force=False):
        try:
            risk = self.get_plugin_risk(plugin)
            if risk >= 2 and not force:
                log_message(f"尝试启用高风险插件 {plugin.name} 被拒绝（需用户确认）", "WARNING")
                return False
            if not plugin.enabled:
                if limited is None:
                    limited = (risk >= 2)
                plugin.limited = limited
                if limited:
                    plugin._apply_restrictions()
                plugin.on_enable()
                plugin.enabled = True
                log_message(f"插件已启用: {plugin.name} (限制模式: {limited})", "INFO")
                self._save_plugin_state(plugin.filename, True, limited)
                return True
            return False
        except Exception as e:
            log_message(f"启用插件 {plugin.name} 失败: {e}", "ERROR")
            return False

    def disable_plugin(self, plugin):
        try:
            if plugin.enabled:
                if plugin.limited:
                    plugin._remove_restrictions()
                plugin.on_disable()
                plugin.enabled = False
                plugin.limited = False
                log_message(f"插件已禁用: {plugin.name}", "INFO")
                self._save_plugin_state(plugin.filename, False, False)
                return True
            return False
        except Exception as e:
            log_message(f"禁用插件 {plugin.name} 失败: {e}", "ERROR")
            return False

    def set_plugin_limited(self, plugin, limited):
        if not plugin.enabled:
            return False
        if plugin.limited == limited:
            return True
        if limited:
            plugin._apply_restrictions()
        else:
            plugin._remove_restrictions()
        plugin.limited = limited
        self._save_plugin_state(plugin.filename, True, limited)
        log_message(f"插件 {plugin.name} 限制模式已切换为 {limited}", "INFO")
        return True

    def _save_plugin_state(self, filename, enabled, limited=False):
        config_path = os.path.join(self.app.data_dir, "countdown_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except:
                config = {}
        else:
            config = {}
        plugin_states = config.get("plugin_states", {})
        plugin_states[filename] = {"enabled": enabled, "limited": limited}
        config["plugin_states"] = plugin_states
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    def set_plugin_permissions(self, plugin, permissions):
        plugin.permissions = permissions
        sec_info = self.plugin_security.get(plugin.filename, {})
        sec_info['permissions'] = permissions.value
        self.plugin_security[plugin.filename] = sec_info
        self.save_security_config()

    def blacklist_plugin(self, plugin, blacklisted=True):
        sec_info = self.plugin_security.get(plugin.filename, {})
        sec_info['blacklisted'] = blacklisted
        self.plugin_security[plugin.filename] = sec_info
        self.save_security_config()
        if blacklisted and plugin.enabled:
            self.disable_plugin(plugin)

    def emergency_stop_plugin(self, plugin):
        plugin.emergency_stop = True
        log_message(f"插件 {plugin.name} 已被紧急停止", "WARNING")

    def get_enabled_plugins(self):
        return [p for p in self.plugins if p.enabled]

    def _call_with_timeout(self, func, args=(), kwargs={}, timeout=5, on_error=None):
        result = [None]
        exception = [None]
        finished = threading.Event()
        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e
            finally:
                finished.set()
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        if not finished.wait(timeout):
            log_message(f"插件函数 {func.__name__} 执行超时 ({timeout}s)", "WARNING")
            if on_error:
                self.app.after(0, on_error, TimeoutError(f"执行超时 ({timeout}s)"))
            return None
        if exception[0]:
            if on_error:
                self.app.after(0, on_error, exception[0])
            raise exception[0]
        return result[0]

    def trigger_event(self, event_name, *args, **kwargs):
        for plugin in self.get_enabled_plugins():
            risk = self.get_plugin_risk(plugin)
            if hasattr(plugin, event_name):
                try:
                    method = getattr(plugin, event_name)
                    if risk >= 2:
                        if self.app.plugin_monitor:
                            def on_error(exc):
                                error_info = traceback.format_exc() if hasattr(exc, '__traceback__') else str(exc)
                                plugin.log_plugin(f"监控到异常: {exc}", "ERROR")
                                self.app.ask_disable_plugin(plugin, error_info)
                            self._call_with_timeout(method, args, kwargs, timeout=3, on_error=on_error)
                        else:
                            self._call_with_timeout(method, args, kwargs, timeout=3)
                    else:
                        if self.app.plugin_monitor and risk >= 1:
                            try:
                                method(*args, **kwargs)
                            except Exception as e:
                                error_info = traceback.format_exc()
                                plugin.log_plugin(f"监控到异常: {e}", "ERROR")
                                self.app.after(0, lambda p=plugin, err=error_info: self.app.ask_disable_plugin(p, err))
                        else:
                            method(*args, **kwargs)
                except Exception as e:
                    plugin.log_plugin(f"事件 {event_name} 处理出错: {e}", "ERROR")
                    log_message(f"插件 {plugin.name} 事件 {event_name} 出错: {e}", "ERROR")

def create_plugin_example():
    plugin_dir = os.path.join(os.getcwd(), "plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    example_path = os.path.join(plugin_dir, "example_plugin.py")
    correct_content = '''# 示例插件 - 展示插件系统所有可用功能（使用安全API）
# 将此文件放入 plugins 文件夹即可加载

__plugin_name__ = "全能示例插件"
__version__ = "2.0"
__author__ = "系统"

import tkinter as tk
from tkinter import messagebox, scrolledtext
import os

class ExamplePlugin(Plugin):
    def on_load(self):
        self.api.log("插件已加载", "INFO")
        try:
            content = self.api.read_file(os.path.join("data", "test.txt"))
            self.api.log(f"读取文件成功: {content[:50]}", "INFO")
        except PermissionError:
            self.api.log("无读取文件权限，将在需要时请求", "WARNING")
        except FileNotFoundError:
            self.api.log("test.txt 不存在，稍后创建", "INFO")

    def on_enable(self):
        self.api.log("插件已启用", "INFO")
        try:
            with self.api.open_file(os.path.join("data", "plugin_example.log"), "a") as f:
                f.write(f"{self.api.app.now()} 插件启用\\n")
        except PermissionError:
            self.api.log("无法写入日志文件，权限不足", "WARNING")

    def on_disable(self):
        self.api.log("插件已禁用", "INFO")

    def on_settings_open(self, parent):
        frame = tk.Frame(parent, bg="#f0f0f0")
        tk.Label(frame, text="全能示例插件设置", font=("微软雅黑", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        config = self.api.get_config()
        info = f"诗词等级: {config['poem_level']}, 项目数: {config['projects_count']}"
        tk.Label(frame, text=info, bg="#f0f0f0").pack(pady=2)
        def test_write():
            try:
                self.api.write_file(os.path.join("data", "plugin_test.txt"), "插件测试写入成功！")
                messagebox.showinfo("插件测试", "文件写入成功！")
            except PermissionError as e:
                messagebox.showerror("权限不足", str(e))
        tk.Button(frame, text="测试写入文件", command=test_write, bg="#3498db", fg="white").pack(pady=5)
        def test_read():
            try:
                content = self.api.read_file(os.path.join("data", "plugin_test.txt"))
                messagebox.showinfo("插件测试", f"文件内容：\\n{content}")
            except PermissionError as e:
                messagebox.showerror("权限不足", str(e))
            except FileNotFoundError:
                messagebox.showerror("文件不存在", "请先写入文件")
        tk.Button(frame, text="测试读取文件", command=test_read, bg="#3498db", fg="white").pack(pady=5)
        def show_log():
            log_win = tk.Toplevel(frame)
            log_win.title("插件日志")
            log_win.geometry("500x300")
            text = scrolledtext.ScrolledText(log_win, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True)
            for line in self.log[-100:]:
                text.insert(tk.END, line + "\\n")
            text.config(state=tk.DISABLED)
        tk.Button(frame, text="查看插件日志", command=show_log, bg="#2ecc71", fg="white").pack(pady=5)
        return frame

    def on_window_create(self, window, project):
        self.api.log(f"窗口创建: {project.name} (ID: {id(window)})", "DEBUG")
        try:
            window.canvas.create_text(10, 10, text="★", fill="yellow", font=("Arial", 64), anchor="nw", tags="plugin_mark")
        except Exception as e:
            self.api.log(f"添加标记失败: {e}", "ERROR")

    def on_window_closed(self, window, project):
        self.api.log(f"窗口关闭: {project.name}", "DEBUG")

    def on_tick(self):
        self.api.log("定时任务执行", "DEBUG")
        try:
            with self.api.open_file(os.path.join("data", "plugin_tick.log"), "a") as f:
                f.write(f"tick at {self.api.app.now()}\\n")
        except PermissionError:
            pass

    def on_before_save_config(self):
        self.api.log("配置即将保存", "DEBUG")

    def on_after_save_config(self):
        self.api.log("配置已保存", "DEBUG")

    def on_settings_closed(self):
        self.api.log("设置窗口已关闭", "DEBUG")

    def on_poem_update(self, new_poem):
        self.api.log(f"每日一诗更新: {new_poem}", "DEBUG")
        try:
            self.api.write_file(os.path.join("data", "last_poem.txt"), new_poem)
        except PermissionError:
            pass

    def on_language_change(self, old_lang, new_lang):
        self.api.log(f"语言从 {old_lang} 变更为 {new_lang}", "DEBUG")
'''
    if not os.path.exists(example_path):
        with open(example_path, "w", encoding="utf-8") as f:
            f.write(correct_content)
        log_message(f"已创建示例插件文件: {example_path}", "INFO")
        return
    try:
        with open(example_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "from plugins_system import Plugin" in content:
            with open(example_path, "w", encoding="utf-8") as f:
                f.write(correct_content)
            log_message(f"示例插件文件内容错误，已自动修复: {example_path}", "WARNING")
        else:
            log_message(f"示例插件文件已存在且内容正确，跳过", "DEBUG")
    except Exception as e:
        log_message(f"检查示例插件文件时出错: {e}", "ERROR")

# ---------- CountdownProject ----------
class CountdownProject:
    def __init__(self, name="新项目", target_date="", target_time="00:00", show_both=True, font_size=14,
                 bg_color="#3498db", font_color="#FFFFFF", position=None, size=None,
                 screen_width=1920, screen_height=1080, always_on_top=True, auto_font=False,
                 background_type="color", background_image="", window_alpha=0.85,
                 project_type="normal", pomodoro_work=25, pomodoro_break=5, pomodoro_long_break=15, pomodoro_cycles=4,
                 custom_layout=None):
        self.project_type = project_type
        self.pomodoro_work = pomodoro_work
        self.pomodoro_break = pomodoro_break
        self.pomodoro_long_break = pomodoro_long_break
        self.pomodoro_cycles = pomodoro_cycles
        self.custom_layout = custom_layout or {}

        self.name = name
        self.target_date = target_date or (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        self.target_time = target_time or "00:00"
        self.show_both = show_both
        self.font_size = font_size
        self.bg_color = bg_color
        self.font_color = font_color
        self.position = position or (100, 100)
        self.size = size or self.get_default_size(screen_width, screen_height)
        self.always_on_top = always_on_top
        self.auto_font = auto_font
        self.background_type = background_type
        self.background_image = background_image
        self.window_alpha = window_alpha
        log_message(f"创建项目: {name} | 目标日期: {target_date} {target_time} | 背景类型: {background_type} | 类型: {project_type}", "DEBUG")

    def get_default_size(self, screen_width, screen_height):
        width = max(400, min(600, screen_width // 3))
        height = max(300, min(300, screen_height // 2))
        return (width, height)

    def to_dict(self):
        return {
            "name": self.name,
            "target_date": self.target_date,
            "target_time": self.target_time,
            "show_both": self.show_both,
            "font_size": self.font_size,
            "bg_color": self.bg_color,
            "font_color": self.font_color,
            "position": self.position,
            "size": self.size,
            "always_on_top": self.always_on_top,
            "auto_font": self.auto_font,
            "background_type": self.background_type,
            "background_image": self.background_image,
            "window_alpha": self.window_alpha,
            "project_type": self.project_type,
            "pomodoro_work": self.pomodoro_work,
            "pomodoro_break": self.pomodoro_break,
            "pomodoro_long_break": self.pomodoro_long_break,
            "pomodoro_cycles": self.pomodoro_cycles,
            "custom_layout": self.custom_layout
        }

    @staticmethod
    def from_dict(data, screen_width=1920, screen_height=1080):
        return CountdownProject(
            data.get("name", "新项目"),
            data.get("target_date", (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")),
            data.get("target_time", "00:00"),
            data.get("show_both", True),
            data.get("font_size", 14),
            data.get("bg_color", "#3498db"),
            data.get("font_color", "#FFFFFF"),
            data.get("position", (100, 100)),
            data.get("size", None),
            screen_width,
            screen_height,
            data.get("always_on_top", True),
            data.get("auto_font", False),
            data.get("background_type", "color"),
            data.get("background_image", ""),
            data.get("window_alpha", 0.85),
            data.get("project_type", "normal"),
            data.get("pomodoro_work", 25),
            data.get("pomodoro_break", 5),
            data.get("pomodoro_long_break", 15),
            data.get("pomodoro_cycles", 4),
            data.get("custom_layout", {})
        )

# ---------- CountdownWindow ----------
class CountdownWindow(tk.Toplevel):
    def __init__(self, master, project, index):
        debug_print(f"【DEBUG】CountdownWindow({index}) 初始化开始")
        super().__init__(master)
        debug_print(f"【DEBUG】CountdownWindow({index}) super 完成")
        self.project = project
        self.index = index
        self.master = master
        log_message(f"创建窗口: {project.name} | 索引: {index} | 位置: {project.position} | 尺寸: {project.size}", "INFO")
        debug_print(f"【DEBUG】CountdownWindow({index}) 属性赋值完成")

        self.title(f"{tr('app_title')}: {project.name}")
        self.overrideredirect(True)
        self.attributes("-topmost", project.always_on_top)

        x, y = project.position
        width, height = project.size
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        debug_print(f"【DEBUG】CountdownWindow({index}) 屏幕尺寸: {screen_width}x{screen_height}, 初始位置: {x},{y} 尺寸: {width}x{height}")
        x = max(0, min(x, screen_width - width))
        y = max(0, min(y, screen_height - height))
        self.geometry(f"{width}x{height}+{x}+{y}")
        debug_print(f"【DEBUG】CountdownWindow({index}) geometry 设置完成，实际位置: {x},{y}")
        self.minsize(250, 150)
        self.attributes("-alpha", project.window_alpha)

        self.canvas = tk.Canvas(
            self,
            bg=project.bg_color if project.background_type == "color" else "black",
            highlightthickness=0,
            borderwidth=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        debug_print(f"【DEBUG】CountdownWindow({index}) canvas 创建完成")

        self.bg_image = None
        self.bg_photo = None
        self.bg_image_id = None
        self.project_text_id = None
        self.countdown_text_id = None
        self.poem_text_id = None
        self.drag_hint_id = None

        # 动画变量
        self.animation_running = False
        self.old_countdown_text_id = None
        self.old_poem_text_id = None

        # 全屏变量
        self.is_fullscreen = False
        self.fullscreen_controls = None
        self.old_geometry = None
        self.old_attributes = {}

        # 创建文本元素
        debug_print(f"【DEBUG】CountdownWindow({index}) 准备创建文本元素")
        self.create_text_elements()
        debug_print(f"【DEBUG】CountdownWindow({index}) 文本元素创建完成")
        # 应用自定义布局
        self.apply_custom_layout()

        if self.project.background_type == "image" and self.project.background_image:
            self.load_background_image()
        else:
            self.draw_background()
        self.draw_drag_hint()

        self.drag_data = {"x": 0, "y": 0, "dragging": False}
        self.resize_data = {"resizing": False, "edge": None, "start_x": 0, "start_y": 0, "width": 0, "height": 0}

        self.canvas.bind("<ButtonPress-1>", self.start_drag_or_resize)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag_or_resize)
        self.canvas.bind("<B1-Motion>", self.on_drag_or_resize)
        self.canvas.bind("<Motion>", self.on_motion)

        self.menu = tk.Menu(self, tearoff=0, bg="#f0f0f0", fg="#333333",
                            activebackground="#3498db", activeforeground="#ffffff")
        self.menu.add_command(label=tr("settings_title"), command=self.open_settings_from_window)
        self.menu.add_command(label="取消置顶" if CURRENT_LANG == LANG_CHINESE else "Unpin", command=self.unset_topmost)
        self.menu.add_command(label="置顶窗口" if CURRENT_LANG == LANG_CHINESE else "Pin", command=self.set_topmost)
        self.menu.add_command(label="全屏" if CURRENT_LANG == LANG_CHINESE else "Fullscreen", command=self.toggle_fullscreen)
        self.menu.add_command(label=tr("close"), command=self.close_window)
        self.menu.add_command(label="退出应用" if CURRENT_LANG == LANG_CHINESE else "Quit", command=self.master.quit_app)
        self.canvas.bind("<Button-3>", self.show_menu)

        self.bind("<Configure>", self.on_configure)
        debug_print(f"【DEBUG】CountdownWindow({index}) 准备第一次更新倒计时")
        self.update_countdown()
        self.schedule_update()

        self.save_timer = None
        self.bg_image_timer = None
        if self.project.background_type == "image" and self.project.background_image:
            self.after(100, self.load_background_image)

        self.master.plugin_manager.trigger_event("on_window_create", self, project)
        self.apply_round_corners()
        debug_print(f"【DEBUG】CountdownWindow({index}) 初始化完成")

    # ---------- 应用自定义布局 ----------
    def apply_custom_layout(self):
        layout = self.project.custom_layout
        if not layout:
            return
        if "name" in layout:
            cfg = layout["name"]
            self.canvas.coords(self.project_text_id, cfg.get("x", self.winfo_width()/2), cfg.get("y", self.winfo_height()*0.15))
            if "font_size" in cfg:
                self.canvas.itemconfig(self.project_text_id, font=(self.master.global_font, cfg["font_size"], "bold"))
            if "color" in cfg:
                self.canvas.itemconfig(self.project_text_id, fill=cfg["color"])
        if "countdown" in layout:
            cfg = layout["countdown"]
            self.canvas.coords(self.countdown_text_id, cfg.get("x", self.winfo_width()/2), cfg.get("y", self.winfo_height()*0.5))
            if "font_size" in cfg:
                self.canvas.itemconfig(self.countdown_text_id, font=(self.master.global_font, cfg["font_size"], "bold"))
            if "color" in cfg:
                self.canvas.itemconfig(self.countdown_text_id, fill=cfg["color"])
        if "poem" in layout:
            cfg = layout["poem"]
            self.canvas.coords(self.poem_text_id, cfg.get("x", self.winfo_width()/2), cfg.get("y", self.winfo_height()*0.8))
            if "font_size" in cfg:
                self.canvas.itemconfig(self.poem_text_id, font=(self.master.global_font, cfg["font_size"]))
            if "color" in cfg:
                self.canvas.itemconfig(self.poem_text_id, fill=cfg["color"])

    # ---------- 动画方法 ----------
    def animate_text_change(self, new_text, element_type="countdown"):
        if element_type == "countdown":
            old_id = self.countdown_text_id
            old_text = self.canvas.itemcget(old_id, "text")
            if old_text == new_text:
                return
            x, y = self.canvas.coords(old_id)
            old_clone = self.canvas.create_text(x, y, text=old_text,
                                                font=self.canvas.itemcget(old_id, "font"),
                                                fill=self.canvas.itemcget(old_id, "fill"),
                                                anchor="center", tags="temp")
            new_clone = self.canvas.create_text(x, y-10, text=new_text,
                                                font=self.canvas.itemcget(old_id, "font"),
                                                fill=self.canvas.itemcget(old_id, "fill"),
                                                anchor="center", tags="temp")
            self.canvas.itemconfig(old_id, state="hidden")

            steps = 10
            delay = 30
            for i in range(steps+1):
                self.after(i*delay, lambda c1=old_clone, c2=new_clone: self._update_animation(c1, c2))

            self.after((steps+1)*delay, lambda: self._finish_animation(old_id, new_text, old_clone, new_clone))

    def _update_animation(self, old_clone, new_clone):
        if old_clone and self.canvas.winfo_exists():
            self.canvas.move(old_clone, 0, -1)
        if new_clone and self.canvas.winfo_exists():
            self.canvas.move(new_clone, 0, 1)

    def _finish_animation(self, old_id, new_text, old_clone, new_clone):
        if self.canvas.winfo_exists():
            self.canvas.delete(old_clone)
            self.canvas.delete(new_clone)
            self.canvas.itemconfig(old_id, state="normal", text=new_text)

    def update_countdown(self):
        try:
            # 现在 calculate_days 返回 5 个值，需要全部接收
            days, hours, minutes, work_days, holiday_name = calculate_days(self.project.target_date,
                                                                           self.project.target_time)
            if days == 0 and hours == 0 and minutes == 0:
                if self.project.target_time != "00:00":
                    text = f"{tr('time_arrived')}\n{self.project.name}"
                else:
                    text = f"{tr('date_arrived')}\n{self.project.name}"
            elif days == 0 and self.project.target_time != "00:00":
                text = f"{tr('days_left').format(name=self.project.name)}\n{tr('hours_minutes_format').format(hours=hours, minutes=minutes)}"
            elif self.project.show_both:
                if self.project.target_time != "00:00":
                    # 如果需要显示节假日名称，可以追加到文本中
                    holiday_text = f"\n🎉 {holiday_name}" if holiday_name else ""
                    text = (f"{tr('days_left').format(name=self.project.name)}\n"
                            f"{tr('days_format').format(days=days)}{tr('hours_minutes_format').format(hours=hours, minutes=minutes)}\n"
                            f"{tr('workdays_format').format(work_days=work_days)}{holiday_text}")
                else:
                    holiday_text = f"\n🎉 {holiday_name}" if holiday_name else ""
                    text = (f"{tr('days_left').format(name=self.project.name)}\n"
                            f"{tr('days_format').format(days=days)}\n"
                            f"{tr('workdays_format').format(work_days=work_days)}{holiday_text}")
            else:
                if self.project.target_time != "00:00":
                    text = f"{tr('days_left').format(name=self.project.name)}\n{tr('days_format').format(days=days)}{tr('hours_minutes_format').format(hours=hours, minutes=minutes)}"
                else:
                    text = f"{tr('days_left').format(name=self.project.name)}\n{tr('days_format').format(days=days)}"

            old_text = self.canvas.itemcget(self.countdown_text_id, "text")
            if old_text != text:
                self.animate_text_change(text, "countdown")
            else:
                self.canvas.itemconfig(self.countdown_text_id, text=text)
            self.canvas.itemconfig(self.project_text_id, text=self.project.name)
            if self.project.auto_font:
                self.adjust_font_size()
            log_message(f"窗口 {self.project.name} 更新倒计时: {text}", "DEBUG")
        except Exception as e:
            log_message(f"更新倒计时错误: {e} | {traceback.format_exc()}", "ERROR")
    # ---------- 全屏模式 ----------
    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            self.old_geometry = self.geometry()
            self.old_attributes["topmost"] = self.attributes("-topmost")
            self.attributes("-topmost", True)
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            self.geometry(f"{screen_width}x{screen_height}+0+0")
            for win in self.master.windows:
                if win != self:
                    win.attributes("-topmost", False)
            self.show_fullscreen_controls()
            self.is_fullscreen = True
            # 进入全屏后立即刷新背景（避免延迟）
            self.after(10, self._force_background_refresh)
        else:
            self.attributes("-topmost", self.old_attributes.get("topmost", True))
            self.geometry(self.old_geometry)
            self.hide_fullscreen_controls()
            self.is_fullscreen = False
            self.after(10, self._force_background_refresh)

    def _force_background_refresh(self):
        """强制立即刷新背景，解决全屏切换时背景残留问题"""
        if self.project.background_type == "color":
            self.draw_background()
        elif self.project.background_type == "image" and self.project.background_image:
            # 取消所有延迟任务，立即更新
            if hasattr(self, 'bg_image_timer') and self.bg_image_timer:
                self.after_cancel(self.bg_image_timer)
                self.bg_image_timer = None
            self.update_background_image()

    def show_fullscreen_controls(self):
        if self.fullscreen_controls:
            return
        frame = tk.Frame(self, bg="#333333", bd=1, relief=tk.SOLID)
        frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        alpha_label = tk.Label(frame, text="透明度", bg="#333333", fg="white", font=("微软雅黑", 8))
        alpha_label.pack(side=tk.LEFT, padx=2)
        alpha_scale = tk.Scale(frame, from_=0.3, to=1.0, orient=tk.HORIZONTAL, length=100,
                               command=self.set_alpha, bg="#333333", fg="white", highlightthickness=0)
        alpha_scale.set(self.project.window_alpha)
        alpha_scale.pack(side=tk.LEFT, padx=2)
        close_btn = tk.Button(frame, text="关闭全屏", command=self.toggle_fullscreen, bg="#e74c3c", fg="white", bd=0, padx=5)
        close_btn.pack(side=tk.LEFT, padx=2)
        self.fullscreen_controls = frame

    def hide_fullscreen_controls(self):
        if self.fullscreen_controls:
            self.fullscreen_controls.destroy()
            self.fullscreen_controls = None

    def set_alpha(self, val):
        self.attributes("-alpha", float(val))
        self.project.window_alpha = float(val)
        self.master.save_config(force=True)

    # ---------- 以下原有方法，仅保留必要打印 ----------
    def open_settings_from_window(self):
        self.master.open_settings()

    def close_window(self):
        self.destroy()
        self.master.check_windows_status()

    def draw_background(self):
        # 如果是图片背景，不绘制纯色矩形（避免覆盖图片）
        if self.project.background_type == "image":
            return
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        self.canvas.delete("background")
        self.canvas.create_rectangle(
            0, 0, width, height,
            fill=self.project.bg_color,
            outline=self.project.bg_color,
            tags="background"
        )
        self.canvas.tag_raise("text")
        self.canvas.tag_raise("drag_hint")
        log_message(f"窗口 {self.project.name} 重绘背景", "DEBUG")

    def load_background_image(self):
        try:
            current_dir = os.getcwd()
            data_dir = os.path.join(current_dir, "data")
            user_dir = os.path.join(data_dir, "user")
            os.makedirs(user_dir, exist_ok=True)
            image_path = os.path.join(user_dir, self.project.background_image)
            if not os.path.exists(image_path):
                image_path = os.path.join(data_dir, self.project.background_image)
            log_message(f"尝试加载背景图片: {image_path}", "DEBUG")
            if os.path.exists(image_path):
                self.bg_image = Image.open(image_path)
                self.update_background_image()
            else:
                log_message(f"图片文件不存在: {image_path}，使用纯色背景", "WARNING")
                self.project.background_type = "color"
                self.refresh()
        except Exception as e:
            log_message(f"加载背景图片失败: {e} | {traceback.format_exc()}", "ERROR")
            self.project.background_type = "color"
            self.refresh()

    def update_background_image(self):
        # 取消之前的更新定时器，避免并发
        if hasattr(self, 'bg_image_timer') and self.bg_image_timer:
            self.after_cancel(self.bg_image_timer)
            self.bg_image_timer = None

        if not self.bg_image:
            return
        try:
            width = self.winfo_width()
            height = self.winfo_height()
            if width <= 1 or height <= 1:
                self.bg_image_timer = self.after(100, self.update_background_image)
                return

            resized_image = self.bg_image.copy()
            resized_image = resized_image.resize((width, height), Image.LANCZOS)
            brightness = self.master.theme.window_brightness
            saturation = self.master.theme.window_saturation
            if brightness != 1.0:
                enhancer = ImageEnhance.Brightness(resized_image)
                resized_image = enhancer.enhance(brightness)
            if saturation != 1.0:
                enhancer = ImageEnhance.Color(resized_image)
                resized_image = enhancer.enhance(saturation)
            self.bg_photo = ImageTk.PhotoImage(resized_image)

            # 彻底删除旧图片项
            if self.bg_image_id is not None:
                self.canvas.delete(self.bg_image_id)
                self.bg_image_id = None

            self.bg_image_id = self.canvas.create_image(
                0, 0,
                anchor=tk.NW,
                image=self.bg_photo,
                tags="background_image"
            )
            self.canvas.lower(self.bg_image_id)

            # 强制刷新画布，消除残留
            self.canvas.update_idletasks()

            self.canvas.tag_raise("text")
            self.canvas.tag_raise("drag_hint")
            log_message(f"窗口 {self.project.name} 更新背景图片", "DEBUG")
        except Exception as e:
            log_message(f"更新背景图片失败: {e} | {traceback.format_exc()}", "ERROR")

    def create_text_elements(self):
        width = self.winfo_width()
        height = self.winfo_height()
        global_font = self.master.global_font
        self.project_text_id = self.canvas.create_text(
            width / 2, height * 0.15,
            text=self.project.name,
            font=(global_font, 12, "bold"),
            fill=self.project.font_color,
            anchor="center",
            tags="text"
        )
        self.countdown_text_id = self.canvas.create_text(
            width / 2, height * 0.5,
            text="",
            font=(global_font, self.project.font_size, "bold"),
            fill=self.project.font_color,
            anchor="center",
            width=width - 40,
            justify="center",
            tags="text"
        )
        self.poem_text_id = self.canvas.create_text(
            width / 2, height * 0.8,
            text=self.master.daily_poem if self.master.poem_level != "none" else "",
            font=(global_font, 10),
            fill=self.project.font_color,
            anchor="center",
            width=width - 40,
            justify="center",
            tags="text"
        )
        if self.bg_image_id:
            self.canvas.tag_raise("text")

    def draw_drag_hint(self):
        width = self.winfo_width()
        height = self.winfo_height()
        self.drag_hint_id = self.canvas.create_text(
            width / 2, height * 0.9,
            text=tr("right_click_hint"),
            font=(self.master.global_font, 9, "italic"),
            fill="#FF0000" if self.project.bg_color != "#FF0000" else "#FFFFFF",
            anchor="center",
            tags="drag_hint",
            state="hidden"
        )

    def update_text_elements(self):
        width = self.winfo_width()
        height = self.winfo_height()
        layout = self.project.custom_layout

        if layout:
            # 存在自定义布局：只更新文字内容和换行宽度，坐标保持不变
            if "name" in layout:
                self.canvas.itemconfig(self.project_text_id, text=self.project.name, width=width - 40)
            else:
                self.canvas.coords(self.project_text_id, width / 2, height * 0.15)
                self.canvas.itemconfig(self.project_text_id, text=self.project.name)

            if "countdown" in layout:
                self.canvas.itemconfig(self.countdown_text_id, width=width - 40)
            else:
                self.canvas.coords(self.countdown_text_id, width / 2, height * 0.5)
                self.canvas.itemconfig(self.countdown_text_id, width=width - 40)

            if "poem" in layout:
                self.canvas.itemconfig(self.poem_text_id,
                                       text=self.master.daily_poem if self.master.poem_level != "none" else "",
                                       width=width - 40)
            else:
                self.canvas.coords(self.poem_text_id, width / 2, height * 0.8)
                self.canvas.itemconfig(self.poem_text_id,
                                       text=self.master.daily_poem if self.master.poem_level != "none" else "",
                                       width=width - 40)

            # 拖动提示一般不自定义，仍按比例放置
            self.canvas.coords(self.drag_hint_id, width / 2, height * 0.9)

            # 调试：打印当前坐标
            log_message(f"自定义布局生效 - 名称: {self.canvas.coords(self.project_text_id)}, 倒计时: {self.canvas.coords(self.countdown_text_id)}, 诗词: {self.canvas.coords(self.poem_text_id)}", "DEBUG")
        else:
            # 无自定义布局：全部按默认比例设置
            self.canvas.coords(self.project_text_id, width / 2, height * 0.15)
            self.canvas.itemconfig(self.project_text_id, text=self.project.name)
            self.canvas.coords(self.countdown_text_id, width / 2, height * 0.5)
            self.canvas.itemconfig(self.countdown_text_id, width=width - 40)
            self.canvas.coords(self.poem_text_id, width / 2, height * 0.8)
            self.canvas.itemconfig(self.poem_text_id,
                                   text=self.master.daily_poem if self.master.poem_level != "none" else "",
                                   width=width - 40)
            self.canvas.coords(self.drag_hint_id, width / 2, height * 0.9)

        if self.bg_image_id:
            self.canvas.tag_raise("text")
            self.canvas.tag_raise("drag_hint")

    def on_configure(self, event):
        log_message(f"窗口 {self.project.name} 调整尺寸", "DEBUG")
        if self.project.background_type == "color":
            self.draw_background()
        elif self.project.background_type == "image" and self.project.background_image:
            # 取消延迟，直接更新（如果尺寸无效，内部会再次定时）
            if hasattr(self, 'bg_image_timer') and self.bg_image_timer:
                self.after_cancel(self.bg_image_timer)
                self.bg_image_timer = None
            self.update_background_image()
        self.update_text_elements()
        self.save_config_later()
        if self.project.auto_font:
            self.adjust_font_size()
        self.apply_round_corners()

    def adjust_font_size(self):
        if not self.project.auto_font:
            return
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        base_size = 12
        width_factor = max(0, (width - 200) / 100 * 3)
        height_factor = max(0, (height - 80) / 50 * 2)
        new_size = int(base_size + min(width_factor, height_factor))
        new_size = max(12, min(64, new_size))
        self.canvas.itemconfig(self.countdown_text_id, font=(self.master.global_font, new_size, "bold"))
        log_message(f"窗口 {self.project.name} 自适应字体大小: {new_size}", "DEBUG")

    def save_config_later(self):
        if self.save_timer:
            self.after_cancel(self.save_timer)
        self.save_timer = self.after(400, self.save_config_now)

    def save_config_now(self):
        self.project.position = (self.winfo_x(), self.winfo_y())
        self.project.size = (self.winfo_width(), self.winfo_height())
        self.master.save_config(force=True)
        self.save_timer = None

    def schedule_update(self):
        self.update_countdown()
        self.update_timer = self.after(60000, self.schedule_update)

    def on_motion(self, event):
        width = self.winfo_width()
        height = self.winfo_height()
        edge_size = 10
        if event.x >= width - edge_size and event.y >= height - edge_size:
            self.config(cursor="sizing")
        elif event.x >= width - edge_size:
            self.config(cursor="right_side")
        elif event.y >= height - edge_size:
            self.config(cursor="bottom_side")
        elif event.x <= edge_size:
            self.config(cursor="left_side")
        elif event.y <= edge_size:
            self.config(cursor="top_side")
        else:
            self.config(cursor="")

    def start_drag_or_resize(self, event):
        width = self.winfo_width()
        height = self.winfo_height()
        edge_size = 10
        if event.x <= edge_size:
            self.resize_data = {
                "resizing": True,
                "edge": "left",
                "start_x": event.x_root,
                "start_y": event.y_root,
                "width": width,
                "height": height,
                "x": self.winfo_x()
            }
        elif event.x >= width - edge_size:
            self.resize_data = {
                "resizing": True,
                "edge": "right",
                "start_x": event.x_root,
                "start_y": event.y_root,
                "width": width,
                "height": height,
                "x": self.winfo_x()
            }
        elif event.y <= edge_size:
            self.resize_data = {
                "resizing": True,
                "edge": "top",
                "start_x": event.x_root,
                "start_y": event.y_root,
                "width": width,
                "height": height,
                "y": self.winfo_y()
            }
        elif event.y >= height - edge_size:
            self.resize_data = {
                "resizing": True,
                "edge": "bottom",
                "start_x": event.x_root,
                "start_y": event.y_root,
                "width": width,
                "height": height,
                "y": self.winfo_y()
            }
        else:
            self.drag_data = {
                "x": event.x_root,
                "y": event.y_root,
                "win_x": self.winfo_x(),
                "win_y": self.winfo_y(),
                "dragging": True
            }
            self.canvas.itemconfig(self.drag_hint_id, state="normal")
            log_message(f"开始拖动窗口 {self.project.name}", "DEBUG")

    def stop_drag_or_resize(self, event):
        if self.resize_data and self.resize_data["resizing"]:
            self.resize_data["resizing"] = False
            self.config(cursor="")
            self.save_config_later()
            log_message(f"结束调整窗口 {self.project.name} 大小", "DEBUG")
        elif self.drag_data and self.drag_data["dragging"]:
            self.drag_data["dragging"] = False
            self.canvas.itemconfig(self.drag_hint_id, state="hidden")
            self.canvas.update_idletasks()
            self.save_config_later()
            log_message(f"结束拖动窗口 {self.project.name}", "DEBUG")

    def on_drag_or_resize(self, event):
        if self.resize_data and self.resize_data["resizing"]:
            dx = event.x_root - self.resize_data["start_x"]
            dy = event.y_root - self.resize_data["start_y"]
            min_width, min_height = 250, 150
            new_width = self.resize_data["width"]
            new_height = self.resize_data["height"]
            new_x = self.winfo_x()
            new_y = self.winfo_y()
            if self.resize_data["edge"] == "left":
                new_width = max(min_width, self.resize_data["width"] - dx)
                new_x = self.resize_data["x"] + dx
            elif self.resize_data["edge"] == "right":
                new_width = max(min_width, self.resize_data["width"] + dx)
            elif self.resize_data["edge"] == "top":
                new_height = max(min_height, self.resize_data["height"] - dy)
                new_y = self.resize_data["y"] + dy
            elif self.resize_data["edge"] == "bottom":
                new_height = max(min_height, self.resize_data["height"] + dy)
            self.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
            self.on_configure(None)
        elif self.drag_data and self.drag_data["dragging"]:
            dx = event.x_root - self.drag_data["x"]
            dy = event.y_root - self.drag_data["y"]
            x = self.drag_data["win_x"] + dx
            y = self.drag_data["win_y"] + dy
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            window_width = self.winfo_width()
            window_height = self.winfo_height()
            x = max(0, min(x, screen_width - window_width))
            y = max(0, min(y, screen_height - window_height))
            self.geometry(f"+{x}+{y}")

    def show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def set_topmost(self):
        self.attributes("-topmost", True)
        self.project.always_on_top = True
        self.master.save_config(force=True)
        log_message(f"窗口 {self.project.name} 置顶", "INFO")

    def unset_topmost(self):
        self.attributes("-topmost", False)
        self.project.always_on_top = False
        self.master.save_config(force=True)
        log_message(f"窗口 {self.project.name} 取消置顶", "INFO")

    def refresh(self, update_poem=False, theme_change=False):
        if not self.winfo_exists():
            return
        self.attributes("-alpha", self.project.window_alpha)

        # 处理背景类型切换
        if self.project.background_type == "color":
            if self.bg_image_id is not None:
                self.canvas.delete(self.bg_image_id)
                self.bg_image_id = None
                self.bg_photo = None
                self.bg_image = None
            self.canvas.config(bg=self.project.bg_color)
            self.draw_background()
        elif self.project.background_type == "image" and self.project.background_image:
            if self.bg_image_id is not None:
                self.canvas.delete(self.bg_image_id)
                self.bg_image_id = None
                self.bg_photo = None
                self.bg_image = None
            self.canvas.config(bg="black")
            self.load_background_image()

        # 根据当前主题更新字体和颜色
        if self.master.current_theme == "system_native":
            default_font = "TkDefaultFont"
            self.canvas.itemconfig(self.project_text_id, font=(default_font, 12, "bold"))
            self.canvas.itemconfig(self.countdown_text_id, font=(default_font, self.project.font_size, "bold"))
            self.canvas.itemconfig(self.poem_text_id, font=(default_font, 10))
            self.canvas.itemconfig(self.drag_hint_id, font=(default_font, 9, "italic"))
            self.canvas.itemconfig("text", fill=self.project.font_color)
            self.canvas.itemconfig(self.drag_hint_id,
                                   fill="#FF0000" if self.project.bg_color != "#FF0000" else "#FFFFFF")
        else:
            global_font = self.master.global_font
            self.canvas.itemconfig(self.project_text_id, font=(global_font, 12, "bold"))
            self.canvas.itemconfig(self.countdown_text_id, font=(global_font, self.project.font_size, "bold"))
            self.canvas.itemconfig(self.poem_text_id, font=(global_font, 10))
            self.canvas.itemconfig(self.drag_hint_id, font=(global_font, 9, "italic"))
            self.canvas.itemconfig("text", fill=self.project.font_color)
            self.canvas.itemconfig(self.drag_hint_id,
                                   fill="#FF0000" if self.project.bg_color != "#FF0000" else "#FFFFFF")

        if update_poem:
            self.canvas.itemconfig(self.poem_text_id,
                                   text=self.master.daily_poem if self.master.poem_level != "none" else "")
        if self.project.auto_font:
            self.adjust_font_size()
        else:
            pass

        self.canvas.tag_raise("text")
        self.canvas.tag_raise("drag_hint")
        self.update_countdown()
        if theme_change:
            self.apply_round_corners()
        log_message(f"窗口 {self.project.name} 刷新", "DEBUG")
    def destroy(self):
        self.master.plugin_manager.trigger_event("on_window_closed", self, self.project)
        if hasattr(self, 'save_timer') and self.save_timer:
            self.after_cancel(self.save_timer)
        if hasattr(self, 'update_timer') and self.update_timer:
            self.after_cancel(self.update_timer)
        if hasattr(self, 'bg_image_timer') and self.bg_image_timer:
            self.after_cancel(self.bg_image_timer)
        super().destroy()
        log_message(f"窗口 {self.project.name} 销毁", "DEBUG")

    def apply_round_corners(self):
        if sys.platform != "win32":
            return
        radius = self.master.theme.window_round_radius
        if radius <= 0:
            return
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = ctypes.windll.user32.GetActiveWindow()
            width = self.winfo_width()
            height = self.winfo_height()
            if width <= 1 or height <= 1:
                return
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, width + 1, height + 1,
                radius, radius
            )
            ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
            ctypes.windll.gdi32.DeleteObject(hrgn)
        except Exception as e:
            log_message(f"设置窗口圆角失败: {e}", "ERROR")
# ---------- SystemTrayIcon ----------
class SystemTrayIcon:
    def __init__(self, master):
        debug_print("【DEBUG】SystemTrayIcon.__init__ 开始")
        self.master = master
        try:
            import pystray
            self.pystray_available = True
            self.create_tray_icon()
        except ImportError:
            self.pystray_available = False
            log_message("pystray未安装，系统托盘功能不可用", "WARNING")
            debug_print("【DEBUG】pystray 未安装，托盘不可用")
        debug_print("【DEBUG】SystemTrayIcon.__init__ 完成")

    def create_tray_icon(self):
        if not self.pystray_available:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw
            current_dir = os.getcwd()
            data_dir = os.path.join(current_dir, "data")
            icon_path = os.path.join(data_dir, "tubiao.bmp")
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
            else:
                image = Image.new('RGB', (64, 64), color='#3498db')
                draw = ImageDraw.Draw(image)
                draw.rectangle([16, 16, 48, 48], fill='#ffffff')
                draw.text((24, 24), "CD", fill='#3498db')
            menu = pystray.Menu(
                pystray.MenuItem(tr("settings_title"), self.show_settings),
                pystray.MenuItem("显示所有窗口" if CURRENT_LANG == LANG_CHINESE else "Show all windows", self.show_all_windows),
                pystray.MenuItem("隐藏所有窗口" if CURRENT_LANG == LANG_CHINESE else "Hide all windows", self.hide_all_windows),
                pystray.MenuItem("退出" if CURRENT_LANG == LANG_CHINESE else "Quit", self.quit_app)
            )
            self.icon = pystray.Icon("countdown_app", image, tr("app_title"), menu)
            import threading
            self.tray_thread = threading.Thread(target=self.icon.run, daemon=True)
            self.tray_thread.start()
            debug_print("【DEBUG】系统托盘图标线程已启动")
        except Exception as e:
            log_message(f"创建系统托盘失败: {e}", "WARNING")
            debug_print(f"【DEBUG】创建系统托盘失败: {e}")
            self.pystray_available = False

    def show_settings(self, icon=None, item=None):
        self.master.open_settings()

    def show_all_windows(self, icon=None, item=None):
        self.master.create_windows()

    def hide_all_windows(self, icon=None, item=None):
        for window in getattr(self.master, 'windows', []):
            try:
                window.destroy()
            except:
                pass
        self.master.windows = []

    def quit_app(self, icon=None, item=None):
        self.master.quit_app()

# ---------- 主应用 CountdownApp ----------
class CountdownApp(tk.Tk):
    def __init__(self):
        debug_print("【DEBUG】CountdownApp.__init__ 开始")
        super().__init__()
        debug_print("【DEBUG】CountdownApp super 完成")
        self.title(tr("app_title"))
        self.withdraw()
        debug_print("【DEBUG】CountdownApp 主窗口已隐藏")

        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        self.current_version = "2.7Beta"
        self.python_version = sys.version.split()[0]

        self.available_fonts = [
            "微软雅黑", "华文楷体", "宋体", "黑体", "楷体", "仿宋",
            "Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana", "Tahoma"
        ]
        self.global_font = "微软雅黑"

        self.current_theme = "light"
        self.custom_themes = []
        self.theme = BUILTIN_THEMES["light"]

        self.projects = [
            CountdownProject("演示项目", "2026-06-20", "00:00", True, 18, "#3498db", "#FFFFFF",
                             screen_width=self.screen_width, screen_height=self.screen_height),
        ]
        self.auto_start = False
        self.last_save_time = 0
        self.settings_geometry = None
        self.editor_geometry = None
        self.help_geometry = None
        self.tools_geometry = None
        self.poem_level = "junior"
        self.daily_poem = ""

        self.plugin_monitor = False
        self.plugin_prompt_on_deny = True
        self.global_disable_all_plugins = False

        self.current_dir = os.getcwd()
        self.data_dir = os.path.join(self.current_dir, "data")
        self.user_dir = os.path.join(self.data_dir, "user")
        os.makedirs(self.user_dir, exist_ok=True)
        debug_print(f"【DEBUG】数据目录: {self.data_dir}, 用户目录: {self.user_dir}")

        # 显示启动动画
        self.show_splash()

        self.load_languages()
        self.load_poems()

        # 插件管理器延迟加载
        self.plugin_manager = PluginManager(self, load_immediately=False)
        self.after(1000, self._load_plugins_and_restore)

        self.load_security_config()
        self.update_daily_poem()

        self.tray_icon = SystemTrayIcon(self)

        self.config_path = os.path.join(self.data_dir, "countdown_config.json")
        self.load_config()

        self.check_command_interval = 1000
        self.check_debug_command()

        # 立即创建窗口
        self.create_windows()
        log_message("应用程序初始化完成", "INFO")
        debug_print("【DEBUG】__init__ 完成，已立即调用 create_windows")

        self._settings_tree = None
        self._settings_plugin_items = None
        self._settings_window = None

        # 测试 Tkinter 基本功能（如果启动画面未执行）
        debug_print("测试 Tkinter 基本功能")
        test_label = tk.Label(self, text="Test")
        test_label.pack()
        self.update()
        debug_print("Tkinter 基本功能正常")
        test_label.destroy()

    def show_splash(self):
        """显示启动画面"""
        debug_print("【DEBUG】show_splash 开始")
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        splash.configure(bg=self.theme.bg_color)
        splash.update_idletasks()
        width, height = 200, 200
        x = (self.screen_width - width) // 2
        y = (self.screen_height - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")
        debug_print(f"【DEBUG】启动画面位置: {x},{y}")

        icon_path = os.path.join(self.data_dir, "djstp.ico")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                img = img.resize((100, 100), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                label = tk.Label(splash, image=photo, bg=self.theme.bg_color)
                label.image = photo
                label.pack(expand=True)
                debug_print("【DEBUG】启动画面加载图标成功")
            except:
                tk.Label(splash, text="加载中...", font=("微软雅黑", 16), bg=self.theme.bg_color, fg=self.theme.accent_color).pack(expand=True)
                debug_print("【DEBUG】启动画面使用文字")
        else:
            tk.Label(splash, text="加载中...", font=("微软雅黑", 16), bg=self.theme.bg_color, fg=self.theme.accent_color).pack(expand=True)
            debug_print("【DEBUG】启动画面使用文字（无图标）")

        self.splash = splash
        self.update_idletasks()
        # 2秒后关闭
        self.after(2000, self.hide_splash)
        debug_print("【DEBUG】show_splash 完成")

    def hide_splash(self):
        if hasattr(self, 'splash') and self.splash:
            self.splash.destroy()
            self.splash = None
            debug_print("【DEBUG】启动画面已关闭")

    def _load_plugins_and_restore(self):
        """加载插件并恢复启用状态"""
        debug_print("【DEBUG】开始加载插件")
        self.plugin_manager.load_plugins()
        self.restore_plugin_states()
        debug_print("【DEBUG】插件加载完成")

    def load_languages(self):
        global _lang_data
        lang_file = os.path.join(self.data_dir, "languages.json")
        if os.path.exists(lang_file):
            try:
                with open(lang_file, "r", encoding="utf-8") as f:
                    _lang_data = json.load(f)
                log_message("语言文件加载成功", "INFO")
            except Exception as e:
                log_message(f"加载语言文件失败，将使用键名作为翻译: {e}", "ERROR")
                _lang_data = {}
        else:
            log_message("语言文件不存在，将使用键名作为翻译", "WARNING")
            _lang_data = {}

    def load_poems(self):
        poem_file = os.path.join(self.data_dir, "poems.json")
        if os.path.exists(poem_file):
            try:
                with open(poem_file, "r", encoding="utf-8") as f:
                    self.poems_data = json.load(f)
                log_message("诗词文件加载成功", "INFO")
            except Exception as e:
                log_message(f"加载诗词文件失败，每日一诗功能将不可用: {e}", "ERROR")
                self.poems_data = {"primary": [], "junior": [], "senior": []}
        else:
            log_message("诗词文件不存在，每日一诗功能将不可用", "WARNING")
            self.poems_data = {"primary": [], "junior": [], "senior": []}

    def load_security_config(self):
        if hasattr(self, 'config_path') and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                self.plugin_prompt_on_deny = config.get('plugin_prompt_on_deny', True)
                self.global_disable_all_plugins = config.get('global_disable_all_plugins', False)
            except:
                pass

    @staticmethod
    def ask_with_timeout(parent, title, message, timeout=20):
        result = False
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        label = tk.Label(dialog, text=message, wraplength=350, justify="left")
        label.pack(pady=20)

        time_var = tk.StringVar()
        time_var.set(f"({timeout} 秒后自动取消)")
        time_label = tk.Label(dialog, textvariable=time_var, fg="gray")
        time_label.pack()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)

        def on_ok():
            nonlocal result
            result = True
            dialog.destroy()
        def on_cancel():
            dialog.destroy()

        ok_btn = tk.Button(btn_frame, text="确认启用", command=on_ok, bg="#e67e22", fg="white", width=12)
        ok_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="取消", command=on_cancel, width=12)
        cancel_btn.pack(side=tk.LEFT, padx=5)

        def update_countdown(remaining):
            if remaining <= 0:
                dialog.destroy()
                return
            time_var.set(f"({remaining} 秒后自动取消)")
            dialog.after(1000, update_countdown, remaining - 1)
        dialog.after(1000, update_countdown, timeout - 1)

        parent.wait_window(dialog)
        return result

    def ask_permission(self, plugin, perm, operation_desc):
        import threading
        result = [False]
        event = threading.Event()
        def dialog():
            dlg = tk.Toplevel(self)
            dlg.title("插件权限请求")
            dlg.geometry("400x400")
            dlg.resizable(False, False)
            dlg.grab_set()
            dlg.update_idletasks()
            x = (dlg.winfo_screenwidth() - dlg.winfo_width()) // 2
            y = (dlg.winfo_screenheight() - dlg.winfo_height()) // 2
            dlg.geometry(f"+{x}+{y}")

            perm_names = {
                PluginPermission.FILE_READ: "读取文件",
                PluginPermission.FILE_WRITE: "写入文件",
                PluginPermission.NETWORK: "网络连接",
                PluginPermission.COMMAND: "执行系统命令"
            }
            perm_name = perm_names.get(perm, str(perm))
            msg = f"插件“{plugin.name}”请求执行以下操作：\n{perm_name}: {operation_desc}\n\n是否允许？"
            tk.Label(dlg, text=msg, wraplength=350, justify='left').pack(pady=20)

            def allow():
                result[0] = True
                dlg.destroy()
                event.set()
            def deny():
                result[0] = False
                dlg.destroy()
                event.set()

            btn_frame = tk.Frame(dlg)
            btn_frame.pack(pady=10)
            tk.Button(btn_frame, text="允许", command=allow, bg="#2ecc71", width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="拒绝", command=deny, bg="#e74c3c", width=10).pack(side=tk.LEFT, padx=5)

        self.after(0, dialog)
        event.wait()
        return result[0]

    def toggle_global_disable_plugins(self, disable):
        self.global_disable_all_plugins = disable
        if disable:
            for plugin in self.plugin_manager.get_enabled_plugins():
                self.plugin_manager.disable_plugin(plugin)
        else:
            messagebox.showinfo("全局禁用", "请手动启用需要的插件")
        self.save_config()

    def emergency_stop_all(self):
        for plugin in self.plugin_manager.plugins:
            plugin.emergency_stop = True
        log_message("所有插件已被紧急停止", "WARNING")

    def ask_disable_plugin(self, plugin, error_info):
        msg = (f"插件“{plugin.name}”在执行过程中发生错误：\n{error_info}\n\n"
               f"是否要立即禁用该插件？")
        result = messagebox.askyesno("插件行为监控", msg, icon='warning')
        if result:
            self.plugin_manager.disable_plugin(plugin)
            if self._settings_window and self._settings_window.winfo_exists():
                self.refresh_plugin_tree_in_settings()

    def refresh_plugin_tree_in_settings(self):
        if self._settings_tree and self._settings_plugin_items is not None:
            tree = self._settings_tree
            plugin_items = self._settings_plugin_items
            for item in tree.get_children():
                tree.delete(item)
            plugin_items.clear()
            for plugin in self.plugin_manager.plugins:
                risk = self.plugin_manager.get_plugin_risk(plugin)
                name_display = plugin.name
                if risk > 0:
                    name_display += " ⚠️"
                status_text = "启用" if plugin.enabled else "禁用" if CURRENT_LANG == LANG_CHINESE else (
                    "Enabled" if plugin.enabled else "Disabled")
                if risk == 2:
                    status_text += " [危险]" if CURRENT_LANG == LANG_CHINESE else " [Danger]"
                elif risk == 1:
                    status_text += " [风险]" if CURRENT_LANG == LANG_CHINESE else " [Risk]"
                perm_text = ""
                if plugin.permissions & PluginPermission.FILE_READ:
                    perm_text += "R"
                if plugin.permissions & PluginPermission.FILE_WRITE:
                    perm_text += "W"
                if plugin.permissions & PluginPermission.NETWORK:
                    perm_text += "N"
                if plugin.permissions & PluginPermission.COMMAND:
                    perm_text += "C"
                if not perm_text:
                    perm_text = "无"
                item = tree.insert("", tk.END, values=(name_display, plugin.version, plugin.author, status_text, perm_text))
                plugin_items[item] = plugin

    def restore_plugin_states(self):
        config_path = os.path.join(self.data_dir, "countdown_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                plugin_states = config.get("plugin_states", {})
                for plugin in self.plugin_manager.plugins:
                    state = plugin_states.get(plugin.filename, {})
                    enabled = state.get("enabled", False)
                    limited = state.get("limited", False)
                    if enabled:
                        risk = self.plugin_manager.get_plugin_risk(plugin)
                        if risk >= 2:
                            log_message(f"高风险插件 {plugin.name} 根据配置启用（用户已确认）", "INFO")
                            self.plugin_manager.enable_plugin(plugin, force=True, limited=limited)
                        else:
                            self.plugin_manager.enable_plugin(plugin, limited=limited)
                    else:
                        log_message(f"插件 {plugin.name} 保持禁用", "DEBUG")
            except Exception as e:
                log_message(f"恢复插件状态失败: {e}", "ERROR")

    def check_windows_status(self):
        active_windows = 0
        for window in getattr(self, 'windows', []):
            try:
                if window.winfo_exists():
                    active_windows += 1
            except tk.TclError:
                pass
        log_message(f"活跃窗口数量: {active_windows}", "DEBUG")
        if active_windows == 0:
            children = self.winfo_children()
            has_dialogs = False
            for child in children:
                if isinstance(child, tk.Toplevel) and child.winfo_viewable():
                    has_dialogs = True
                    break
            if not has_dialogs:
                log_message("所有悬浮窗已关闭，应用仍在后台运行", "INFO")

    def quit_app(self):
        self.save_config(force=True)
        self.destroy()
        log_message("应用退出", "INFO")

    def update_daily_poem(self):
        if self.poem_level != "none":
            poems = self.poems_data.get(self.poem_level, [])
            if poems:
                self.daily_poem = random.choice(poems)
            else:
                self.daily_poem = ""
        else:
            self.daily_poem = ""
        self.plugin_manager.trigger_event("on_poem_update", self.daily_poem)

    def create_windows(self):
        debug_print("【DEBUG】create_windows 开始")
        self.update_idletasks()
        debug_print("create_windows: 开始销毁旧窗口")
        for window in getattr(self, 'windows', []):
            try:
                window.destroy()
            except:
                pass
        self.windows = []
        debug_print(f"create_windows: 准备创建 {len(self.projects)} 个窗口")
        for i, project in enumerate(self.projects):
            debug_print(f"正在创建窗口 {i}: {project.name}")
            try:
                window = CountdownWindow(self, project, i)
                self.windows.append(window)
                debug_print(f"窗口 {i} 创建成功")
            except Exception as e:
                debug_print(f"创建窗口 {i} 失败: {e}")
                traceback.print_exc(file=sys.stderr)
                log_message(f"创建窗口失败: {e} | {traceback.format_exc()}", "ERROR")
        debug_print(f"create_windows: 完成，当前窗口数: {len(self.windows)}")
        log_message(f"已创建 {len(self.windows)} 个窗口", "INFO")

    def get_optimal_window_size(self, base_width, base_height, dialog_type="settings"):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        if dialog_type == "settings":
            base_w, base_h = 850, 1350
        elif dialog_type == "help":
            base_w, base_h = 800, 600
        elif dialog_type == "editor":
            base_w, base_h = 800, 1050
        elif dialog_type == "tools":
            base_w, base_h = 700, 1050
        else:
            base_w, base_h = base_width, base_height
        scale_w = screen_width / 2560
        scale_h = screen_height / 1440
        scale = min(scale_w, scale_h, 1.2)
        optimal_width = int(base_w * scale)
        optimal_height = int(base_h * scale)
        optimal_width = min(optimal_width, int(screen_width * 0.9))
        optimal_height = min(optimal_height, int(screen_height * 0.9))
        return optimal_width, optimal_height

    def load_config(self):
        global DEBUG_MODE, CONFIG_LOADED, STATUS_MONITOR, CURRENT_LANG
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    self.projects = [CountdownProject.from_dict(p, self.screen_width, self.screen_height)
                                     for p in config.get("projects", [])]
                    if not self.projects:
                        self.projects = [
                            CountdownProject(screen_width=self.screen_width, screen_height=self.screen_height)]
                    self.auto_start = config.get("auto_start", False)
                    self.settings_geometry = config.get("settings_geometry", None)
                    self.editor_geometry = config.get("editor_geometry", None)
                    self.help_geometry = config.get("help_geometry", None)
                    self.tools_geometry = config.get("tools_geometry", None)
                    self.poem_level = config.get("poem_level", "junior")
                    debug_val = config.get("debug_mode", 0)
                    if isinstance(debug_val, bool):
                        DEBUG_MODE = 3 if debug_val else 0
                    else:
                        DEBUG_MODE = debug_val
                    STATUS_MONITOR = config.get("status_monitor", False)
                    self.global_font = config.get("global_font", "微软雅黑")
                    lang = config.get("language", LANG_CHINESE)
                    if lang in [LANG_CHINESE, LANG_ENGLISH]:
                        CURRENT_LANG = lang
                    self.plugin_monitor = config.get("plugin_monitor", False)
                    self.plugin_prompt_on_deny = config.get("plugin_prompt_on_deny", True)
                    self.global_disable_all_plugins = config.get("global_disable_all_plugins", False)
                    self.current_theme = config.get("current_theme", "light")
                    self.custom_themes = [Theme.from_dict(t) for t in config.get("custom_themes", [])]
                    self._apply_theme(self.current_theme)
                    CONFIG_LOADED = True
                log_message(f"从 {self.config_path} 加载配置成功", "INFO")
            else:
                self.projects = [
                    CountdownProject("示例项目", "2026-06-20", "00:00", True, 18, "#3498db", "#FFFFFF",
                                     screen_width=self.screen_width, screen_height=self.screen_height),
                ]
                self.save_config(force=True)
                log_message(f"创建默认配置文件: {self.config_path}", "INFO")
        except Exception as e:
            log_message(f"加载配置错误: {e} | {traceback.format_exc()}", "ERROR")
            self.projects = [
                CountdownProject("示例项目", "2026-06-20", "00:00", True, 18, "#3498db", "#FFFFFF",
                                 screen_width=self.screen_width, screen_height=self.screen_height),
            ]
            self.save_config(force=True)

    def save_config(self, force=False):
        global DEBUG_MODE, STATUS_MONITOR, CURRENT_LANG
        log_message("开始保存配置", "DEBUG")
        self.plugin_manager.trigger_event("on_before_save_config")
        current_time = time.time()
        if not force and current_time - self.last_save_time < 1.0:
            return
        try:
            for window in getattr(self, 'windows', []):
                try:
                    if window.winfo_exists():
                        window.project.position = (window.winfo_x(), window.winfo_y())
                        window.project.size = (window.winfo_width(), window.winfo_height())
                except tk.TclError:
                    pass
            plugin_states = {}
            for plugin in self.plugin_manager.plugins:
                if plugin.filename:
                    plugin_states[plugin.filename] = {"enabled": plugin.enabled, "limited": plugin.limited}
            config_data = {
                "projects": [p.to_dict() for p in self.projects],
                "auto_start": self.auto_start,
                "settings_geometry": self.settings_geometry,
                "editor_geometry": self.editor_geometry,
                "help_geometry": self.help_geometry,
                "tools_geometry": self.tools_geometry,
                "poem_level": self.poem_level,
                "debug_mode": DEBUG_MODE,
                "status_monitor": STATUS_MONITOR,
                "global_font": self.global_font,
                "language": CURRENT_LANG,
                "plugin_states": plugin_states,
                "plugin_monitor": self.plugin_monitor,
                "plugin_prompt_on_deny": self.plugin_prompt_on_deny,
                "global_disable_all_plugins": self.global_disable_all_plugins,
                "current_theme": self.current_theme,
                "custom_themes": [t.to_dict() for t in self.custom_themes]
            }
            with open(self.config_path, "w") as f:
                json.dump(config_data, f, indent=2)
            self.last_save_time = current_time
            log_message(f"配置已保存到: {self.config_path}", "INFO")
            self.plugin_manager.trigger_event("on_after_save_config")
        except Exception as e:
            log_message(f"保存配置错误: {e} | {traceback.format_exc()}", "ERROR")
        log_message("配置保存完成", "DEBUG")

    def set_auto_start_with_retry(self, enabled, max_retries=10):
        self.auto_start = enabled
        auto_start_status = "设置成功" if CURRENT_LANG == LANG_CHINESE else "Success"
        auto_start_color = "#2ecc71"
        retry_count = 0
        success = False
        while retry_count < max_retries and not success:
            try:
                if sys.platform == "win32":
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                         r"Software\Microsoft\Windows\CurrentVersion\Run",
                                         0, winreg.KEY_SET_VALUE)
                    if enabled:
                        if getattr(sys, 'frozen', False):
                            executable = f'"{sys.executable}"'
                        else:
                            python_exe = sys.executable
                            pythonw_exe = python_exe.replace('python.exe', 'pythonw.exe')
                            if not os.path.exists(pythonw_exe):
                                pythonw_exe = python_exe
                            script_path = os.path.abspath(__file__)
                            executable = f'"{pythonw_exe}" "{script_path}"'
                        winreg.SetValueEx(key, "CountdownApp", 0, winreg.REG_SZ, executable)
                    else:
                        try:
                            winreg.DeleteValue(key, "CountdownApp")
                        except FileNotFoundError:
                            pass
                    winreg.CloseKey(key)
                    success = True
                else:
                    success = True
                break
            except Exception as e:
                retry_count += 1
                log_message(f"设置开机自启动失败 (尝试 {retry_count}/{max_retries}): {e}", "ERROR")
                if retry_count < max_retries:
                    time.sleep(0.5)
        if not success:
            auto_start_status = "设置失败" if CURRENT_LANG == LANG_CHINESE else "Failed"
            auto_start_color = "#e74c3c"
        return auto_start_status, auto_start_color

    def restart_application(self):
        try:
            self.save_config(force=True)
            python = sys.executable
            if getattr(sys, 'frozen', False):
                args = [sys.argv[0]]
            else:
                args = [python] + sys.argv
            subprocess.Popen(args)
            self.destroy()
        except Exception as e:
            messagebox.showerror("重启失败" if CURRENT_LANG == LANG_CHINESE else "Restart Failed",
                                 f"重启应用程序时出错: {e}\n\n请手动重启应用程序。")

    def apply_global_font(self):
        try:
            available = font.families()
            if self.global_font not in available:
                fallback = "Arial" if "Arial" in available else "TkDefaultFont"
                log_message(f"字体 {self.global_font} 不存在，使用后备字体 {fallback}", "WARNING")
                self.global_font = fallback
            for window in getattr(self, 'windows', []):
                try:
                    if window.winfo_exists():
                        window.refresh()
                except Exception as e:
                    log_message(f"悬浮窗字体设置失败: {e}", "WARNING")
            self.apply_font_to_widget(self)
            messagebox.showinfo(tr("save"), tr("global_font") + " " + ("已应用，部分界面可能需要重启生效" if CURRENT_LANG==LANG_CHINESE else "applied, some interfaces may need restart"))
        except Exception as e:
            log_message(f"应用全局字体时出错: {e}", "ERROR")
            messagebox.showerror(tr("settings_title"), f"{tr('global_font')} error: {e}")

    def apply_font_to_widget(self, widget):
        try:
            if hasattr(widget, 'config') and 'font' in widget.config():
                current_font = widget.cget('font')
                if isinstance(current_font, str) and any(
                        font in current_font for font in self.available_fonts + ["微软雅黑", "TkDefaultFont"]):
                    try:
                        font_size = self.get_font_size(current_font)
                        if "bold" in current_font.lower():
                            widget.config(font=(self.global_font, font_size, "bold"))
                        else:
                            widget.config(font=(self.global_font, font_size))
                    except:
                        widget.config(font=("微软雅黑", self.get_font_size(current_font)))
            for child in widget.winfo_children():
                self.apply_font_to_widget(child)
        except:
            pass

    def get_font_size(self, font_string):
        try:
            if isinstance(font_string, (tuple, list)):
                return font_string[1] if len(font_string) > 1 else 10
            elif isinstance(font_string, str):
                import re
                numbers = re.findall(r'\d+', font_string)
                return int(numbers[0]) if numbers else 10
            else:
                return 10
        except:
            return 10

    def check_debug_command(self):
        cmd_file = os.path.join(self.data_dir, "debug_command.txt")
        if os.path.exists(cmd_file):
            if os.path.getsize(cmd_file) == 0:
                os.remove(cmd_file)
                log_message("debug_command.txt 为空，已删除", "DEBUG")
                self.after(self.check_command_interval, self.check_debug_command)
                return
            try:
                with open(cmd_file, "r", encoding="utf-8") as f:
                    cmd_data = json.load(f)
                os.remove(cmd_file)
                self.execute_debug_command(cmd_data)
            except json.JSONDecodeError:
                log_message(f"debug_command.txt 内容不是有效 JSON，已删除", "WARNING")
                os.remove(cmd_file)
            except Exception as e:
                log_message(f"处理调试命令失败: {e}", "ERROR")
                try:
                    os.remove(cmd_file)
                except:
                    pass
        self.after(self.check_command_interval, self.check_debug_command)

    def execute_debug_command(self, cmd_data):
        command = cmd_data.get("command")
        if command == "show_message":
            message = cmd_data.get("message", "")
            level = cmd_data.get("level", "info")
            if level == "error":
                messagebox.showerror("监控程序消息", message)
            else:
                messagebox.showinfo("监控程序消息", message)
            log_message(f"收到监控消息: {message}", level.upper())
        elif command == "set_debug_level":
            new_level = cmd_data.get("level", 2)
            global DEBUG_MODE
            DEBUG_MODE = new_level
            self.save_config(force=True)
            log_message(f"监控程序将调试等级设置为 {new_level}", "INFO")
        elif command == "restart":
            self.restart_application()
        elif command == "terminate":
            self.quit_app()
        elif command == "disable_all_plugins":
            self.toggle_global_disable_plugins(True)
            log_message("监控器命令：禁用所有插件", "INFO")
        elif command == "disable_all_plugins_and_restart":
            self.toggle_global_disable_plugins(True)
            self.restart_application()
            log_message("监控器命令：禁用所有插件并重启", "INFO")
        elif command == "hide_all_windows":
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.hide_all_windows()
            else:
                for w in self.windows:
                    try:
                        w.destroy()
                    except:
                        pass
                self.windows = []
            log_message("监控器命令：隐藏所有窗口", "INFO")
        elif command == "simulate_error":
            raise Exception("这是监控器模拟的错误")
        elif command == "reset_and_restart":
            try:
                if os.path.exists(self.config_path):
                    os.remove(self.config_path)
                    log_message("已删除配置文件，将重置为默认", "INFO")
            except:
                pass
            self.restart_application()

    def _apply_theme(self, theme_name):
        if theme_name == "system_native":
            # 系统原生主题：使用一个占位 Theme 对象，但实际不应用任何自定义颜色
            self.theme = Theme("系统原生")
            self.global_font = "TkDefaultFont"
            self._apply_theme_to_all_windows()
            self._update_ttk_style(force_system=True)
        else:
            if theme_name in BUILTIN_THEMES:
                self.theme = BUILTIN_THEMES[theme_name]
            else:
                found = [t for t in self.custom_themes if t.name == theme_name]
                if found:
                    self.theme = found[0]
                else:
                    self.theme = BUILTIN_THEMES["light"]
            self.global_font = self.theme.font_family
            self._apply_theme_to_all_windows()
            self._update_ttk_style(force_system=False)

    def _apply_theme_to_widget(self, widget):
        if self.current_theme == "system_native":
            return
        try:
            if isinstance(widget, tk.Toplevel) or isinstance(widget, tk.Tk):
                widget.configure(bg=self.theme.bg_color)
            elif isinstance(widget, tk.Frame) or isinstance(widget, tk.LabelFrame):
                widget.configure(bg=self.theme.frame_bg)
            elif isinstance(widget, tk.Label):
                widget.configure(bg=self.theme.frame_bg, fg=self.theme.text_color,
                                 font=(self.theme.font_family, self.theme.font_size))
            elif isinstance(widget, tk.Button):
                widget.configure(bg=self.theme.accent_color, fg=self.theme.text_color,
                                 font=(self.theme.font_family, self.theme.font_size))
            for child in widget.winfo_children():
                self._apply_theme_to_widget(child)
        except:
            pass
    def _update_ttk_style(self, force_system=False):
        style = ttk.Style()
        if force_system:
            # 尝试使用 Windows 原生主题
            try:
                style.theme_use('vista')
            except:
                try:
                    style.theme_use('xpnative')
                except:
                    try:
                        style.theme_use('winnative')
                    except:
                        pass
            # 不进行任何自定义颜色配置
            return

        try:
            style.theme_use('clam')
        except:
            pass
        style.configure(".", background=self.theme.bg_color, foreground=self.theme.text_color,
                        font=(self.theme.font_family, self.theme.font_size))
        style.configure("TFrame", background=self.theme.bg_color)
        style.configure("TLabel", background=self.theme.bg_color, foreground=self.theme.text_color)
        style.configure("TButton", background=self.theme.accent_color, foreground=self.theme.text_color,
                        font=(self.theme.font_family, self.theme.font_size))
        style.configure("Primary.TButton", font=(self.theme.font_family, self.theme.font_size, "bold"),
                        background=self.theme.accent_color, foreground=self.theme.text_color)
        style.configure("TNotebook", background=self.theme.bg_color)
        style.configure("TNotebook.Tab", font=(self.theme.font_family, self.theme.font_size, "bold"),
                        background=self.theme.frame_bg, foreground=self.theme.text_color)
        style.map("TNotebook.Tab", background=[("selected", self.theme.accent_color)],
                  foreground=[("selected", self.theme.text_color)])
        style.configure("TLabelframe", background=self.theme.frame_bg, foreground=self.theme.text_color,
                        font=(self.theme.font_family, self.theme.font_size, "bold"))
        style.configure("TLabelframe.Label", background=self.theme.frame_bg, foreground=self.theme.text_color)
        style.configure("TEntry", fieldbackground=self.theme.frame_bg, foreground=self.theme.text_color,
                        bordercolor=self.theme.border_color, lightcolor=self.theme.border_color,
                        darkcolor=self.theme.border_color)
        style.configure("TCheckbutton", background=self.theme.bg_color, foreground=self.theme.text_color)
        style.configure("TCombobox", fieldbackground=self.theme.frame_bg, foreground=self.theme.text_color,
                        arrowcolor=self.theme.text_color)
        style.configure("TSpinbox", fieldbackground=self.theme.frame_bg, foreground=self.theme.text_color,
                        arrowcolor=self.theme.text_color)
        style.configure("TScrollbar", background=self.theme.frame_bg, troughcolor=self.theme.bg_color,
                        arrowcolor=self.theme.text_color)

    def delete_custom_theme(self):
        selected = self._theme_var.get()
        if selected in BUILTIN_THEMES:
            messagebox.showinfo(tr("theme"), tr("cannot_delete_builtin"))
            return
        for i, theme in enumerate(self.custom_themes):
            if theme.name == selected:
                del self.custom_themes[i]
                break
        else:
            return
        self._theme_combo['values'] = list(BUILTIN_THEMES.keys()) + [t.name for t in self.custom_themes]
        if self.current_theme == selected:
            self.current_theme = "light"
            self._apply_theme("light")
            self._theme_combo.set("light")
        self.save_config(force=True)
        log_message(f"删除自定义主题: {selected}", "INFO")
        messagebox.showinfo(tr("theme"), tr("theme_deleted"))

    # ---------- 设置界面----------
    def open_settings(self):
        settings = tk.Toplevel(self)
        settings.title(tr("settings_title"))
        self._settings_window = settings

        def on_settings_close():
            try:
                self.settings_geometry = settings.geometry()
                self.save_config(force=True)
            except:
                pass
            self.plugin_manager.trigger_event("on_settings_closed")
            self._settings_window = None
            self._settings_tree = None
            self._settings_plugin_items = None
            settings.destroy()

        settings.protocol("WM_DELETE_WINDOW", on_settings_close)

        optimal_width, optimal_height = self.get_optimal_window_size(930, 1100, "settings")
        x = (self.screen_width - optimal_width) // 2
        y = (self.screen_height - optimal_height) // 2

        if self.settings_geometry:
            try:
                settings.geometry(self.settings_geometry)
            except tk.TclError:
                settings.geometry(f"{optimal_width}x{optimal_height}+{x}+{y}")
        else:
            settings.geometry(f"{optimal_width}x{optimal_height}+{x}+{y}")

        settings.resizable(True, True)
        settings.minsize(400, 200)

        try:
            if sys.platform == "win32":
                settings.iconbitmap(sys.executable)
        except:
            pass

        settings.configure(bg=self.theme.bg_color)

        main_frame = ttk.Frame(settings)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0,15))

        ttk.Label(header_frame, text=tr("settings_title"), font=("微软雅黑", 16, "bold"), foreground=self.theme.accent_color).pack(side=tk.LEFT)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # ---------- 项目管理选项卡 ----------
        projects_frame = ttk.Frame(notebook, padding=10)
        notebook.add(projects_frame, text=tr("project_management"))

        list_frame = ttk.LabelFrame(projects_frame, text=tr("project_list"), padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5, ipady=5)

        projects_listbox = tk.Listbox(
            list_frame, height=8, width=70, font=("微软雅黑", 9),
            bg=self.theme.frame_bg, relief=tk.SOLID, borderwidth=1, highlightthickness=0,
            selectbackground=self.theme.accent_color, selectforeground="#ffffff"
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=projects_listbox.yview)
        projects_listbox.config(yscrollcommand=scrollbar.set)

        projects_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for i, project in enumerate(self.projects):
            projects_listbox.insert(tk.END, f"{i + 1}. {project.name} ({project.target_date})")

        btn_frame = ttk.Frame(projects_frame, padding=10)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        # 自定义外观按钮（初始隐藏）
        custom_appearance_btn = ttk.Button(btn_frame, text="自定义外观", command=None, style="Primary.TButton", width=15)
        custom_appearance_btn.pack_forget()  # 初始隐藏

        def open_custom_appearance():
            selected = projects_listbox.curselection()
            if not selected:
                return
            index = selected[0]
            project = self.projects[index]
            self.open_appearance_editor(project)
        custom_appearance_btn.config(command=open_custom_appearance)

        def on_project_select(event):
            if projects_listbox.curselection():
                custom_appearance_btn.pack(side=tk.LEFT, padx=5, ipady=3)
            else:
                custom_appearance_btn.pack_forget()
        projects_listbox.bind('<<ListboxSelect>>', on_project_select)

        def add_project():
            new_project = CountdownProject(screen_width=self.screen_width, screen_height=self.screen_height)
            self.projects.append(new_project)
            projects_listbox.insert(tk.END, f"{len(self.projects)}. {new_project.name} ({new_project.target_date})")
            project_editor(new_project, len(self.projects) - 1)
            self.create_windows()
            self.save_config(force=True)

        def remove_project():
            if len(self.projects) <= 1:
                messagebox.showwarning(tr("settings_title"),
                                       "至少需要保留一个项目" if CURRENT_LANG == LANG_CHINESE else "At least one project required")
                return
            selected = projects_listbox.curselection()
            if not selected:
                return
            index = selected[0]
            del self.projects[index]
            projects_listbox.delete(index)
            projects_listbox.delete(0, tk.END)
            for i, project in enumerate(self.projects):
                projects_listbox.insert(tk.END, f"{i + 1}. {project.name} ({project.target_date})")
            self.create_windows()
            self.save_config(force=True)

        def edit_project():
            selected = projects_listbox.curselection()
            if not selected:
                return
            index = selected[0]
            project_editor(self.projects[index], index)

        def project_editor(project, index):
            editor = tk.Toplevel(settings)
            editor.title(tr("edit_project"))

            def on_editor_close():
                try:
                    self.editor_geometry = editor.geometry()
                    self.save_config(force=True)
                except:
                    pass
                editor.destroy()

            editor.protocol("WM_DELETE_WINDOW", on_editor_close)

            optimal_width, optimal_height = self.get_optimal_window_size(800, 900, "editor")
            x = (self.screen_width - optimal_width) // 2
            y = (self.screen_height - optimal_height) // 2

            if self.editor_geometry:
                try:
                    editor.geometry(self.editor_geometry)
                except tk.TclError:
                    editor.geometry(f"{optimal_width}x{optimal_height}+{x}+{y}")
            else:
                editor.geometry(f"{optimal_width}x{optimal_height}+{x}+{y}")

            editor.resizable(True, True)
            editor.minsize(400, 200)

            try:
                if sys.platform == "win32":
                    editor.iconbitmap(sys.executable)
            except:
                pass

            main_editor = ttk.Frame(editor, padding=15)
            main_editor.pack(fill=tk.BOTH, expand=True)

            padx_val, pady_val = 10, 10

            # 项目名称
            ttk.Label(main_editor, text=tr("project_name") + ":").grid(row=0, column=0, padx=padx_val, pady=pady_val, sticky='e')
            name_var = tk.StringVar(value=project.name)
            name_entry = ttk.Entry(main_editor, textvariable=name_var, width=25)
            name_entry.grid(row=0, column=1, padx=padx_val, pady=pady_val, sticky='w')
            name_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            name_status_label.grid(row=0, column=2, padx=3, pady=pady_val)

            def update_name_status():
                if STATUS_MONITOR:
                    if name_var.get().strip():
                        name_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                    else:
                        name_status_label.config(text="设置失败" if CURRENT_LANG == LANG_CHINESE else "Failed", foreground="#e74c3c")
                else:
                    name_status_label.config(text="")
            name_var.trace("w", lambda *args: update_name_status())
            update_name_status()

            # 目标日期
            ttk.Label(main_editor, text=tr("target_date") + ":").grid(row=1, column=0, padx=padx_val, pady=pady_val, sticky='e')
            date_var = tk.StringVar(value=project.target_date)
            date_entry = ttk.Entry(main_editor, textvariable=date_var, width=25)
            date_entry.grid(row=1, column=1, padx=padx_val, pady=pady_val, sticky='w')
            date_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            date_status_label.grid(row=1, column=2, padx=3, pady=pady_val)

            # 精确时间
            time_frame = ttk.Frame(main_editor)
            time_frame.grid(row=2, column=0, columnspan=2, padx=padx_val, pady=pady_val, sticky='w')

            exact_time_var = tk.BooleanVar(value=project.target_time != "00:00")
            exact_time_cb = ttk.Checkbutton(time_frame, text=tr("set_exact_time"), variable=exact_time_var)
            exact_time_cb.pack(side=tk.LEFT, padx=(0, 10))

            time_var = tk.StringVar(value=project.target_time if project.target_time != "00:00" else "08:00")
            time_entry = ttk.Entry(time_frame, textvariable=time_var, width=8, state=tk.DISABLED)
            time_entry.pack(side=tk.LEFT)

            time_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            time_status_label.grid(row=2, column=2, padx=3, pady=pady_val)

            def toggle_time_entry():
                if exact_time_var.get():
                    time_entry.config(state=tk.NORMAL)
                else:
                    time_entry.config(state=tk.DISABLED)
                update_time_status()
            def update_time_status():
                if STATUS_MONITOR:
                    if exact_time_var.get():
                        if validate_time(time_var.get()):
                            time_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                        else:
                            time_status_label.config(text="设置失败" if CURRENT_LANG == LANG_CHINESE else "Failed", foreground="#e74c3c")
                    else:
                        time_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    time_status_label.config(text="")
            exact_time_var.trace("w", lambda *args: toggle_time_entry())
            time_var.trace("w", lambda *args: update_time_status())
            toggle_time_entry()

            # 日期验证提示
            date_status = ttk.Label(main_editor, text="", foreground="#e74c3c", font=("微软雅黑", 8))
            date_status.grid(row=3, column=1, padx=padx_val, pady=(0, pady_val), sticky='w')

            def validate_date_entry():
                date_str = date_var.get()
                time_str = time_var.get() if exact_time_var.get() else "00:00"
                date_valid = validate_date(date_str)
                time_valid = validate_time(time_str) if exact_time_var.get() else True
                if date_valid and time_valid:
                    date_status.config(text="日期时间格式正确" if CURRENT_LANG == LANG_CHINESE else "Date/time format correct", foreground="#2ecc71")
                    if STATUS_MONITOR:
                        date_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    if not date_valid:
                        date_status.config(text="无效日期！请使用YYYY-MM-DD格式" if CURRENT_LANG == LANG_CHINESE else "Invalid date! Use YYYY-MM-DD", foreground="#e74c3c")
                        if STATUS_MONITOR:
                            date_status_label.config(text="设置失败" if CURRENT_LANG == LANG_CHINESE else "Failed", foreground="#e74c3c")
                    else:
                        date_status.config(text="无效时间！请使用HH:MM格式" if CURRENT_LANG == LANG_CHINESE else "Invalid time! Use HH:MM", foreground="#e74c3c")
                        if STATUS_MONITOR:
                            date_status_label.config(text="设置失败" if CURRENT_LANG == LANG_CHINESE else "Failed", foreground="#e74c3c")
            date_var.trace("w", lambda *args: validate_date_entry())
            time_var.trace("w", lambda *args: validate_date_entry())
            exact_time_var.trace("w", lambda *args: validate_date_entry())

            # 显示工作日
            show_var = tk.BooleanVar(value=project.show_both)
            show_cb = ttk.Checkbutton(main_editor, text=tr("show_both"), variable=show_var)
            show_cb.grid(row=4, column=0, columnspan=2, padx=padx_val, pady=pady_val)
            show_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            show_status_label.grid(row=4, column=2, padx=3, pady=pady_val)

            def update_show_status():
                if STATUS_MONITOR:
                    show_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    show_status_label.config(text="")
            show_var.trace("w", lambda *args: update_show_status())
            update_show_status()

            # 自适应字体
            auto_font_var = tk.BooleanVar(value=project.auto_font)
            auto_font_cb = ttk.Checkbutton(main_editor, text=tr("auto_font"), variable=auto_font_var)
            auto_font_cb.grid(row=5, column=0, columnspan=2, padx=padx_val, pady=pady_val)
            auto_font_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            auto_font_status_label.grid(row=5, column=2, padx=3, pady=pady_val)

            def update_auto_font_status():
                if STATUS_MONITOR:
                    auto_font_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    auto_font_status_label.config(text="")
            auto_font_var.trace("w", lambda *args: update_auto_font_status())
            update_auto_font_status()

            # 透明度
            alpha_frame = ttk.Frame(main_editor)
            alpha_frame.grid(row=6, column=0, columnspan=2, padx=padx_val, pady=pady_val, sticky='w')

            ttk.Label(alpha_frame, text=tr("window_alpha") + ":").pack(side=tk.LEFT, padx=(0, 10))
            alpha_var = tk.DoubleVar(value=project.window_alpha)
            alpha_scale = ttk.Scale(alpha_frame, from_=0.3, to=1.0, variable=alpha_var, length=150, orient=tk.HORIZONTAL)
            alpha_scale.pack(side=tk.LEFT, padx=(0, 10))
            alpha_label = ttk.Label(alpha_frame, text=f"{alpha_var.get():.2f}")
            alpha_label.pack(side=tk.LEFT)

            alpha_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            alpha_status_label.grid(row=6, column=2, padx=3, pady=pady_val)

            def update_alpha_label(*args):
                alpha_label.config(text=f"{alpha_var.get():.2f}")
                if STATUS_MONITOR:
                    alpha_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    alpha_status_label.config(text="")
            alpha_var.trace("w", update_alpha_label)
            update_alpha_label()

            # 字体大小
            font_frame = ttk.Frame(main_editor)
            font_frame.grid(row=7, column=0, columnspan=2, padx=padx_val, pady=pady_val, sticky='w')

            ttk.Label(font_frame, text=tr("font_size") + ":").pack(side=tk.LEFT, padx=(0, 10))
            font_var = tk.IntVar(value=project.font_size)
            font_spin = ttk.Spinbox(font_frame, from_=8, to=24, width=5, textvariable=font_var)
            font_spin.pack(side=tk.LEFT)
            ttk.Label(font_frame, text="(建议值: 12-18)" if CURRENT_LANG == LANG_CHINESE else "(Recommended: 12-18)").pack(side=tk.LEFT, padx=(10, 0))

            font_size_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            font_size_status_label.grid(row=7, column=2, padx=3, pady=pady_val)

            def update_font_size_status():
                if STATUS_MONITOR:
                    font_size_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    font_size_status_label.config(text="")
            font_var.trace("w", lambda *args: update_font_size_status())
            update_font_size_status()

            def toggle_font_spin():
                if auto_font_var.get():
                    font_spin.config(state=tk.DISABLED)
                else:
                    font_spin.config(state=tk.NORMAL)
            auto_font_var.trace("w", lambda *args: toggle_font_spin())
            toggle_font_spin()

            # 预设按钮
            preset_frame = ttk.Frame(main_editor)
            preset_frame.grid(row=8, column=0, columnspan=2, padx=padx_val, pady=pady_val, sticky='w')

            def apply_preset():
                try:
                    preset_image_path = os.path.join(self.data_dir, "ys1.jpg")
                    if not os.path.exists(preset_image_path):
                        messagebox.showerror(tr("settings_title"),
                                             "预设图片不存在！请确保data目录下存在ys1.jpg文件" if CURRENT_LANG == LANG_CHINESE else "Preset image not found! Please ensure ys1.jpg exists in data folder")
                        return
                    bg_type_var.set("image")
                    toggle_bg_settings()
                    image_var.set("ys1.jpg")
                    update_preview()
                    font_family_var.set("华文楷体")
                    self.global_font = "华文楷体"
                    project.background_type = "image"
                    project.background_image = "ys1.jpg"
                    self.save_config(force=True)
                    messagebox.showinfo(tr("settings_title"), tr("preset_apply") + " " + (
                        "已应用，请重启应用以生效" if CURRENT_LANG == LANG_CHINESE else "applied, please restart to take effect"))
                    editor.destroy()
                except Exception as e:
                    messagebox.showerror(tr("settings_title"),
                                         f"应用预设时出错: {e}" if CURRENT_LANG == LANG_CHINESE else f"Error applying preset: {e}")
            ttk.Button(preset_frame, text=tr("preset_apply"), command=apply_preset).pack(side=tk.LEFT, padx=(0, 10))

            # 背景类型
            bg_type_frame = ttk.LabelFrame(main_editor, text=tr("background_type"), padding=10)
            bg_type_frame.grid(row=9, column=0, columnspan=2, padx=padx_val, pady=pady_val, sticky='we')

            bg_type_var = tk.StringVar(value=project.background_type)
            bg_type_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            bg_type_status_label.grid(row=9, column=2, padx=3, pady=pady_val)

            def toggle_bg_settings():
                if bg_type_var.get() == "color":
                    bg_frame.pack(fill=tk.X, pady=5)
                    image_frame.pack_forget()
                else:
                    bg_frame.pack_forget()
                    image_frame.pack(fill=tk.X, pady=5)
                if STATUS_MONITOR:
                    bg_type_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    bg_type_status_label.config(text="")
            ttk.Radiobutton(bg_type_frame, text=tr("color_bg"), variable=bg_type_var, value="color", command=toggle_bg_settings).pack(anchor='w', padx=5, pady=2)
            ttk.Radiobutton(bg_type_frame, text=tr("image_bg"), variable=bg_type_var, value="image", command=toggle_bg_settings).pack(anchor='w', padx=5, pady=2)

            color_frame = ttk.LabelFrame(main_editor, text=tr("bg_color"), padding=15)
            color_frame.grid(row=10, column=0, columnspan=2, padx=padx_val, pady=pady_val, sticky='we')

            bg_frame = ttk.Frame(color_frame)
            if project.background_type == "color":
                bg_frame.pack(fill=tk.X, pady=5)

            ttk.Label(bg_frame, text=tr("bg_color") + ":").pack(side=tk.LEFT, padx=(0, 10))
            bg_var = tk.StringVar(value=project.bg_color)

            def choose_bg_color():
                color = colorchooser.askcolor(title=tr("choose_bg_color"), initialcolor=bg_var.get())
                if color and color[1]:
                    bg_var.set(color[1])
                    bg_preview.config(bg=color[1])
                    if STATUS_MONITOR:
                        bg_color_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
            bg_preview = tk.Label(bg_frame, width=10, height=2, bg=project.bg_color, relief=tk.SOLID, borderwidth=1)
            bg_preview.pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(bg_frame, text=tr("choose_bg_color"), command=choose_bg_color, style="TButton", width=12).pack(side=tk.LEFT)

            bg_color_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            bg_color_status_label.grid(row=10, column=2, padx=3, pady=pady_val)

            def update_bg_color_status():
                if STATUS_MONITOR:
                    bg_color_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    bg_color_status_label.config(text="")
            bg_var.trace("w", lambda *args: update_bg_color_status())
            update_bg_color_status()

            image_frame = ttk.Frame(color_frame)
            if project.background_type == "image":
                image_frame.pack(fill=tk.X, pady=5)
            else:
                image_frame.pack_forget()

            image_files = [f for f in os.listdir(self.user_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]

            ttk.Label(image_frame, text=tr("select_image") + ":").pack(side=tk.LEFT, padx=(0, 10))

            image_var = tk.StringVar(value=project.background_image if project.background_image in image_files else "")

            preview_label = tk.Label(image_frame, bg="#f0f0f0", relief=tk.SOLID, width=10, height=3)
            preview_label.pack(side=tk.LEFT, padx=(0, 10))

            bg_image_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            bg_image_status_label.grid(row=10, column=2, padx=3, pady=pady_val)

            def update_preview():
                if image_var.get():
                    image_path = os.path.join(self.user_dir, image_var.get())
                    try:
                        img = Image.open(image_path)
                        preview_img = img.copy()
                        preview_img.thumbnail((150, 100), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(preview_img)
                        preview_label.config(image=photo)
                        preview_label.image = photo
                        if STATUS_MONITOR:
                            bg_image_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                    except:
                        preview_label.config(image="", text="预览失败" if CURRENT_LANG == LANG_CHINESE else "Preview failed")
                        if STATUS_MONITOR:
                            bg_image_status_label.config(text="设置失败" if CURRENT_LANG == LANG_CHINESE else "Failed", foreground="#e74c3c")
                else:
                    preview_label.config(image="", text="无图片" if CURRENT_LANG == LANG_CHINESE else "No image")
                    if STATUS_MONITOR:
                        bg_image_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")

            image_combo = ttk.Combobox(image_frame, textvariable=image_var, width=15, state="readonly")
            image_combo['values'] = image_files
            image_combo.pack(side=tk.LEFT, padx=(0, 10))
            image_combo.bind("<<ComboboxSelected>>", lambda e: update_preview())

            def upload_image():
                filetypes = ((tr("select_image"), "*.jpg *.jpeg *.png *.gif *.bmp"), ("All files", "*.*"))
                file_path = filedialog.askopenfilename(title=tr("upload_image"), filetypes=filetypes)
                if file_path:
                    filename = os.path.basename(file_path)
                    dest_path = os.path.join(self.user_dir, filename)
                    counter = 1
                    base, ext = os.path.splitext(filename)
                    while os.path.exists(dest_path):
                        filename = f"{base}_{counter}{ext}"
                        dest_path = os.path.join(self.user_dir, filename)
                        counter += 1
                    try:
                        import shutil
                        shutil.copy(file_path, dest_path)
                        image_files.append(filename)
                        image_combo['values'] = image_files
                        image_var.set(filename)
                        update_preview()
                    except Exception as e:
                        messagebox.showerror(tr("settings_title"),
                                             f"上传图片失败: {e}" if CURRENT_LANG == LANG_CHINESE else f"Upload failed: {e}")
            ttk.Button(image_frame, text=tr("upload_image"), command=upload_image, width=12).pack(side=tk.LEFT, padx=(0, 10))

            update_preview()

            font_family_frame = ttk.Frame(color_frame)
            font_family_frame.pack(fill=tk.X, pady=5)

            ttk.Label(font_family_frame, text=tr("global_font") + ":").pack(side=tk.LEFT, padx=(0, 10))
            font_family_var = tk.StringVar(value=self.global_font)
            font_family_combo = ttk.Combobox(font_family_frame, textvariable=font_family_var,
                                             values=self.available_fonts, state="readonly", width=12)
            font_family_combo.pack(side=tk.LEFT, padx=(0, 10))

            font_family_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            font_family_status_label.grid(row=10, column=2, padx=3, pady=pady_val)

            def update_font_family_status():
                if STATUS_MONITOR:
                    font_family_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    font_family_status_label.config(text="")
            font_family_var.trace("w", lambda *args: update_font_family_status())
            update_font_family_status()

            font_color_frame = ttk.Frame(color_frame)
            font_color_frame.pack(fill=tk.X, pady=5)

            ttk.Label(font_color_frame, text=tr("font_color") + ":").pack(side=tk.LEFT, padx=(0, 10))
            font_color_var = tk.StringVar(value=project.font_color)

            def choose_font_color():
                color = colorchooser.askcolor(title=tr("choose_font_color"), initialcolor=font_color_var.get())
                if color and color[1]:
                    font_color_var.set(color[1])
                    font_color_preview.config(bg=color[1])
                    if STATUS_MONITOR:
                        font_color_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
            font_color_preview = tk.Label(font_color_frame, width=10, height=2, bg=project.font_color, relief=tk.SOLID, borderwidth=1)
            font_color_preview.pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(font_color_frame, text=tr("choose_font_color"), command=choose_font_color, style="TButton", width=12).pack(side=tk.LEFT)

            font_color_status_label = ttk.Label(main_editor, text="", font=("微软雅黑", 7))
            font_color_status_label.grid(row=10, column=2, padx=3, pady=pady_val)

            def update_font_color_status():
                if STATUS_MONITOR:
                    font_color_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success", foreground="#2ecc71")
                else:
                    font_color_status_label.config(text="")
            font_color_var.trace("w", lambda *args: update_font_color_status())
            update_font_color_status()

            btn_frame_editor = ttk.Frame(main_editor)
            btn_frame_editor.grid(row=11, column=0, columnspan=2, pady=15)

            def save_changes():
                if not validate_date(date_var.get()):
                    messagebox.showerror(tr("settings_title"),
                                         "日期格式无效！请使用YYYY-MM-DD格式" if CURRENT_LANG == LANG_CHINESE else "Invalid date format! Use YYYY-MM-DD")
                    return
                if exact_time_var.get() and not validate_time(time_var.get()):
                    messagebox.showerror(tr("settings_title"),
                                         "时间格式无效！请使用HH:MM格式" if CURRENT_LANG == LANG_CHINESE else "Invalid time format! Use HH:MM")
                    return
                old_name = project.name
                project.name = name_var.get()
                project.target_date = date_var.get()
                project.target_time = time_var.get() if exact_time_var.get() else "00:00"
                project.show_both = show_var.get()
                project.font_size = font_var.get()
                project.bg_color = bg_var.get()
                project.font_color = font_color_var.get()
                project.auto_font = auto_font_var.get()
                project.window_alpha = alpha_var.get()

                background_changed = False
                if bg_type_var.get() != project.background_type:
                    background_changed = True
                project.background_type = bg_type_var.get()
                if bg_type_var.get() == "image":
                    project.background_image = image_var.get()
                else:
                    project.background_image = ""

                projects_listbox.delete(index)
                projects_listbox.insert(index, f"{index + 1}. {project.name} ({project.target_date})")

                self.editor_geometry = editor.geometry()
                self.save_config(force=True)

                if background_changed and bg_type_var.get() == "image":
                    messagebox.showinfo(tr("settings_title"),
                                        "背景类型已从纯色改为图片，需要重启应用才能生效。请手动重启应用程序。" if CURRENT_LANG == LANG_CHINESE else "Background type changed from color to image, restart required.")
                    editor.destroy()
                    return

                editor.destroy()
                self.save_config(force=True)

                if index < len(self.windows):
                    try:
                        self.windows[index].refresh()
                    except Exception as e:
                        try:
                            self.windows[index].destroy()
                            self.windows[index] = CountdownWindow(self, project, index)
                        except:
                            pass

            ttk.Button(btn_frame_editor, text=tr("save"), command=save_changes, width=15, style="Primary.TButton").pack(pady=5, ipady=3)
            ttk.Button(btn_frame_editor, text=tr("cancel"), command=on_editor_close, width=15, style="TButton").pack(pady=5, ipady=3)

            toggle_bg_settings()
            validate_date_entry()

        ttk.Button(btn_frame, text=tr("add_project"), command=add_project, style="Primary.TButton", width=15).pack(
            side=tk.LEFT, padx=5, ipady=3)
        ttk.Button(btn_frame, text=tr("edit_project"), command=edit_project, style="Primary.TButton", width=15).pack(
            side=tk.LEFT, padx=5, ipady=3)
        ttk.Button(btn_frame, text=tr("delete_project"), command=remove_project, style="Primary.TButton",
                   width=15).pack(side=tk.LEFT, padx=5, ipady=3)

        # ---------- 全局设置选项卡 ----------
        global_frame = ttk.Frame(notebook, padding=10)
        notebook.add(global_frame, text=tr("global_settings"))

        global_frame.columnconfigure(0, weight=1)
        global_frame.columnconfigure(1, weight=1)

        font_setting_frame = ttk.LabelFrame(global_frame, text=tr("global_font"), padding=10)
        font_setting_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="we")
        ttk.Label(font_setting_frame, text=tr("global_font") + ":").pack(side=tk.LEFT, padx=(0, 10))
        font_var = tk.StringVar(value=self.global_font)
        font_combo = ttk.Combobox(font_setting_frame, textvariable=font_var, values=self.available_fonts,
                                  state="readonly", width=12)
        font_combo.pack(side=tk.LEFT, padx=(0, 10))

        def apply_font():
            self.global_font = font_var.get()
            self.save_config(force=True)
            self.apply_global_font()

        ttk.Button(font_setting_frame, text=tr("apply_font"), command=apply_font).pack(side=tk.LEFT, padx=(0, 10))
        font_status_label = ttk.Label(font_setting_frame, text="", font=("微软雅黑", 7))
        font_status_label.pack(side=tk.LEFT, padx=(10, 0))

        def update_font_status():
            if STATUS_MONITOR:
                font_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success",
                                         foreground="#2ecc71")
            else:
                font_status_label.config(text="")

        font_var.trace("w", lambda *args: update_font_status())
        update_font_status()

        status_monitor_frame = ttk.LabelFrame(global_frame, text=tr("status_monitor"), padding=10)
        status_monitor_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="we")
        status_monitor_var = tk.BooleanVar(value=STATUS_MONITOR)
        status_monitor_cb = ttk.Checkbutton(status_monitor_frame, text=tr("status_monitor"),
                                            variable=status_monitor_var, style="TCheckbutton")
        status_monitor_cb.pack(anchor='w', padx=10, pady=5)

        def toggle_status_monitor():
            global STATUS_MONITOR
            new_value = status_monitor_var.get()
            if new_value != STATUS_MONITOR:
                STATUS_MONITOR = new_value
                self.save_config(force=True)
                messagebox.showinfo(tr("settings_title"),
                                    "状态监控设置已更改，需要重启应用才能生效。" if CURRENT_LANG == LANG_CHINESE else "Status monitor changed, restart required.")

        status_monitor_var.trace("w", lambda *args: toggle_status_monitor())

        auto_start_frame = ttk.LabelFrame(global_frame, text=tr("auto_start"), padding=10)
        auto_start_frame.grid(row=2, column=0, padx=10, pady=10, sticky="we")
        auto_start_var = tk.BooleanVar(value=self.auto_start)
        auto_start_cb = tk.Checkbutton(auto_start_frame, text=tr("auto_start"), variable=auto_start_var,
               bg=self.theme.frame_bg, fg=self.theme.text_color,
               activebackground=self.theme.accent_color, activeforeground="#ffffff",
               selectcolor=self.theme.frame_bg)
        auto_start_cb.pack(anchor='w', padx=10, pady=5)
        auto_start_status_label = ttk.Label(auto_start_frame, text="", font=("微软雅黑", 7))
        auto_start_status_label.pack(anchor='w', padx=10, pady=2)

        def update_auto_start_status():
            if STATUS_MONITOR:
                auto_start_status, auto_start_color = self.set_auto_start_with_retry(auto_start_var.get())
                auto_start_status_label.config(text=auto_start_status, foreground=auto_start_color)
            else:
                auto_start_status_label.config(text="")

        auto_start_var.trace("w", lambda *args: update_auto_start_status())
        update_auto_start_status()

        poem_frame = ttk.LabelFrame(global_frame, text=tr("daily_poem"), padding=10)
        poem_frame.grid(row=2, column=1, padx=10, pady=10, sticky="we")
        poem_level_var = tk.StringVar(value=self.poem_level)
        poem_options = [(tr("none"), "none"), (tr("primary"), "primary"), (tr("junior"), "junior"),
                        (tr("senior"), "senior")]
        for text, value in poem_options:
            ttk.Radiobutton(poem_frame, text=text, variable=poem_level_var, value=value, style="TCheckbutton").pack(
                anchor='w', padx=10, pady=2)
        poem_status_label = ttk.Label(poem_frame, text="", font=("微软雅黑", 7))
        poem_status_label.pack(anchor='w', padx=10, pady=2)

        def update_poem_status():
            if STATUS_MONITOR:
                poem_status_label.config(text="设置成功" if CURRENT_LANG == LANG_CHINESE else "Success",
                                         foreground="#2ecc71")
            else:
                poem_status_label.config(text="")

        poem_level_var.trace("w", lambda *args: update_poem_status())
        update_poem_status()

        lang_frame = ttk.LabelFrame(global_frame, text=tr("language"), padding=10)
        lang_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="we")
        lang_var = tk.StringVar(value=CURRENT_LANG)
        lang_cb_chinese = ttk.Radiobutton(lang_frame, text=tr("chinese"), variable=lang_var, value=LANG_CHINESE)
        lang_cb_chinese.pack(side=tk.LEFT, padx=5)
        lang_cb_english = ttk.Radiobutton(lang_frame, text=tr("english"), variable=lang_var, value=LANG_ENGLISH)
        lang_cb_english.pack(side=tk.LEFT, padx=5)

        def on_lang_change(*args):
            global CURRENT_LANG
            new_lang = lang_var.get()
            if new_lang != CURRENT_LANG:
                old_lang = CURRENT_LANG
                CURRENT_LANG = new_lang
                self.save_config(force=True)
                self.plugin_manager.trigger_event("on_language_change", old_lang, new_lang)
                messagebox.showinfo(tr("settings_title"),
                                    "语言已更改，需要重启应用才能完全生效。" if CURRENT_LANG == LANG_CHINESE else "Language changed, restart to take full effect.")

        lang_var.trace("w", on_lang_change)

        info_frame = ttk.LabelFrame(global_frame, text=tr("software_info"), padding=10)
        info_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky="we")
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(info_grid, text=tr("version") + ":", font=("微软雅黑", 10, "bold")).grid(row=0, column=0, sticky='w',
                                                                                           padx=(0, 10), pady=2)
        ttk.Label(info_grid, text=f"v{self.current_version}", font=("微软雅黑", 10)).grid(row=0, column=1, sticky='w',
                                                                                          pady=2)
        ttk.Label(info_grid, text=tr("kernel_version") + ":", font=("微软雅黑", 10, "bold")).grid(row=1, column=0,
                                                                                                  sticky='w',
                                                                                                  padx=(0, 10), pady=2)
        ttk.Label(info_grid, text=f"Python {self.python_version}", font=("微软雅黑", 10)).grid(row=1, column=1,
                                                                                               sticky='w', pady=2)
        ttk.Label(info_grid, text=tr("software_dir") + ":", font=("微软雅黑", 10, "bold")).grid(row=2, column=0,
                                                                                                sticky='w',
                                                                                                padx=(0, 10), pady=2)
        ttk.Label(info_grid, text=self.current_dir, font=("微软雅黑", 10)).grid(row=2, column=1, sticky='w', pady=2)
        ttk.Label(info_grid, text=tr("data_dir") + ":", font=("微软雅黑", 10, "bold")).grid(row=3, column=0, sticky='w',
                                                                                            padx=(0, 10), pady=2)
        ttk.Label(info_grid, text=self.data_dir, font=("微软雅黑", 10)).grid(row=3, column=1, sticky='w', pady=2)
        ttk.Label(info_grid, text=tr("user_image_dir") + ":", font=("微软雅黑", 10, "bold")).grid(row=4, column=0,
                                                                                                  sticky='w',
                                                                                                  padx=(0, 10), pady=2)
        ttk.Label(info_grid, text=self.user_dir, font=("微软雅黑", 10)).grid(row=4, column=1, sticky='w', pady=2)
        ttk.Label(info_grid, text=tr("author") + ":", font=("微软雅黑", 10, "bold")).grid(row=5, column=0, sticky='w',
                                                                                          padx=(0, 10), pady=2)
        ttk.Label(info_grid, text="苗睿轩", font=("微软雅黑", 10)).grid(row=5, column=1, sticky='w', pady=2)

        action_frame = ttk.Frame(global_frame)
        action_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=10, sticky="we")

        def open_help_in_settings():
            notebook.select(notebook.index("end") - 1)

        def check_update():
            webbrowser.open("https://www.123912.com/s/tM3gjv-9rwJA")

        ttk.Button(action_frame, text=tr("help"), command=open_help_in_settings, style="Primary.TButton",
                   width=15).pack(side=tk.LEFT, padx=5, ipady=3)
        ttk.Button(action_frame, text=tr("check_update"), command=check_update, style="Primary.TButton", width=15).pack(
            side=tk.LEFT, padx=5, ipady=3)

        # ---------- 高级选项卡 ----------
        advanced_frame = ttk.Frame(notebook, padding=10)
        notebook.add(advanced_frame, text=tr("advanced"))

        safety_label = ttk.Label(advanced_frame, text="⚠️ 请谨慎安装来源不明的插件，可能存在安全风险。", foreground="red",
                                 font=("微软雅黑", 9, "bold"))
        safety_label.pack(anchor='w', padx=10, pady=(5, 0))

        global_sec_frame = ttk.LabelFrame(advanced_frame, text="全局安全设置", padding=5)
        global_sec_frame.pack(fill=tk.X, padx=5, pady=5)

        global_disable_var = tk.BooleanVar(value=self.global_disable_all_plugins)

        def toggle_global_disable():
            self.toggle_global_disable_plugins(global_disable_var.get())

        ttk.Checkbutton(global_sec_frame, text="全局禁用所有插件", variable=global_disable_var,
                        command=toggle_global_disable).pack(anchor='w')

        prompt_var = tk.BooleanVar(value=self.plugin_prompt_on_deny)

        def toggle_prompt():
            self.plugin_prompt_on_deny = prompt_var.get()
            self.save_config()

        ttk.Checkbutton(global_sec_frame, text="权限不足时询问用户", variable=prompt_var, command=toggle_prompt).pack(
            anchor='w')

        monitor_frame = ttk.Frame(advanced_frame)
        monitor_frame.pack(fill=tk.X, padx=5, pady=2)
        monitor_var = tk.BooleanVar(value=self.plugin_monitor)

        def toggle_monitor():
            self.plugin_monitor = monitor_var.get()
            self.save_config(force=True)

        monitor_cb = ttk.Checkbutton(monitor_frame, text="启用插件行为监控（捕获异常时询问禁用）", variable=monitor_var,
                                     command=toggle_monitor)
        monitor_cb.pack(anchor='w')

        plugin_list_frame = ttk.LabelFrame(advanced_frame, text=tr("plugin_list"), padding=10)
        plugin_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("name", "version", "author", "status", "permissions")
        tree = ttk.Treeview(plugin_list_frame, columns=columns, show="headings", height=5)
        tree.heading("name", text=tr("plugin_name"))
        tree.heading("version", text=tr("plugin_version"))
        tree.heading("author", text=tr("plugin_author"))
        tree.heading("status", text=tr("plugin_status"))
        tree.heading("permissions", text="权限")
        tree.column("name", width=120)
        tree.column("version", width=60)
        tree.column("author", width=80)
        tree.column("status", width=70)
        tree.column("permissions", width=80)

        scrollbar = ttk.Scrollbar(plugin_list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        plugin_items = {}
        for plugin in self.plugin_manager.plugins:
            risk = self.plugin_manager.get_plugin_risk(plugin)
            name_display = plugin.name + (" ⚠️" if risk > 0 else "")
            status_text = "启用" if plugin.enabled else "禁用" if CURRENT_LANG == LANG_CHINESE else (
                "Enabled" if plugin.enabled else "Disabled")
            if risk == 2:
                status_text += " [危险]" if CURRENT_LANG == LANG_CHINESE else " [Danger]"
            elif risk == 1:
                status_text += " [风险]" if CURRENT_LANG == LANG_CHINESE else " [Risk]"
            perm_text = ""
            if plugin.permissions & PluginPermission.FILE_READ: perm_text += "R"
            if plugin.permissions & PluginPermission.FILE_WRITE: perm_text += "W"
            if plugin.permissions & PluginPermission.NETWORK: perm_text += "N"
            if plugin.permissions & PluginPermission.COMMAND: perm_text += "C"
            if not perm_text: perm_text = "无"
            item = tree.insert("", tk.END, values=(name_display, plugin.version, plugin.author, status_text, perm_text))
            plugin_items[item] = plugin

        self._settings_tree = tree
        self._settings_plugin_items = plugin_items

        plugin_btn_frame = ttk.Frame(advanced_frame)
        plugin_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        def enable_plugin():
            selected = tree.selection()
            if not selected: return
            item = selected[0]
            plugin = plugin_items[item]
            if not plugin.enabled:
                risk = self.plugin_manager.get_plugin_risk(plugin)
                if risk >= 2:
                    msg = f"插件“{plugin.name}”被检测为高风险插件，可能包含危险操作。\n是否自动启用限制模式？(推荐)"
                    limited = messagebox.askyesno("安全建议", msg, default=messagebox.YES)
                    if not self.plugin_manager.enable_plugin(plugin, force=True, limited=limited):
                        return
                else:
                    if not self.plugin_manager.enable_plugin(plugin):
                        return
                status_text = "启用" if CURRENT_LANG == LANG_CHINESE else "Enabled"
                if risk == 2:
                    status_text += " [危险]" if CURRENT_LANG == LANG_CHINESE else " [Danger]"
                elif risk == 1:
                    status_text += " [风险]" if CURRENT_LANG == LANG_CHINESE else " [Risk]"
                tree.item(item, values=(plugin.name + (" ⚠️" if risk > 0 else ""),
                                        plugin.version, plugin.author, status_text,
                                        tree.item(item, 'values')[4]))
                refresh_plugin_settings_combo()

        def disable_plugin():
            selected = tree.selection()
            if not selected: return
            item = selected[0]
            plugin = plugin_items[item]
            if plugin.enabled:
                if self.plugin_manager.disable_plugin(plugin):
                    status_text = "禁用" if CURRENT_LANG == LANG_CHINESE else "Disabled"
                    risk = self.plugin_manager.get_plugin_risk(plugin)
                    if risk == 2:
                        status_text += " [危险]" if CURRENT_LANG == LANG_CHINESE else " [Danger]"
                    elif risk == 1:
                        status_text += " [风险]" if CURRENT_LANG == LANG_CHINESE else " [Risk]"
                    tree.item(item, values=(plugin.name + (" ⚠️" if risk > 0 else ""),
                                            plugin.version, plugin.author, status_text,
                                            tree.item(item, 'values')[4]))
                    refresh_plugin_settings_combo()

        ttk.Button(plugin_btn_frame, text=tr("enable"), command=enable_plugin, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(plugin_btn_frame, text=tr("disable"), command=disable_plugin, width=12).pack(side=tk.LEFT, padx=2)

        def reload_plugins():
            self.plugin_manager = PluginManager(self)
            for item in tree.get_children():
                tree.delete(item)
            plugin_items.clear()
            for plugin in self.plugin_manager.plugins:
                risk = self.plugin_manager.get_plugin_risk(plugin)
                name_display = plugin.name + (" ⚠️" if risk > 0 else "")
                status_text = "启用" if plugin.enabled else "禁用" if CURRENT_LANG == LANG_CHINESE else (
                    "Enabled" if plugin.enabled else "Disabled")
                if risk == 2:
                    status_text += " [危险]" if CURRENT_LANG == LANG_CHINESE else " [Danger]"
                elif risk == 1:
                    status_text += " [风险]" if CURRENT_LANG == LANG_CHINESE else " [Risk]"
                perm_text = ""
                if plugin.permissions & PluginPermission.FILE_READ: perm_text += "R"
                if plugin.permissions & PluginPermission.FILE_WRITE: perm_text += "W"
                if plugin.permissions & PluginPermission.NETWORK: perm_text += "N"
                if plugin.permissions & PluginPermission.COMMAND: perm_text += "C"
                if not perm_text: perm_text = "无"
                item = tree.insert("", tk.END,
                                   values=(name_display, plugin.version, plugin.author, status_text, perm_text))
                plugin_items[item] = plugin
            refresh_plugin_settings_combo()
            log_message("插件列表已刷新", "INFO")

        ttk.Button(plugin_btn_frame, text=tr("reload_plugins"), command=reload_plugins, width=12).pack(side=tk.LEFT,
                                                                                                       padx=2)

        def open_plugin_folder():
            if sys.platform == "win32":
                os.startfile(self.plugin_manager.plugin_dir)
            else:
                messagebox.showinfo(tr("advanced"),
                                    f"插件目录: {self.plugin_manager.plugin_dir}" if CURRENT_LANG == LANG_CHINESE else f"Plugin folder: {self.plugin_manager.plugin_dir}")

        ttk.Button(plugin_btn_frame, text=tr("open_plugin_folder"), command=open_plugin_folder, width=12).pack(
            side=tk.LEFT, padx=2)

        def manage_permissions():
            selected = tree.selection()
            if not selected: return
            item = selected[0]
            plugin = plugin_items[item]
            perm_dialog = tk.Toplevel(settings)
            perm_dialog.title(f"权限管理 - {plugin.name}")
            perm_dialog.geometry("400x380")
            perm_dialog.resizable(False, False)
            perm_dialog.grab_set()

            perms = plugin.permissions
            var_read = tk.BooleanVar(value=bool(perms & PluginPermission.FILE_READ))
            var_write = tk.BooleanVar(value=bool(perms & PluginPermission.FILE_WRITE))
            var_net = tk.BooleanVar(value=bool(perms & PluginPermission.NETWORK))
            var_cmd = tk.BooleanVar(value=bool(perms & PluginPermission.COMMAND))

            tk.Label(perm_dialog, text="选择允许的操作：").pack(pady=5)
            tk.Checkbutton(perm_dialog, text="读取文件", variable=var_read).pack(anchor='w', padx=20)
            tk.Checkbutton(perm_dialog, text="写入文件", variable=var_write).pack(anchor='w', padx=20)
            tk.Checkbutton(perm_dialog, text="网络连接", variable=var_net).pack(anchor='w', padx=20)
            tk.Checkbutton(perm_dialog, text="执行系统命令", variable=var_cmd).pack(anchor='w', padx=20)

            def save_perms():
                new_perms = PluginPermission.NONE
                if var_read.get(): new_perms |= PluginPermission.FILE_READ
                if var_write.get(): new_perms |= PluginPermission.FILE_WRITE
                if var_net.get(): new_perms |= PluginPermission.NETWORK
                if var_cmd.get(): new_perms |= PluginPermission.COMMAND
                self.plugin_manager.set_plugin_permissions(plugin, new_perms)
                perm_text = ""
                if new_perms & PluginPermission.FILE_READ: perm_text += "R"
                if new_perms & PluginPermission.FILE_WRITE: perm_text += "W"
                if new_perms & PluginPermission.NETWORK: perm_text += "N"
                if new_perms & PluginPermission.COMMAND: perm_text += "C"
                if not perm_text: perm_text = "无"
                current_values = list(tree.item(item, 'values'))
                current_values[4] = perm_text
                tree.item(item, values=current_values)
                perm_dialog.destroy()

            tk.Button(perm_dialog, text="保存", command=save_perms, bg="#3498db", fg="white", width=10).pack(pady=10)
            tk.Button(perm_dialog, text="取消", command=perm_dialog.destroy, width=10).pack()

        ttk.Button(plugin_btn_frame, text="权限管理", command=manage_permissions, width=12).pack(side=tk.LEFT, padx=2)

        log_frame = ttk.LabelFrame(advanced_frame, text=tr("plugin_log"), padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        log_text = scrolledtext.ScrolledText(log_frame, height=6, font=("Consolas", 8), wrap=tk.WORD)
        log_text.pack(fill=tk.BOTH, expand=True)

        def update_log_display():
            if not log_text.winfo_exists():
                return
            log_text.delete(1.0, tk.END)
            all_logs = []
            for plugin in self.plugin_manager.plugins:
                for entry in plugin.log[-30:]:
                    all_logs.append(f"[{plugin.name}] {entry}")
            all_logs.sort()
            for line in all_logs[-150:]:
                log_text.insert(tk.END, line + "\n")
            log_text.see(tk.END)
            self.after(5000, update_log_display)

        update_log_display()

        plugin_settings_frame = ttk.LabelFrame(advanced_frame,
                                               text="插件设置" if CURRENT_LANG == LANG_CHINESE else "Plugin Settings",
                                               padding=10)
        plugin_settings_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def load_plugin_settings(plugin, parent_frame):
            for w in parent_frame.winfo_children():
                w.destroy()
            if hasattr(plugin, "on_settings_open"):
                try:
                    frame = plugin.on_settings_open(parent_frame)
                    if frame and isinstance(frame, tk.Frame):
                        frame.pack(fill=tk.BOTH, expand=True)
                except Exception as e:
                    log_message(f"插件 {plugin.name} on_settings_open 出错: {e}", "ERROR")
                    ttk.Label(parent_frame, text=f"加载设置失败: {e}", foreground="red").pack()

        def refresh_plugin_settings_combo():
            for widget in plugin_settings_frame.winfo_children():
                widget.destroy()
            enabled_plugins = self.plugin_manager.get_enabled_plugins()
            if not enabled_plugins:
                ttk.Label(plugin_settings_frame, text="无已启用插件").pack()
                return
            select_frame = ttk.Frame(plugin_settings_frame)
            select_frame.pack(fill=tk.X, pady=2)
            ttk.Label(select_frame, text="选择插件:").pack(side=tk.LEFT)
            plugin_var = tk.StringVar()
            plugin_names = [p.name for p in enabled_plugins]
            plugin_combo = ttk.Combobox(select_frame, textvariable=plugin_var,
                                        values=plugin_names, state="readonly", width=20)
            plugin_combo.pack(side=tk.LEFT, padx=5)
            content_frame = ttk.Frame(plugin_settings_frame)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            def on_plugin_select(*args):
                selected_name = plugin_var.get()
                for p in enabled_plugins:
                    if p.name == selected_name:
                        load_plugin_settings(p, content_frame)
                        break

            plugin_var.trace('w', on_plugin_select)
            if enabled_plugins:
                plugin_combo.current(0)
                load_plugin_settings(enabled_plugins[0], content_frame)

        refresh_plugin_settings_combo()

        def show_plugin_docs():
            doc_window = tk.Toplevel(settings)
            doc_window.title(tr("plugin_docs"))
            doc_window.geometry("550x350")
            doc_text = scrolledtext.ScrolledText(doc_window, wrap=tk.WORD, font=("微软雅黑", 9))
            doc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            docs = """# 插件开发指南

        插件应继承 Plugin 类，并可选实现以下方法：

        - on_load(): 插件被加载时调用
        - on_enable(): 插件被启用时调用
        - on_disable(): 插件被禁用时调用
        - on_settings_open(parent): 在设置窗口的“高级”选项卡中添加自定义设置界面，应返回一个Frame
        - on_window_create(window, project): 每次创建倒计时窗口时调用
        - on_window_closed(window, project): 窗口关闭时调用
        - on_tick(): 每分钟调用一次（由主循环触发）
        - on_before_save_config(): 配置即将保存前调用
        - on_after_save_config(): 配置保存成功后调用
        - on_settings_closed(): 设置窗口关闭时调用
        - on_poem_update(new_poem): 每日一诗更新时调用
        - on_language_change(old_lang, new_lang): 语言切换时调用

        插件内可使用 self.log_plugin(message, level) 记录日志。

        插件元数据可通过模块级变量定义：
            __plugin_name__ = "插件名"
            __version__ = "1.0"
            __author__ = "作者"

        示例插件已放在 plugins/example_plugin.py 中。
        """
            doc_text.insert(tk.END, docs)
            doc_text.config(state=tk.DISABLED)
            ttk.Button(doc_window, text=tr("close"), command=doc_window.destroy).pack(pady=5)

        ttk.Button(plugin_btn_frame, text=tr("plugin_docs"), command=show_plugin_docs, width=12).pack(side=tk.LEFT,
                                                                                                      padx=2)

        # ---------- 主题选项卡 ----------
        theme_frame = ttk.Frame(notebook, padding=10)
        notebook.add(theme_frame, text=tr("theme") if CURRENT_LANG == LANG_CHINESE else "Theme")

        select_frame = ttk.Frame(theme_frame)
        select_frame.pack(fill=tk.X, pady=5)
        ttk.Label(select_frame, text=tr("select_theme") + ":").pack(side=tk.LEFT)
        theme_var = tk.StringVar(value=self.current_theme)
        theme_combo = ttk.Combobox(select_frame, textvariable=theme_var,
                                   values=list(BUILTIN_THEMES.keys()) + [t.name for t in self.custom_themes],
                                   state="readonly", width=20)
        theme_combo.pack(side=tk.LEFT, padx=5)
        self._theme_var = theme_var
        self._theme_combo = theme_combo

        preview_frame = ttk.LabelFrame(theme_frame, text=tr("preview"), padding=10)
        preview_frame.pack(fill=tk.X, pady=5)
        preview_canvas = tk.Canvas(preview_frame, width=300, height=100, bg=self.theme.bg_color, highlightthickness=1,
                                   highlightbackground=self.theme.border_color)
        preview_canvas.pack()
        preview_canvas.create_rectangle(10, 10, 100, 90, fill=self.theme.frame_bg, outline=self.theme.border_color)
        preview_canvas.create_rectangle(110, 10, 200, 90, fill=self.theme.accent_color, outline=self.theme.border_color)
        preview_canvas.create_text(55, 50, text="背景", fill=self.theme.text_color)
        preview_canvas.create_text(155, 50, text="强调", fill=self.theme.text_color)

        round_frame = ttk.Frame(theme_frame)
        round_frame.pack(fill=tk.X, pady=5)
        ttk.Label(round_frame, text=tr("window_round_radius") + ":").pack(side=tk.LEFT)
        round_var = tk.IntVar(value=self.theme.window_round_radius)
        round_scale = ttk.Scale(round_frame, from_=0, to=50, variable=round_var, length=200, orient=tk.HORIZONTAL)
        round_scale.pack(side=tk.LEFT, padx=5)
        round_label = ttk.Label(round_frame, text=f"{round_var.get()}px")
        round_label.pack(side=tk.LEFT)

        def update_round_label(*args):
            round_label.config(text=f"{round_var.get()}px")

        round_var.trace('w', update_round_label)

        bright_frame = ttk.Frame(theme_frame)
        bright_frame.pack(fill=tk.X, pady=5)
        ttk.Label(bright_frame, text=tr("brightness") + ":").pack(side=tk.LEFT)
        bright_var = tk.DoubleVar(value=self.theme.window_brightness)
        bright_scale = ttk.Scale(bright_frame, from_=0.5, to=2.0, variable=bright_var, length=200)
        bright_scale.pack(side=tk.LEFT, padx=5)
        bright_label = ttk.Label(bright_frame, text=f"{bright_var.get():.1f}")
        bright_label.pack(side=tk.LEFT)

        def update_bright_label(*args):
            bright_label.config(text=f"{bright_var.get():.1f}")

        bright_var.trace('w', update_bright_label)

        sat_frame = ttk.Frame(theme_frame)
        sat_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sat_frame, text=tr("saturation") + ":").pack(side=tk.LEFT)
        sat_var = tk.DoubleVar(value=self.theme.window_saturation)
        sat_scale = ttk.Scale(sat_frame, from_=0.0, to=2.0, variable=sat_var, length=200)
        sat_scale.pack(side=tk.LEFT, padx=5)
        sat_label = ttk.Label(sat_frame, text=f"{sat_var.get():.1f}")
        sat_label.pack(side=tk.LEFT)

        def update_sat_label(*args):
            sat_label.config(text=f"{sat_var.get():.1f}")

        sat_var.trace('w', update_sat_label)

        custom_edit_frame = ttk.LabelFrame(theme_frame, text=tr("custom_theme_editor"), padding=10)
        custom_edit_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        color_grid = ttk.Frame(custom_edit_frame)
        color_grid.pack(fill=tk.X, pady=5)

        row = 0
        ttk.Label(color_grid, text="背景色:").grid(row=row, column=0, sticky='w', padx=5, pady=2)
        bg_color_var = tk.StringVar(value=self.theme.bg_color)
        bg_color_entry = ttk.Entry(color_grid, textvariable=bg_color_var, width=10)
        bg_color_entry.grid(row=row, column=1, padx=5)

        def choose_bg_color_theme():
            color = colorchooser.askcolor(title="选择背景色", initialcolor=bg_color_var.get())
            if color and color[1]:
                bg_color_var.set(color[1])

        ttk.Button(color_grid, text="选择", command=choose_bg_color_theme).grid(row=row, column=2, padx=5)

        row += 1
        ttk.Label(color_grid, text="框架色:").grid(row=row, column=0, sticky='w', padx=5, pady=2)
        frame_bg_var = tk.StringVar(value=self.theme.frame_bg)
        frame_bg_entry = ttk.Entry(color_grid, textvariable=frame_bg_var, width=10)
        frame_bg_entry.grid(row=row, column=1, padx=5)

        def choose_frame_bg():
            color = colorchooser.askcolor(title="选择框架色", initialcolor=frame_bg_var.get())
            if color and color[1]:
                frame_bg_var.set(color[1])

        ttk.Button(color_grid, text="选择", command=choose_frame_bg).grid(row=row, column=2, padx=5)

        row += 1
        ttk.Label(color_grid, text="强调色:").grid(row=row, column=0, sticky='w', padx=5, pady=2)
        accent_color_var = tk.StringVar(value=self.theme.accent_color)
        accent_color_entry = ttk.Entry(color_grid, textvariable=accent_color_var, width=10)
        accent_color_entry.grid(row=row, column=1, padx=5)

        def choose_accent_color():
            color = colorchooser.askcolor(title="选择强调色", initialcolor=accent_color_var.get())
            if color and color[1]:
                accent_color_var.set(color[1])

        ttk.Button(color_grid, text="选择", command=choose_accent_color).grid(row=row, column=2, padx=5)

        row += 1
        ttk.Label(color_grid, text="文字色:").grid(row=row, column=0, sticky='w', padx=5, pady=2)
        text_color_var = tk.StringVar(value=self.theme.text_color)
        text_color_entry = ttk.Entry(color_grid, textvariable=text_color_var, width=10)
        text_color_entry.grid(row=row, column=1, padx=5)

        def choose_text_color():
            color = colorchooser.askcolor(title="选择文字色", initialcolor=text_color_var.get())
            if color and color[1]:
                text_color_var.set(color[1])

        ttk.Button(color_grid, text="选择", command=choose_text_color).grid(row=row, column=2, padx=5)

        row += 1
        ttk.Label(color_grid, text="边框色:").grid(row=row, column=0, sticky='w', padx=5, pady=2)
        border_color_var = tk.StringVar(value=self.theme.border_color)
        border_color_entry = ttk.Entry(color_grid, textvariable=border_color_var, width=10)
        border_color_entry.grid(row=row, column=1, padx=5)

        def choose_border_color():
            color = colorchooser.askcolor(title="选择边框色", initialcolor=border_color_var.get())
            if color and color[1]:
                border_color_var.set(color[1])

        ttk.Button(color_grid, text="选择", command=choose_border_color).grid(row=row, column=2, padx=5)

        font_frame = ttk.Frame(custom_edit_frame)
        font_frame.pack(fill=tk.X, pady=5)
        ttk.Label(font_frame, text="字体:").pack(side=tk.LEFT)
        font_family_var = tk.StringVar(value=self.theme.font_family)
        font_combo = ttk.Combobox(font_frame, textvariable=font_family_var, values=self.available_fonts,
                                  state="readonly", width=12)
        font_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(font_frame, text="字号:").pack(side=tk.LEFT)
        font_size_var = tk.IntVar(value=self.theme.font_size)
        font_size_spin = ttk.Spinbox(font_frame, from_=8, to=20, textvariable=font_size_var, width=5)
        font_size_spin.pack(side=tk.LEFT, padx=5)

        def save_custom_theme():
            name = tk.simpledialog.askstring("新建主题", "请输入主题名称:", parent=settings)
            if not name:
                return
            if name in BUILTIN_THEMES or any(t.name == name for t in self.custom_themes):
                messagebox.showerror("错误", "主题名称已存在，请使用其他名称")
                return
            new_theme = Theme(
                name=name, is_dark=False,
                bg_color=bg_color_var.get(), frame_bg=frame_bg_var.get(),
                accent_color=accent_color_var.get(), text_color=text_color_var.get(),
                border_color=border_color_var.get(), font_family=font_family_var.get(),
                font_size=font_size_var.get(),
                window_round_radius=round_var.get(), window_brightness=bright_var.get(),
                window_saturation=sat_var.get()
            )
            self.custom_themes.append(new_theme)
            theme_combo['values'] = list(BUILTIN_THEMES.keys()) + [t.name for t in self.custom_themes]
            theme_var.set(name)
            self.current_theme = name
            self._apply_theme(name)
            self.save_config(force=True)
            log_message(f"新建自定义主题: {name}", "INFO")
            messagebox.showinfo("主题", "自定义主题已保存并应用")

        ttk.Button(custom_edit_frame, text="保存为新主题", command=save_custom_theme).pack(pady=5)

        delete_theme_btn = ttk.Button(
            custom_edit_frame,
            text=tr("delete_theme"),
            command=self.delete_custom_theme,
            state=tk.DISABLED
        )
        delete_theme_btn.pack(pady=5)

        def on_theme_select(*args):
            selected = theme_var.get()
            if selected in BUILTIN_THEMES:
                theme_obj = BUILTIN_THEMES[selected]
                delete_theme_btn.config(state=tk.DISABLED)
            else:
                theme_obj = next((t for t in self.custom_themes if t.name == selected), None)
                if theme_obj:
                    delete_theme_btn.config(state=tk.NORMAL)
                else:
                    delete_theme_btn.config(state=tk.DISABLED)
            if theme_obj:
                round_var.set(theme_obj.window_round_radius)
                bright_var.set(theme_obj.window_brightness)
                sat_var.set(theme_obj.window_saturation)
                bg_color_var.set(theme_obj.bg_color)
                frame_bg_var.set(theme_obj.frame_bg)
                accent_color_var.set(theme_obj.accent_color)
                text_color_var.set(theme_obj.text_color)
                border_color_var.set(theme_obj.border_color)
                font_family_var.set(theme_obj.font_family)
                font_size_var.set(theme_obj.font_size)
                preview_canvas.config(bg=theme_obj.bg_color)
                preview_canvas.itemconfig(1, fill=theme_obj.frame_bg, outline=theme_obj.border_color)
                preview_canvas.itemconfig(2, fill=theme_obj.accent_color, outline=theme_obj.border_color)
                preview_canvas.itemconfig(3, fill=theme_obj.text_color)
                preview_canvas.itemconfig(4, fill=theme_obj.text_color)

        theme_var.trace('w', on_theme_select)

        def apply_theme_now():
            selected = theme_var.get()
            if selected in BUILTIN_THEMES:
                # 直接应用内置主题
                self.current_theme = selected
                self._apply_theme(selected)
                self.save_config(force=True)
                log_message(f"应用内置主题: {selected}", "INFO")
                messagebox.showinfo("主题", "主题已应用")
            else:
                # 自定义主题：更新属性后再应用
                theme_obj = next((t for t in self.custom_themes if t.name == selected), None)
                if theme_obj:
                    theme_obj.window_round_radius = round_var.get()
                    theme_obj.window_brightness = bright_var.get()
                    theme_obj.window_saturation = sat_var.get()
                    theme_obj.bg_color = bg_color_var.get()
                    theme_obj.frame_bg = frame_bg_var.get()
                    theme_obj.accent_color = accent_color_var.get()
                    theme_obj.text_color = text_color_var.get()
                    theme_obj.border_color = border_color_var.get()
                    theme_obj.font_family = font_family_var.get()
                    theme_obj.font_size = font_size_var.get()
                    self.current_theme = selected
                    self._apply_theme(selected)
                    self.save_config(force=True)
                    log_message(f"更新并应用自定义主题: {selected}", "INFO")
                    messagebox.showinfo("主题", "主题已应用")
                else:
                    messagebox.showerror("错误", "主题不存在")

        # ========== 帮助选项卡 ==========
        help_frame = ttk.Frame(notebook, padding=10)
        notebook.add(help_frame, text=tr("help") if CURRENT_LANG == LANG_CHINESE else "Help")

        help_notebook = ttk.Notebook(help_frame)
        help_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ----- 基础使用 -----
        basic_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(basic_frame, text="基础使用" if CURRENT_LANG == LANG_CHINESE else "Basic Usage")

        basic_text = scrolledtext.ScrolledText(
            basic_frame,
            wrap=tk.WORD,
            font=("微软雅黑", 9),
            bg=self.theme.frame_bg,
            fg=self.theme.text_color,
            padx=10,
            pady=10,
            relief="flat"
        )
        basic_text.pack(fill=tk.BOTH, expand=True)

        basic_content = """Q&A

        Q：为什么我每次重启需要重新设置一遍这些设置？
        A：首先可能是应用程序的权限不足，请尝试重新安装到其他目录位置，或者使用管理员的权限运行此程序，如果还是没用请检查全局设置中的软件信息查看软件工作目录

        Q：为什么我的设置应用失败了？
        A：如果是开机自启动项或者是从纯色背景改为图片背景，请先前往设置中的全局设置帮助文档中找到自助工具，并前往查看当前保存的状态。如果是发生了未知错误，请截屏联系开发者，或者尝试关闭杀毒软件。如果是其他的设置项，一般过一会儿会弹出错误提示，如果重试后依然错误请联系开发者

        Q：你们这软件也太坑了，怎么收费这么贵？
        A：软件完全免费，如果需要收费说明你被骗了

        常见错误代码说明：

        1. "Tcl data directory not found"
           原因：打包后的应用程序在临时目录运行时找不到Tcl数据文件
           解决方案：请尝试重新安装应用程序或使用管理员权限运行

        2. "Failed to execute script"
           原因：应用程序启动脚本执行失败
           解决方案：检查应用程序完整性，可能需要重新安装

        3. "Permission denied"
           原因：应用程序没有足够的权限访问系统资源
           解决方案：尝试以管理员身份运行应用程序

        4. "Image file not found"
           原因：背景图片文件不存在或已被移动
           解决方案：检查data/user目录中的图片文件，重新上传或选择其他图片

        5. "JSON decode error"
           原因：配置文件损坏或格式错误
           解决方案：删除data/countdown_config.json文件，应用程序将创建新的默认配置

        6. "Font family not found"
           原因：系统缺少指定的字体
           解决方案：在全局设置中更换为系统支持的字体

        如有其他问题请联系开发者2835531424@qq.com
        """
        basic_text.insert(tk.INSERT, basic_content)
        basic_text.config(state=tk.DISABLED)

        # ----- 进阶使用（自助工具）-----
        advanced_usage_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(advanced_usage_frame, text="进阶使用" if CURRENT_LANG == LANG_CHINESE else "Advanced Usage")

        runtime_frame = ttk.LabelFrame(advanced_usage_frame,
                                       text="运行信息与状态" if CURRENT_LANG == LANG_CHINESE else "Runtime Info & Status",
                                       padding=10)
        runtime_frame.pack(fill=tk.X, padx=5, pady=5)

        runtime_info = ttk.Frame(runtime_frame)
        runtime_info.pack(fill=tk.X, padx=10, pady=10)

        status_vars = {}
        ttk.Label(runtime_info, text="运行状态:" if CURRENT_LANG == LANG_CHINESE else "Status:",
                  font=("微软雅黑", 9, "bold")).grid(row=0, column=0, sticky='w', pady=2)
        status_label = ttk.Label(runtime_info, text="正常" if CURRENT_LANG == LANG_CHINESE else "Normal",
                                 font=("微软雅黑", 9), foreground="#2ecc71")
        status_label.grid(row=0, column=1, sticky='w', pady=2)
        status_vars['runtime'] = status_label

        ttk.Label(runtime_info, text="悬浮窗数量:" if CURRENT_LANG == LANG_CHINESE else "Windows:",
                  font=("微软雅黑", 9, "bold")).grid(row=1, column=0, sticky='w', pady=2)
        window_count_label = ttk.Label(runtime_info, text=str(len(self.windows)), font=("微软雅黑", 9))
        window_count_label.grid(row=1, column=1, sticky='w', pady=2)
        status_vars['window_count'] = window_count_label

        ttk.Label(runtime_info, text="项目数量:" if CURRENT_LANG == LANG_CHINESE else "Projects:",
                  font=("微软雅黑", 9, "bold")).grid(row=2, column=0, sticky='w', pady=2)
        project_count_label = ttk.Label(runtime_info, text=str(len(self.projects)), font=("微软雅黑", 9))
        project_count_label.grid(row=2, column=1, sticky='w', pady=2)
        status_vars['project_count'] = project_count_label

        ttk.Label(runtime_info, text="最后保存:" if CURRENT_LANG == LANG_CHINESE else "Last save:",
                  font=("微软雅黑", 9, "bold")).grid(row=3, column=0, sticky='w', pady=2)
        last_save_label = ttk.Label(runtime_info,
                                    text=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_save_time)),
                                    font=("微软雅黑", 9))
        last_save_label.grid(row=3, column=1, sticky='w', pady=2)
        status_vars['last_save'] = last_save_label

        dev_frame = ttk.LabelFrame(advanced_usage_frame,
                                   text="开发者设置" if CURRENT_LANG == LANG_CHINESE else "Developer Settings",
                                   padding=10)
        dev_frame.pack(fill=tk.X, padx=5, pady=5)

        debug_level_frame = ttk.Frame(dev_frame)
        debug_level_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(debug_level_frame, text="调试等级:" if CURRENT_LANG == LANG_CHINESE else "Debug level:").pack(
            side=tk.LEFT)
        debug_level_var = tk.IntVar(value=DEBUG_MODE)
        debug_combo = ttk.Combobox(debug_level_frame, textvariable=debug_level_var,
                                   values=[0, 1, 2, 3], state="readonly", width=5)
        debug_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(debug_level_frame,
                  text="0=关闭 1=错误 2=信息 3=调试" if CURRENT_LANG == LANG_CHINESE else "0=off 1=error 2=info 3=debug").pack(
            side=tk.LEFT)

        def set_debug_level(*args):
            global DEBUG_MODE
            DEBUG_MODE = debug_level_var.get()
            self.save_config(force=True)

        debug_level_var.trace('w', set_debug_level)

        def open_log_file():
            log_path = os.path.join(self.data_dir, "LOG.txt")
            if os.path.exists(log_path):
                try:
                    if sys.platform == "win32":
                        os.startfile(log_path)
                    elif sys.platform == "darwin":
                        subprocess.run(["open", log_path])
                    else:
                        subprocess.run(["xdg-open", log_path])
                except Exception as e:
                    messagebox.showerror(tr("settings_title"),
                                         f"无法打开日志文件: {e}" if CURRENT_LANG == LANG_CHINESE else f"Cannot open log file: {e}")
            else:
                messagebox.showinfo(tr("settings_title"),
                                    "日志文件尚未创建" if CURRENT_LANG == LANG_CHINESE else "Log file not yet created")

        ttk.Button(dev_frame, text="查看日志" if CURRENT_LANG == LANG_CHINESE else "View log",
                   command=open_log_file, width=12).pack(anchor='w', padx=10, pady=2)

        tools_btn_frame = ttk.Frame(advanced_usage_frame)
        tools_btn_frame.pack(fill=tk.X, padx=5, pady=10)

        def refresh_status():
            active_windows = len([w for w in self.windows if w.winfo_exists()])
            status_vars['runtime'].config(
                text="正常" if active_windows > 0 else "后台运行" if CURRENT_LANG == LANG_CHINESE else "Normal" if active_windows > 0 else "Background",
                foreground="#2ecc71" if active_windows > 0 else "#f39c12"
            )
            status_vars['window_count'].config(text=str(active_windows))
            status_vars['project_count'].config(text=str(len(self.projects)))
            status_vars['last_save'].config(
                text=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_save_time)))

        ttk.Button(tools_btn_frame, text="刷新状态" if CURRENT_LANG == LANG_CHINESE else "Refresh",
                   command=refresh_status, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(tools_btn_frame, text="打开数据目录" if CURRENT_LANG == LANG_CHINESE else "Open data dir",
                   command=lambda: os.startfile(self.data_dir) if sys.platform == "win32" else messagebox.showinfo(
                       tr("settings_title"),
                       f"数据目录: {self.data_dir}" if CURRENT_LANG == LANG_CHINESE else f"Data dir: {self.data_dir}"),
                   width=12).pack(side=tk.LEFT, padx=5)

        refresh_status()

        # ----- 插件开发指南 -----
        guide_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(guide_frame, text="插件开发" if CURRENT_LANG == LANG_CHINESE else "Plugin Dev")

        guide_text = scrolledtext.ScrolledText(
            guide_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg=self.theme.frame_bg,
            fg=self.theme.text_color,
            padx=10,
            pady=10,
            relief="flat"
        )
        guide_text.pack(fill=tk.BOTH, expand=True)

        help_file = os.path.join(self.data_dir, "help.txt")
        if os.path.exists(help_file):
            try:
                with open(help_file, "r", encoding="utf-8") as f:
                    plugin_guide_content = f.read()
            except:
                plugin_guide_content = "无法读取 help.txt 文件。"
        else:
            plugin_guide_content = '''# 倒计时应用插件开发指南

        插件应继承 Plugin 类，并可选实现以下方法：

        - on_load(): 插件被加载时调用
        - on_enable(): 插件被启用时调用
        - on_disable(): 插件被禁用时调用
        - on_settings_open(parent): 在设置窗口的“高级”选项卡中添加自定义设置界面，应返回一个Frame
        - on_window_create(window, project): 每次创建倒计时窗口时调用
        - on_window_closed(window, project): 窗口关闭时调用
        - on_tick(): 每分钟调用一次（由主循环触发）
        - on_before_save_config(): 配置即将保存前调用
        - on_after_save_config(): 配置保存成功后调用
        - on_settings_closed(): 设置窗口关闭时调用
        - on_poem_update(new_poem): 每日一诗更新时调用
        - on_language_change(old_lang, new_lang): 语言切换时调用

        插件内可使用 self.log_plugin(message, level) 记录日志。

        插件元数据可通过模块级变量定义：
            __plugin_name__ = "插件名"
            __version__ = "1.0"
            __author__ = "作者"

        示例插件已放在 plugins/example_plugin.py 中。

        注意：危险操作需要申请权限，请使用 self.api 进行文件、网络、命令操作。
        '''

        guide_text.insert(tk.INSERT, plugin_guide_content)
        guide_text.config(state=tk.DISABLED)

        # 保存设置按钮
        save_btn_frame = ttk.Frame(settings)
        save_btn_frame.pack(fill=tk.X, pady=15)

        def save_settings():
            self.save_config(force=True)
            messagebox.showinfo(tr("save_settings"), tr("save_settings") + " " + ("成功保存！" if CURRENT_LANG==LANG_CHINESE else "saved successfully!"))
            settings.destroy()

        ttk.Button(save_btn_frame, text=tr("save_settings"), command=save_settings, width=20, style="Primary.TButton").pack(ipady=5, pady=5)
        sizegrip = ttk.Sizegrip(settings)
        sizegrip.place(relx=1.0, rely=1.0, anchor='se')

        self.plugin_timer()

    def plugin_timer(self):
        """每分钟触发插件的 on_tick 事件"""
        self.plugin_manager.trigger_event("on_tick")
        self.after(60000, self.plugin_timer)

    def open_appearance_editor(self, project):
        """打开自定义外观编辑器"""
        editor = tk.Toplevel(self)
        editor.title(f"自定义外观 - {project.name}")
        width, height = 800, 600
        x = (self.screen_width - width) // 2
        y = (self.screen_height - height) // 2
        editor.geometry(f"{width}x{height}+{x}+{y}")
        editor.resizable(True, True)
        editor.minsize(600, 400)
        AppearanceEditor(editor, self, project)
class AppearanceEditor:
    def __init__(self, master, app, project):
        self.master = master
        self.app = app
        self.project = project
        self.elements = {}
        self.current_elem = None
        self.dragging = None
        self.resizing = False
        self.resize_start_x = 0
        self.resize_start_y = 0
        self.start_width = 0
        self.start_height = 0
        self.create_widgets()
        self.create_preview()

    def create_widgets(self):
        main_frame = ttk.Frame(self.master, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.LabelFrame(main_frame, text="元素属性", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # 元素列表（带滚动条）
        listbox_frame = ttk.Frame(left_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.element_listbox = tk.Listbox(listbox_frame, width=20, height=10)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.element_listbox.yview)
        self.element_listbox.config(yscrollcommand=scrollbar.set)
        self.element_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        for elem in ["项目名称", "倒计时", "每日一诗"]:
            self.element_listbox.insert(tk.END, elem)
        self.element_listbox.bind('<<ListboxSelect>>', self.on_element_select)

        # 属性编辑区域（使用 Spinbox 带箭头）
        prop_frame = ttk.Frame(left_frame)
        prop_frame.pack(fill=tk.X, pady=5)
        ttk.Label(prop_frame, text="X坐标:").grid(row=0, column=0, sticky='w')
        self.x_var = tk.IntVar()
        x_spin = ttk.Spinbox(prop_frame, from_=0, to=1000, textvariable=self.x_var, width=8, increment=1)
        x_spin.grid(row=0, column=1)
        ttk.Label(prop_frame, text="Y坐标:").grid(row=1, column=0, sticky='w')
        self.y_var = tk.IntVar()
        y_spin = ttk.Spinbox(prop_frame, from_=0, to=1000, textvariable=self.y_var, width=8, increment=1)
        y_spin.grid(row=1, column=1)
        ttk.Label(prop_frame, text="字体大小:").grid(row=2, column=0, sticky='w')
        self.font_size_var = tk.IntVar()
        ttk.Spinbox(prop_frame, from_=8, to=64, textvariable=self.font_size_var, width=8).grid(row=2, column=1)
        ttk.Label(prop_frame, text="颜色:").grid(row=3, column=0, sticky='w')
        self.color_var = tk.StringVar()
        color_btn = tk.Button(prop_frame, text="选择颜色", command=self.choose_color, bg=self.color_var.get())
        color_btn.grid(row=3, column=1)

        right_frame = ttk.LabelFrame(main_frame, text="预览 (可拖拽调整)", padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        self.canvas = tk.Canvas(right_frame, bg=self.project.bg_color, width=400, height=300)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用", command=self.apply_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="保存到项目", command=self.save_to_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=self.master.destroy).pack(side=tk.LEFT, padx=5)

        # 自定义大尺寸拖拽手柄（40x40，带图标）
        handle_frame = tk.Frame(self.master, bg="#cccccc", width=40, height=40, cursor="sizing")
        handle_frame.place(relx=1.0, rely=1.0, anchor='se')
        handle_frame.bind("<Button-1>", self.start_resize)
        handle_frame.bind("<B1-Motion>", self.on_resize)
        handle_frame.bind("<ButtonRelease-1>", self.stop_resize)
        label = tk.Label(handle_frame, text="⬇️⬇️", bg="#cccccc", font=("Arial", 16))
        label.pack(expand=True)

    def start_resize(self, event):
        self.resizing = True
        self.resize_start_x = event.x_root
        self.resize_start_y = event.y_root
        self.start_width = self.master.winfo_width()
        self.start_height = self.master.winfo_height()

    def on_resize(self, event):
        if not self.resizing:
            return
        dx = event.x_root - self.resize_start_x
        dy = event.y_root - self.resize_start_y
        new_width = max(400, self.start_width + dx)
        new_height = max(300, self.start_height + dy)
        self.master.geometry(f"{new_width}x{new_height}")

    def stop_resize(self, event):
        self.resizing = False

    def create_preview(self):
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.draw_preview()

    def draw_preview(self):
        self.canvas.delete("all")
        self.name_id = self.canvas.create_text(100, 50, text=self.project.name,
                                               font=(self.app.global_font, 12, "bold"),
                                               fill=self.project.font_color,
                                               tags=("name", "draggable"))
        self.countdown_id = self.canvas.create_text(100, 150, text="00天00小时00分",
                                                    font=(self.app.global_font, 14, "bold"),
                                                    fill=self.project.font_color,
                                                    tags=("countdown", "draggable"))
        self.poem_id = self.canvas.create_text(100, 250, text=self.app.daily_poem,
                                               font=(self.app.global_font, 10),
                                               fill=self.project.font_color,
                                               tags=("poem", "draggable"))

    def on_element_select(self, event):
        selection = self.element_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index == 0:
            self.current_elem = "name"
            x, y = self.canvas.coords(self.name_id)
            font = self.canvas.itemcget(self.name_id, "font")
            size = self.extract_font_size(font)
            self.x_var.set(int(x))
            self.y_var.set(int(y))
            self.font_size_var.set(size)
            self.color_var.set(self.canvas.itemcget(self.name_id, "fill"))
        elif index == 1:
            self.current_elem = "countdown"
            x, y = self.canvas.coords(self.countdown_id)
            font = self.canvas.itemcget(self.countdown_id, "font")
            size = self.extract_font_size(font)
            self.x_var.set(int(x))
            self.y_var.set(int(y))
            self.font_size_var.set(size)
            self.color_var.set(self.canvas.itemcget(self.countdown_id, "fill"))
        elif index == 2:
            self.current_elem = "poem"
            x, y = self.canvas.coords(self.poem_id)
            font = self.canvas.itemcget(self.poem_id, "font")
            size = self.extract_font_size(font)
            self.x_var.set(int(x))
            self.y_var.set(int(y))
            self.font_size_var.set(size)
            self.color_var.set(self.canvas.itemcget(self.poem_id, "fill"))

    def start_drag(self, event):
        items = self.canvas.find_withtag("current")
        if items:
            tags = self.canvas.gettags(items[0])
            if "draggable" in tags:
                self.dragging = items[0]
                # 自动选中对应的元素
                if "name" in tags:
                    self.element_listbox.selection_clear(0, tk.END)
                    self.element_listbox.selection_set(0)
                    self.element_listbox.event_generate("<<ListboxSelect>>")
                elif "countdown" in tags:
                    self.element_listbox.selection_clear(0, tk.END)
                    self.element_listbox.selection_set(1)
                    self.element_listbox.event_generate("<<ListboxSelect>>")
                elif "poem" in tags:
                    self.element_listbox.selection_clear(0, tk.END)
                    self.element_listbox.selection_set(2)
                    self.element_listbox.event_generate("<<ListboxSelect>>")

    def on_drag(self, event):
        if self.dragging:
            self.canvas.coords(self.dragging, event.x, event.y)
            self.update_coords_from_drag()

    def stop_drag(self, event):
        self.dragging = None

    def update_coords_from_drag(self):
        if not self.dragging:
            return
        x, y = self.canvas.coords(self.dragging)
        tags = self.canvas.gettags(self.dragging)
        if "name" in tags:
            if self.current_elem == "name":
                self.x_var.set(int(x))
                self.y_var.set(int(y))
        elif "countdown" in tags:
            if self.current_elem == "countdown":
                self.x_var.set(int(x))
                self.y_var.set(int(y))
        elif "poem" in tags:
            if self.current_elem == "poem":
                self.x_var.set(int(x))
                self.y_var.set(int(y))

    def choose_color(self):
        color = colorchooser.askcolor(title="选择颜色", initialcolor=self.color_var.get())
        if color and color[1]:
            self.color_var.set(color[1])

    def apply_changes(self):
        if not self.current_elem:
            return
        elem_id = None
        if self.current_elem == "name":
            elem_id = self.name_id
        elif self.current_elem == "countdown":
            elem_id = self.countdown_id
        elif self.current_elem == "poem":
            elem_id = self.poem_id
        if elem_id:
            self.canvas.coords(elem_id, self.x_var.get(), self.y_var.get())
            self.canvas.itemconfig(elem_id,
                                   font=(self.app.global_font, self.font_size_var.get(), "bold" if self.current_elem != "poem" else ""),
                                   fill=self.color_var.get())
            log_message(f"外观编辑器应用更改 - {self.current_elem}: 坐标({self.x_var.get()},{self.y_var.get()}) 字号{self.font_size_var.get()} 颜色{self.color_var.get()}", "DEBUG")

    def save_to_project(self):
        layout = {}
        x, y = self.canvas.coords(self.name_id)
        font = self.canvas.itemcget(self.name_id, "font")
        size = self.extract_font_size(font)
        color = self.canvas.itemcget(self.name_id, "fill")
        layout["name"] = {"x": int(x), "y": int(y), "font_size": size, "color": color}
        x, y = self.canvas.coords(self.countdown_id)
        font = self.canvas.itemcget(self.countdown_id, "font")
        size = self.extract_font_size(font)
        color = self.canvas.itemcget(self.countdown_id, "fill")
        layout["countdown"] = {"x": int(x), "y": int(y), "font_size": size, "color": color}
        x, y = self.canvas.coords(self.poem_id)
        font = self.canvas.itemcget(self.poem_id, "font")
        size = self.extract_font_size(font)
        color = self.canvas.itemcget(self.poem_id, "fill")
        layout["poem"] = {"x": int(x), "y": int(y), "font_size": size, "color": color}

        self.project.custom_layout = layout
        self.app.save_config(force=True)
        # 立即更新对应窗口
        for idx, win in enumerate(self.app.windows):
            if win.project == self.project:
                win.apply_custom_layout()
                win.refresh()
                break
        messagebox.showinfo("保存成功", "自定义外观已保存到项目。")
        log_message(f"外观编辑器保存项目 {self.project.name} 的自定义布局: {layout}", "INFO")

    def extract_font_size(self, font_str):
        try:
            if isinstance(font_str, (tuple, list)):
                return font_str[1]
            import re
            nums = re.findall(r'\d+', font_str)
            return int(nums[0]) if nums else 12
        except:
            return 12
# ---------- 程序入口 ----------
if __name__ == "__main__":
    hide_console()
    try:
        if sys.platform == "win32":
            win_version = platform.version().split('.')
            if len(win_version) >= 2:
                major, minor = int(win_version[0]), int(win_version[1])
                if major > 6 or (major == 6 and minor >= 3):
                    try:
                        ctypes.windll.shcore.SetProcessDpiAwareness(1)
                    except:
                        ctypes.windll.user32.SetProcessDPIAware()
                else:
                    ctypes.windll.user32.SetProcessDPIAware()
        app = CountdownApp()
        if sys.platform == "win32" and platform.release() == '7':
            ctypes.windll.uxtheme.SetThemeAppProperties(0)
        debug_print("【DEBUG】即将进入主循环")
        app.mainloop()
        debug_print("【DEBUG】主循环已退出")
    except Exception as e:
        error_log = os.path.join(os.getcwd(), "countdown_error.log")
        with open(error_log, "a") as f:
            f.write(f"{datetime.now()} - 程序崩溃: {str(e)}\n")
            f.write(traceback.format_exc())
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("严重错误", f"程序遇到错误: {e}\n\n错误日志已保存到: {error_log}")
        root.destroy()