# -*- coding: utf-8 -*-
"""
语录循环粘贴（GUI 版 / 深色扁平 / 无边框 / 高分屏自适应）
- 默认读取 exe 同目录下的 语录.txt，可在设置中修改文件路径
- 设置（文件路径、切换延迟）保存在 exe 同目录的 config.json，下次打开保持
- 每按一次 Ctrl+V 粘贴当前行，自动切换到下一行，循环往复
- 编辑语录窗口输入后自动保存（防抖 600ms）
- 全局热键 Ctrl+Q 退出
"""
import json
import os
import sys
import time
import ctypes
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

import keyboard

EXIT_HOTKEY = "ctrl+q"

# ---------- 配色 ----------
C_BG      = "#14161a"   # 窗口背景
C_CARD    = "#1e2127"   # 卡片/标题栏背景
C_CARD2   = "#262a31"   # 输入框背景
C_FG      = "#e8eaed"   # 主文字
C_MUTED   = "#9aa0a6"   # 次要文字
C_ACCENT  = "#4f8cff"   # 主按钮
C_ACCENT_H= "#6b9fff"   # 主按钮悬停
C_GREEN   = "#3ddc84"   # 运行状态
C_DANGER  = "#ff6b6b"   # 退出按钮悬停
C_BORDER  = "#2c313a"   # 边框

# exe（或脚本）所在目录
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEFAULT_TXT = os.path.join(BASE_DIR, "语录.txt")
ICON_PATH = os.path.join(BASE_DIR, "fish.ico")


def enable_dpi_awareness():
    """启用高 DPI 感知，避免高分屏下模糊"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def log_error(msg: str):
    """把错误写入 exe 同目录的 error.log 便于排查"""
    try:
        with open(os.path.join(BASE_DIR, "error.log"), "a", encoding="utf-8") as f:
            import traceback
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
            if sys.exc_info()[0] is not None:
                traceback.print_exc(file=f)
            f.write("\n")
    except OSError:
        pass


def load_config():
    cfg = {"txt_path": DEFAULT_TXT, "delay_ms": 100}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError) as e:
        messagebox.showerror("错误", "无法保存设置:\n" + str(e))


def flat_button(parent, text, command, bg=C_CARD2, fg=C_FG, hover=None,
                font=("微软雅黑", 10), padx=18, pady=8, **kw):
    """扁平按钮 + 悬停变色"""
    hover = hover or bg
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                    activebackground=hover, activeforeground=fg,
                    relief="flat", bd=0, cursor="hand2",
                    font=font, padx=padx, pady=pady, **kw)
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def titlebar_button(parent, text, command, fg=C_MUTED, hover_fg=C_FG, size=11):
    """标题栏上的文字按钮（最小化/关闭）"""
    lbl = tk.Label(parent, text=text, bg=C_CARD, fg=fg, cursor="hand2",
                   font=("Segoe UI", size), width=3, pady=2)
    lbl.bind("<Enter>", lambda e: lbl.config(fg=hover_fg))
    lbl.bind("<Leave>", lambda e: lbl.config(fg=fg))
    lbl.bind("<Button-1>", lambda e: command())
    return lbl


def make_draggable(widget, win):
    """让控件拖动窗口"""
    state = {"dx": 0, "dy": 0}
    widget.bind("<Button-1>", lambda e: state.update(dx=e.x, dy=e.y))
    widget.bind("<B1-Motion>",
                lambda e: win.geometry(f"+{e.x_root - state['dx']}+{e.y_root - state['dy']}"))


class SlimScrollbar(tk.Canvas):
    """细长扁平滚动条（无箭头、悬停高亮）"""

    def __init__(self, parent, widget, scale=1.0):
        super().__init__(parent, width=int(6 * scale), bg=parent["bg"],
                         highlightthickness=0)
        self.widget = widget
        self.s = scale
        self.lo, self.hi = 0.0, 1.0
        self.press_y = None
        self.press_lo = None
        widget.config(yscrollcommand=self._set)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "press_y", None))
        self.bind("<Configure>", lambda e: self._draw())

    def _set(self, lo, hi):
        self.lo, self.hi = float(lo), float(hi)
        self._draw()

    def _draw(self):
        self.delete("all")
        h = self.winfo_height()
        if h < 10 or self.hi - self.lo >= 0.999:
            return  # 内容不满一屏时隐藏
        th = max(h * (self.hi - self.lo), int(30 * self.s))
        ty = h * self.lo
        self.create_rectangle(int(2 * self.s), ty, int(4 * self.s), ty + th,
                              fill=C_MUTED, width=0, tags="thumb")

    def _press(self, e):
        h = self.winfo_height()
        th = max(h * (self.hi - self.lo), int(30 * self.s))
        ty = h * self.lo
        if ty <= e.y <= ty + th:
            self.press_y = e.y
            self.press_lo = self.lo
        else:  # 点击空白处翻页
            self.widget.yview_scroll(-1 if e.y < ty else 1, "pages")

    def _motion(self, e):
        if self.press_y is None:
            return
        h = self.winfo_height()
        delta = (e.y - self.press_y) / h
        self.widget.yview_moveto(min(max(self.press_lo + delta, 0.0), 1.0))


def make_raise_on_top(win):
    """点击窗口时把它提到最上层"""
    def raise_it(_e=None):
        win.attributes("-topmost", True)
        win.lift()
    win.bind("<Button-1>", raise_it, add="+")


def make_dialog(app, title, w, h, resizable=False, minsize=None):
    """无边框对话框：自定义标题栏 + 置顶（不用 grab, 避免模态卡死）"""
    s = app.s
    win = tk.Toplevel(app.root)
    win.title(title)
    win.configure(bg=C_BG)
    win.resizable(resizable, resizable)
    if minsize:
        win.minsize(*minsize)
    win.transient(app.root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    w, h = int(w * s), int(h * s)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{max((sw - w) // 2, 0)}+{max((sh - h) // 2, 0)}")
    make_raise_on_top(win)
    # 弹窗映射后强制升到最顶层并获得焦点
    def bring_to_front():
        win.attributes("-topmost", True)
        win.lift()
        win.focus_force()
    win.after(30, bring_to_front)
    try:
        if os.path.exists(ICON_PATH):
            win.iconbitmap(ICON_PATH)
    except Exception:
        pass

    # 自定义标题栏
    tb = tk.Frame(win, bg=C_CARD, height=int(38 * s))
    tb.pack(fill="x", side="top")
    tb.pack_propagate(False)
    t = tk.Label(tb, text=title, bg=C_CARD, fg=C_FG, font=("微软雅黑", 9, "bold"))
    t.pack(side="left", padx=14)
    titlebar_button(tb, "✕", win.destroy, hover_fg=C_DANGER).pack(side="right")
    make_draggable(tb, win)
    make_draggable(t, win)
    win.bind("<Escape>", lambda e: win.destroy())

    content = tk.Frame(win, bg=C_BG)
    content.pack(fill="both", expand=True)
    return win, content


class QuotePasteApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("语录循环粘贴")
        root.resizable(False, False)
        root.configure(bg=C_BG)
        root.overrideredirect(True)   # 隐藏系统边框

        # 高分屏缩放比例（tk 字体用磅值会自动缩放，像素尺寸需手动乘）
        self.s = max(root.winfo_fpixels("1i") / 96.0, 1.0)
        w, h = int(480 * self.s), int(400 * self.s)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{max((sw - w) // 2, 0)}+{max((sh - h) // 2, 0)}")

        self.cfg = load_config()
        self.lines = []
        self.idx = 0
        self.running = False
        self.hotkey_handler = None
        self.delay_ms = tk.IntVar(value=self.cfg.get("delay_ms", 100))

        self._build_main_ui()
        root.update_idletasks()
        self._setup_chrome()          # 图标 + 任务栏
        self._load_file()
        self.start()                  # 启动即自动运行
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 窗口外观 ----------
    def _setup_chrome(self):
        """设置窗口图标，让无边框窗口保留任务栏图标，并置顶显示"""
        self.root.attributes("-topmost", True)   # 主窗口始终在顶部
        make_raise_on_top(self.root)
        try:
            if os.path.exists(ICON_PATH):
                self.root.iconbitmap(ICON_PATH)
        except Exception:
            pass
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                  (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW)
            SWP = 0x0001 | 0x0002 | 0x0004 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|FRAMECHANGED
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP)
        except Exception:
            pass

    def _minimize(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        except Exception:
            self.root.iconify()

    def _build_titlebar(self):
        """自定义标题栏（拖动 + 最小化 + 关闭）"""
        tb = tk.Frame(self.root, bg=C_CARD, height=int(38 * self.s))
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)
        t = tk.Label(tb, text="🐟 语录循环粘贴", bg=C_CARD, fg=C_FG,
                     font=("微软雅黑", 9, "bold"))
        t.pack(side="left", padx=14)
        titlebar_button(tb, "✕", self._on_close, hover_fg=C_DANGER).pack(side="right")
        titlebar_button(tb, "─", self._minimize).pack(side="right")
        make_draggable(tb, self.root)
        make_draggable(t, self.root)

    # ---------- 主界面 ----------
    def _build_main_ui(self):
        s = self.s
        self._build_titlebar()

        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill="both", expand=True)

        # 当前语录卡片
        card = tk.Frame(body, bg=C_CARD, highlightbackground=C_BORDER,
                        highlightthickness=1)
        card.pack(fill="x", padx=int(20 * s), pady=(int(14 * s), 0))

        self.info_var = tk.StringVar(value="未加载语录")
        tk.Label(card, textvariable=self.info_var, font=("微软雅黑", 8),
                 bg=C_CARD, fg=C_MUTED, wraplength=int(400 * s), justify="left"
                 ).pack(anchor="w", padx=int(16 * s), pady=(int(12 * s), int(4 * s)))

        self.cur_var = tk.StringVar(value="当前行: -")
        tk.Label(card, textvariable=self.cur_var, font=("微软雅黑", 13, "bold"),
                 bg=C_CARD, fg=C_FG, wraplength=int(400 * s), justify="left"
                 ).pack(anchor="w", padx=int(16 * s), pady=(0, int(8 * s)))

        # 进度条
        self.bar_w = int(408 * s)
        self.bar = tk.Canvas(card, width=self.bar_w, height=int(6 * s), bg=C_CARD2,
                             highlightthickness=0)
        self.bar.pack(fill="x", padx=int(16 * s), pady=(0, int(14 * s)))

        # 状态行
        status = tk.Frame(body, bg=C_BG)
        status.pack(fill="x", padx=int(20 * s), pady=(int(12 * s), 0))
        self.status_dot = tk.Label(status, text="●", font=("微软雅黑", 11),
                                   bg=C_BG, fg=C_GREEN)
        self.status_dot.pack(side="right")
        self.status_txt = tk.Label(status, text="运行中", font=("微软雅黑", 9),
                                   bg=C_BG, fg=C_MUTED)
        self.status_txt.pack(side="right", padx=(0, int(6 * s)))

        # 按钮区
        btns = tk.Frame(body, bg=C_BG)
        btns.pack(fill="x", padx=int(20 * s), pady=int(14 * s))
        self.toggle_btn = flat_button(btns, "暂停", self.toggle,
                                      bg=C_ACCENT, hover=C_ACCENT_H,
                                      padx=int(18 * s), pady=int(8 * s))
        self.toggle_btn.pack(side="left")
        flat_button(btns, "编辑语录", self._open_editor,
                    padx=int(18 * s), pady=int(8 * s)).pack(side="left", padx=int(10 * s))
        flat_button(btns, "设置", self._open_settings,
                    padx=int(18 * s), pady=int(8 * s)).pack(side="left")
        flat_button(btns, "退出", self._on_close,
                    fg=C_MUTED, hover=C_DANGER,
                    padx=int(18 * s), pady=int(8 * s)).pack(side="right")

        tk.Label(body, text="Ctrl+V 粘贴当前行并自动切到下一行 ｜ Ctrl+Q 退出程序",
                 font=("微软雅黑", 8), bg=C_BG, fg=C_MUTED
                 ).pack(side="bottom", pady=int(10 * s))

    def _draw_progress(self):
        """在画布上绘制进度条"""
        self.bar.delete("all")
        if self.lines:
            w = int(self.bar_w * (self.idx + 1) / len(self.lines))
            self.bar.create_rectangle(0, 0, max(w, int(8 * self.s)),
                                      int(6 * self.s), fill=C_ACCENT, width=0)

    # ---------- 文件读写 ----------
    def _load_file(self):
        self.lines = []
        path = self.cfg.get("txt_path", DEFAULT_TXT)
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                with open(path, "r", encoding=enc) as f:
                    self.lines = [ln.strip() for ln in f if ln.strip()]
                break
            except (UnicodeDecodeError, OSError):
                continue
        self.idx = 0
        if self.lines:
            self._copy_current()
            self.info_var.set(f"已加载 {len(self.lines)} 行 ｜ {path}")
            self._update_cur()
        else:
            self.info_var.set("语录文件为空或读取失败: " + path)
            self.cur_var.set("当前行: -")
            self.bar.delete("all")

    def _copy_current(self):
        if not self.lines:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.lines[self.idx])
        self.root.update()  # 让剪贴板内容立即生效

    def _update_cur(self):
        if self.lines:
            self.cur_var.set(f"当前行 ({self.idx + 1}/{len(self.lines)}): {self.lines[self.idx]}")
            self._draw_progress()

    # ---------- 热键监听 ----------
    def start(self):
        if self.running or not self.lines:
            if not self.lines:
                messagebox.showwarning("提示", "语录为空，请先编辑语录内容")
            return
        self.hotkey_handler = keyboard.add_hotkey("ctrl+v", self._on_paste)
        self.running = True
        self.toggle_btn.config(text="暂停")
        self.status_dot.config(fg=C_GREEN)
        self.status_txt.config(text="运行中")

    def stop(self):
        if not self.running:
            return
        keyboard.remove_hotkey(self.hotkey_handler)
        self.hotkey_handler = None
        self.running = False
        self.toggle_btn.config(text="继续")
        self.status_dot.config(fg=C_MUTED)
        self.status_txt.config(text="已暂停")

    def toggle(self):
        self.stop() if self.running else self.start()

    def _on_paste(self):
        """Ctrl+V 触发: 等粘贴动作读完剪贴板后, 再切到下一行"""
        time.sleep(self.delay_ms.get() / 1000.0)
        if not self.lines:
            return
        self.idx = (self.idx + 1) % len(self.lines)
        self.root.after(0, self._copy_current)
        self.root.after(0, self._update_cur)

    # ---------- 编辑语录弹窗（输入自动保存） ----------
    def _open_editor(self):
        s = self.s
        win, body = make_dialog(self, "🐟 编辑语录", 560, 480,
                                resizable=True,
                                minsize=(int(460 * s), int(340 * s)))

        # 充足留白: 外边距 28, 内容区之间有间隔
        tk.Label(body, text="语录内容（每行一条，空行自动忽略，输入后自动保存）",
                 font=("微软雅黑", 9, "bold"), bg=C_BG, fg=C_MUTED
                 ).pack(anchor="w", padx=int(28 * s), pady=(int(18 * s), int(8 * s)))

        textwrap_frame = tk.Frame(body, bg=C_BORDER)  # 仅作为 1px 描边容器
        textwrap_frame.pack(fill="both", expand=True,
                            padx=int(28 * s), pady=(0, int(12 * s)))

        inner = tk.Frame(textwrap_frame, bg=C_CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        txt = tk.Text(inner, font=("微软雅黑", 10), wrap="word",
                      bg=C_CARD, fg=C_FG, relief="flat",
                      insertbackground=C_FG, bd=0,
                      padx=int(16 * s), pady=int(12 * s),
                      spacing1=int(4 * s), spacing3=int(4 * s),
                      selectbackground=C_ACCENT, selectforeground=C_FG)
        txt.pack(side="left", fill="both", expand=True)
        SlimScrollbar(inner, txt, scale=s).pack(side="right", fill="y")
        txt.insert("1.0", "\n".join(self.lines))

        bottom = tk.Frame(body, bg=C_BG)
        bottom.pack(fill="x", padx=int(28 * s), pady=(0, int(18 * s)))
        save_status = tk.Label(bottom, text="● 自动保存已开启", font=("微软雅黑", 8),
                               bg=C_BG, fg=C_GREEN)
        save_status.pack(side="left")
        flat_button(bottom, "关闭", win.destroy, fg=C_MUTED,
                    padx=int(18 * s), pady=int(6 * s)).pack(side="right")

        # 防抖自动保存
        after_id = {"id": None}

        def do_save():
            after_id["id"] = None
            content = txt.get("1.0", "end").strip("\n")
            try:
                with open(self.cfg["txt_path"], "w", encoding="utf-8") as f:
                    f.write(content)
            except OSError as e:
                save_status.config(text="● 保存失败: " + str(e), fg=C_DANGER)
                return
            self._refresh_lines(content)
            save_status.config(text=f"● 已自动保存（共 {len(self.lines)} 行）", fg=C_GREEN)

        def on_key(_e):
            if after_id["id"] is not None:
                win.after_cancel(after_id["id"])
            save_status.config(text="● 编辑中...", fg=C_MUTED)
            after_id["id"] = win.after(600, do_save)

        def on_close():
            if after_id["id"] is not None:   # 关闭前把未保存的内容落盘
                win.after_cancel(after_id["id"])
                do_save()
            win.destroy()

        txt.bind("<KeyRelease>", on_key)
        win.protocol("WM_DELETE_WINDOW", on_close)

    def _refresh_lines(self, content: str):
        """自动保存后同步内存数据（不打断当前进度）"""
        self.lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        if self.lines:
            self.idx %= len(self.lines)
            self.info_var.set(f"已加载 {len(self.lines)} 行 ｜ {self.cfg['txt_path']}")
            self._update_cur()
            self._copy_current()
        else:
            self.idx = 0
            self.info_var.set("语录文件为空: " + self.cfg["txt_path"])
            self.cur_var.set("当前行: -")
            self.bar.delete("all")

    # ---------- 设置弹窗 ----------
    def _open_settings(self):
        s = self.s
        win, frame = make_dialog(self, "🐟 设置", 560, 240)

        inner = tk.Frame(frame, bg=C_BG)
        inner.pack(fill="both", expand=True, padx=int(28 * s), pady=int(16 * s))

        # 语录文件路径
        tk.Label(inner, text="语录文件路径", font=("微软雅黑", 9, "bold"),
                 bg=C_BG, fg=C_MUTED).pack(anchor="w")
        row = tk.Frame(inner, bg=C_BG)
        row.pack(fill="x", pady=(int(6 * s), 0))
        path_var = tk.StringVar(value=self.cfg.get("txt_path", DEFAULT_TXT))
        tk.Entry(row, textvariable=path_var, bg=C_CARD2, fg=C_FG,
                 relief="flat", insertbackground=C_FG,
                 font=("微软雅黑", 9)).pack(side="left", fill="x", expand=True,
                                           ipady=int(6 * s))

        def browse():
            p = filedialog.askopenfilename(
                title="选择语录文件", parent=win,
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
            if p:
                path_var.set(p)

        flat_button(row, "浏览", browse, padx=int(14 * s), pady=int(4 * s)
                    ).pack(side="left", padx=(int(8 * s), 0))

        # 延迟设置
        opt = tk.Frame(inner, bg=C_BG)
        opt.pack(fill="x", pady=(int(14 * s), 0))
        tk.Label(opt, text="粘贴后切换下一行的延迟(毫秒):", font=("微软雅黑", 9),
                 bg=C_BG, fg=C_FG).pack(side="left")
        tk.Spinbox(opt, from_=0, to=2000, increment=50, width=6,
                   textvariable=self.delay_ms, bg=C_CARD2, fg=C_FG,
                   relief="flat", insertbackground=C_FG,
                   buttonbackground=C_CARD2, font=("微软雅黑", 9)
                   ).pack(side="left", padx=int(8 * s))

        # 按钮
        btns = tk.Frame(inner, bg=C_BG)
        btns.pack(fill="x", pady=(int(18 * s), 0))
        was_running = self.running
        flat_button(btns, "保存",
                    command=lambda: self._save_settings(path_var.get(), win, was_running),
                    bg=C_ACCENT, hover=C_ACCENT_H,
                    padx=int(18 * s), pady=int(6 * s)).pack(side="right")
        flat_button(btns, "取消", win.destroy, fg=C_MUTED,
                    padx=int(18 * s), pady=int(6 * s)).pack(side="right", padx=int(10 * s))

    def _save_settings(self, new_path: str, win, was_running: bool):
        new_path = new_path.strip()
        if not new_path:
            messagebox.showwarning("提示", "文件路径不能为空", parent=win)
            return
        if not os.path.exists(new_path):
            messagebox.showerror("错误", "文件不存在:\n" + new_path, parent=win)
            return
        self.stop()
        self.cfg["txt_path"] = new_path
        self.cfg["delay_ms"] = self.delay_ms.get()
        save_config(self.cfg)
        self._load_file()
        win.destroy()
        if was_running:
            self.start()
        messagebox.showinfo("成功", f"设置已保存\n文件: {new_path}\n共 {len(self.lines)} 行")

    # ---------- 退出 ----------
    def _on_close(self):
        self.stop()
        keyboard.unhook_all()
        self.root.destroy()


def main():
    enable_dpi_awareness()

    # Tk 回调异常写入日志（避免无控制台时无声崩溃）
    def _cb_exc(exc_type, exc, tb):
        import traceback
        log_error("".join(traceback.format_exception(exc_type, exc, tb)))

    tk.Tk.report_callback_exception = _cb_exc

    root = tk.Tk()
    app = QuotePasteApp(root)
    keyboard.add_hotkey(EXIT_HOTKEY, lambda: root.after(0, root.destroy))
    # 调试钩子: 设置 QP_AUTOTEST=editor 启动时自动打开编辑窗口
    if os.environ.get("QP_AUTOTEST") == "editor":
        root.after(800, lambda: log_error("marker-800ms"))
        root.after(1200, app._open_editor)
        root.after(1500, lambda: log_error("marker-editor-opened"))
        root.after(2500, lambda: log_error("marker-2500ms"))
        root.after(3000, lambda: log_error("marker-before-destroy"))
        root.after(3300, root.destroy)
        root.after(3800, lambda: log_error("marker-after-destroy-should-not-fire"))
    root.mainloop()
    log_error("mainloop exited")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_error("fatal in main")
        raise
