"""
文件夹收纳专家 - FolderSorter Pro
定价：¥9.9 终身授权
"""
import os
import sys
import hashlib
import shutil
import re
import json
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import threading
import hashlib as hl

# ── 尝试导入CTkMessagebox（可选）──────────────────────────────
try:
    from CTkMessagebox import CTkMessagebox
except ImportError:
    CTkMessagebox = None

# ── 配置 ──────────────────────────────────────────────────────
APP_NAME = "文件夹收纳专家"
APP_VER = "v1.0"
REG_CODE_PATTERN = re.compile(r'^FSP-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')
PAID_KEYS = {"FSP-X9K2-M3P7-N8Q4", "FSP-K5J9-R2W6-T1B3"}
TRIAL_FILE_LIMIT = 50
TRIAL_DUP_LIMIT = 10

# 注册表存储路径（用于保存付费状态）
REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".license")

# ── 样式 ──────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

COLORS = {
    "bg": "#1a1a2e",
    "surface": "#16213e",
    "accent": "#e94560",
    "text": "#eaeaea",
    "subtext": "#a0a0a0",
    "success": "#4ecca3",
    "warning": "#f39c12",
    "border": "#2d3a5a",
}

# ── 工具函数 ──────────────────────────────────────────────────
def md5(path):
    h = hl.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def get_file_info(path):
    try:
        stat = os.stat(path)
        return {
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime),
            "ext": os.path.splitext(path)[1].lower(),
            "name": os.path.basename(path),
            "dir": os.path.dirname(path),
        }
    except Exception:
        return None

def format_size(size):
    for unit in ["B","KB","MB","GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def is_paid():
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                data = json.load(f)
            return data.get("paid", False)
        except Exception:
            pass
    return False

def activate_paid(code):
    code = code.strip().upper()
    if code in PAID_KEYS:
        with open(REGISTRY_FILE, "w") as f:
            json.dump({"paid": True, "code": code, "date": str(datetime.now())}, f)
        return True
    return False

def enforce_trial(count):
    """试用限制，超过则弹窗"""
    if is_paid():
        return True
    if count > TRIAL_FILE_LIMIT:
        CTkMessagebox(
            title="试用限制",
            message=f"试用版每次最多处理 {TRIAL_FILE_LIMIT} 个文件。\n请付费 ¥9.9 解锁完整版！",
            icon="warning",
            option_1="复制支付宝联系", option_2="取消"
        )
        return False
    return True

# ── 主应用 ────────────────────────────────────────────────────
class FolderSorterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VER}")
        self.geometry("900x650")
        self.minsize(800, 580)
        self._paid = is_paid()
        self._rules = []
        self._current_files = []
        self._rename_preview = []
        self._dup_results = []

        self._build_ui()
        if not self._paid:
            self._show_trial_banner()

    # ── UI 构建 ───────────────────────────────────────────────
    def _build_ui(self):
        # 顶栏
        top = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=52, corner_radius=0)
        top.pack(fill="x", padx=0, pady=0)
        top.pack_propagate(False)

        title_label = ctk.CTkLabel(
            top, text=f"📁 {APP_NAME}", font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(side="left", padx=20, pady=10)

        paid_btn = ctk.CTkButton(
            top, text="💎 已授权" if self._paid else "💎 付费解锁",
            command=self._show_pay_dialog,
            width=130, height=34,
            fg_color=COLORS["accent"] if not self._paid else COLORS["success"],
            hover_color=("#c0354e" if not self._paid else "#3baa87"),
        )
        paid_btn.pack(side="right", padx=15, pady=8)
        self._paid_btn = paid_btn

        ver_label = ctk.CTkLabel(top, text=APP_VER, text_color=COLORS["subtext"])
        ver_label.pack(side="right", padx=5, pady=10)

        # 主内容区
        content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        content.pack(fill="both", expand=True)

        # TabView
        self.tabview = ctk.CTkTabview(content, fg_color=COLORS["bg"],
                                       text_color=COLORS["text"],
                                       selected_color=COLORS["accent"],
                                       segmented_button_fg_color=COLORS["surface"],
                                       segmented_button_selected_color=COLORS["accent"],
                                       segmented_button_selected_hover_color=COLORS["accent"])
        self.tabview.pack(fill="both", expand=True, padx=15, pady=10)

        self.tab_auto = self.tabview.add("自动整理")
        self.tab_rename = self.tabview.add("批量重命名")
        self.tab_dup = self.tabview.add("重复文件检测")
        self.tab_rules = self.tabview.add("规则管理")

        self._build_auto_tab()
        self._build_rename_tab()
        self._build_dup_tab()
        self._build_rules_tab()

        # 状态栏
        self._status_var = tk.StringVar(value="就绪")
        status_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=30, corner_radius=0)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        self._trial_label = ctk.CTkLabel(
            status_bar, textvariable=self._status_var,
            text_color=COLORS["subtext"], font=ctk.CTkFont(size=11)
        )
        self._trial_label.pack(side="left", padx=15, pady=4)

    def _show_trial_banner(self):
        banner = ctk.CTkFrame(self, fg_color="#3d1a2e", height=36, corner_radius=0)
        banner.pack(fill="x", side="bottom")
        banner.pack_propagate(False)
        lbl = ctk.CTkLabel(
            banner,
            text=f"⚠ 试用版：每次最多处理 {TRIAL_FILE_LIMIT} 个文件  |  付费 ¥9.9 解锁无限制",
            text_color="#ffaaa0", font=ctk.CTkFont(size=11)
        )
        lbl.pack(side="left", padx=15, pady=6)
        btn = ctk.CTkButton(
            banner, text="立即解锁", command=self._show_pay_dialog,
            width=90, height=24, fg_color=COLORS["accent"], hover_color="#c0354e",
            text_color="white", font=ctk.CTkFont(size=11)
        )
        btn.pack(side="right", padx=10, pady=4)

    # ── Tab: 自动整理 ─────────────────────────────────────────
    def _build_auto_tab(self):
        f = self.tab_auto
        # 顶部操作栏
        toolbar = ctk.CTkFrame(f, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(15,5))

        self._auto_folder_var = tk.StringVar()
        ctk.CTkEntry(toolbar, textvariable=self._auto_folder_var,
                     placeholder_text="选择要整理的文件夹...", width=400).pack(side="left", padx=(0,8))
        ctk.CTkButton(toolbar, text="浏览...", command=self._browse_auto_folder,
                      width=80).pack(side="left", padx=(0,15))

        ctk.CTkLabel(toolbar, text="整理规则:").pack(side="left", padx=(0,5))
        self._auto_rule_var = tk.StringVar(value="按扩展名")
        rule_menu = ctk.CTkOptionMenu(toolbar, variable=self._auto_rule_var,
                                      values=["按扩展名","按文件大小","按修改日期","自定义规则"],
                                      dropdown_color=COLORS["surface"], width=130)
        rule_menu.pack(side="left")
        ctk.CTkButton(toolbar, text="▶ 开始整理", command=self._run_auto_sort,
                      fg_color=COLORS["accent"], hover_color="#c0354e",
                      width=100).pack(side="right")

        # 文件列表
        list_frame = ctk.CTkFrame(f, fg_color=COLORS["surface"], corner_radius=8)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(5,10))

        cols = ("文件名", "大小", "修改日期", "扩展名", "目标位置")
        self._auto_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                       style="Dark.Treeview", selectmode="extended")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Treeview", background=COLORS["surface"],
                        foreground=COLORS["text"], fieldbackground=COLORS["surface"],
                        rowheight=26)
        style.configure("Dark.Treeview.Heading", background=COLORS["bg"],
                        foreground=COLORS["text"])

        for col in cols:
            self._auto_tree.heading(col, text=col)
            self._auto_tree.column(col, width=150)
        scroll = ttk.Scrollbar(list_frame, command=self._auto_tree.yview)
        self._auto_tree.configure(yscrollcommand=scroll.set)
        self._auto_tree.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        scroll.pack(side="right", fill="y", padx=(0,5), pady=5)

        self._auto_tree.tag_configure("odd", background="#1e2d4a")
        self._auto_tree.tag_configure("even", background=COLORS["surface"])

    def _browse_auto_folder(self):
        folder = filedialog.askdirectory(title="选择要整理的文件夹")
        if folder:
            self._auto_folder_var.set(folder)
            self._load_auto_files(folder)

    def _load_auto_files(self, folder):
        for row in self._auto_tree.get_children():
            self._auto_tree.delete(row)
        files = []
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    info = get_file_info(path)
                    if info:
                        info["path"] = path
                        files.append(info)
        except Exception as e:
            messagebox.showerror("错误", str(e))
            return

        self._current_files = files
        rule = self._auto_rule_var.get()
        for i, info in enumerate(files):
            target = self._calc_target(info, rule, folder)
            tag = "odd" if i % 2 == 0 else "even"
            self._auto_tree.insert("", "end", values=(
                info["name"], format_size(info["size"]),
                info["mtime"].strftime("%Y-%m-%d %H:%M"),
                info["ext"], target
            ), tags=(tag,))

    def _calc_target(self, info, rule, base_folder):
        if rule == "按扩展名":
            ext = info["ext"].lstrip(".")
            if not ext:
                ext = "无扩展名"
            return os.path.join(base_folder, f"📁_{ext.upper()}_文件", info["name"])
        elif rule == "按文件大小":
            size = info["size"]
            if size < 1024*100: cat = "微小文件(<100KB)"
            elif size < 1024*1024*10: cat = "小文件(<10MB)"
            elif size < 1024*1024*100: cat = "中等文件(<100MB)"
            else: cat = "大文件(>100MB)"
            return os.path.join(base_folder, f"📁_{cat}", info["name"])
        elif rule == "按修改日期":
            d = info["mtime"].strftime("%Y-%m")
            return os.path.join(base_folder, f"📁_{d}_文件", info["name"])
        else:
            return info["path"]

    def _run_auto_sort(self):
        folder = self._auto_folder_var.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("提示", "请先选择要整理的文件夹")
            return
        if not enforce_trial(len(self._current_files)):
            return

        rule = self._auto_rule_var.get()
        moved = 0
        errors = []
        for i, info in enumerate(self._current_files):
            target_dir = os.path.dirname(self._calc_target(info, rule, folder))
            try:
                os.makedirs(target_dir, exist_ok=True)
                tgt = self._calc_target(info, rule, folder)
                if info["path"] != tgt:
                    shutil.move(info["path"], tgt)
                    moved += 1
            except Exception as e:
                errors.append(f"{info['name']}: {e}")

        self._status_var.set(f"整理完成！移动了 {moved} 个文件" + (f"，{len(errors)} 个失败" if errors else ""))
        self._load_auto_files(folder)
        messagebox.showinfo("完成", f"整理完成！\n成功移动 {moved} 个文件。" +
                            (f"\n失败 {len(errors)} 个" if errors else ""))

    # ── Tab: 批量重命名 ────────────────────────────────────────
    def _build_rename_tab(self):
        f = self.tab_rename
        # 工具栏
        toolbar = ctk.CTkFrame(f, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(15,5))

        ctk.CTkButton(toolbar, text="📂 添加文件", command=self._add_rename_files,
                      width=120).pack(side="left", padx=(0,8))
        ctk.CTkButton(toolbar, text="📁 添加文件夹", command=self._add_rename_folder,
                      width=120).pack(side="left", padx=(0,8))

        ctk.CTkLabel(toolbar, text="模板:").pack(side="left", padx=(10,5))
        self._rename_template_var = tk.StringVar(value="{name}{ext}")
        ctk.CTkEntry(toolbar, textvariable=self._rename_template_var,
                     placeholder_text="{name}_{num}{ext}", width=220).pack(side="left", padx=(0,8))

        ctk.CTkButton(toolbar, text="🔍 预览", command=self._preview_rename,
                      fg_color="#2d6a8a", hover_color="#1e4a6a",
                      width=80).pack(side="left", padx=(0,8))
        ctk.CTkButton(toolbar, text="✅ 执行重命名", command=self._run_rename,
                      fg_color=COLORS["accent"], hover_color="#c0354e",
                      width=110).pack(side="right")

        hint = ctk.CTkLabel(
            toolbar, text="语法: {name} {ext} {date} {num} {size}  例: photo_{num}_{date}{ext}",
            text_color=COLORS["subtext"], font=ctk.CTkFont(size=10)
        )
        hint.pack(side="bottom", padx=0, pady=(2,0))

        # 列表
        list_frame = ctk.CTkFrame(f, fg_color=COLORS["surface"], corner_radius=8)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(5,10))

        cols = ("原文件名", "新文件名", "路径")
        self._rename_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                         style="Dark.Treeview", selectmode="extended")
        for col in cols:
            self._rename_tree.heading(col, text=col)
            self._rename_tree.column(col, width=250)
        scroll = ttk.Scrollbar(list_frame, command=self._rename_tree.yview)
        self._rename_tree.configure(yscrollcommand=scroll.set)
        self._rename_tree.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        scroll.pack(side="right", fill="y", padx=(0,5), pady=5)

    def _add_rename_files(self):
        files = filedialog.askopenfilenames(title="选择文件")
        for fp in files:
            self._rename_preview.append({"path": fp, "new_name": None})
        self._refresh_rename_tree()

    def _add_rename_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    self._rename_preview.append({"path": path, "new_name": None})
        self._refresh_rename_tree()

    def _refresh_rename_tree(self):
        for row in self._rename_tree.get_children():
            self._rename_tree.delete(row)
        for i, item in enumerate(self._rename_preview):
            path = item["path"]
            name = os.path.basename(path)
            new_name = item.get("new_name") or name
            tag = "odd" if i % 2 == 0 else "even"
            self._rename_tree.insert("", "end", values=(name, new_name, os.path.dirname(path)), tags=(tag,))

    def _preview_rename(self):
        if not self._rename_preview:
            messagebox.showwarning("提示", "请先添加文件")
            return
        if not enforce_trial(len(self._rename_preview)):
            return
        template = self._rename_template_var.get() or "{name}{ext}"
        for i, item in enumerate(self._rename_preview):
            info = get_file_info(item["path"])
            if not info:
                continue
            new_name = (template
                .replace("{name}", os.path.splitext(info["name"])[0])
                .replace("{ext}", info["ext"])
                .replace("{date}", info["mtime"].strftime("%Y%m%d"))
                .replace("{num}", str(i+1).zfill(3))
                .replace("{size}", format_size(info["size"]).replace(" ","")))
            item["new_name"] = new_name
        self._refresh_rename_tree()
        self._status_var.set(f"预览完成，共 {len(self._rename_preview)} 个文件")

    def _run_rename(self):
        if not self._rename_preview:
            return
        renamed, errors = 0, []
        for item in self._rename_preview:
            if not item.get("new_name"):
                continue
            new_path = os.path.join(os.path.dirname(item["path"]), item["new_name"])
            try:
                os.rename(item["path"], new_path)
                item["path"] = new_path
                renamed += 1
            except Exception as e:
                errors.append(f"{os.path.basename(item['path'])}: {e}")
        self._rename_preview = []
        self._refresh_rename_tree()
        self._status_var.set(f"重命名完成：{renamed} 个成功" + (f"，{len(errors)} 个失败" if errors else ""))
        messagebox.showinfo("完成", f"重命名完成！\n成功 {renamed} 个" + (f"\n失败 {len(errors)} 个" if errors else ""))

    # ── Tab: 重复文件 ─────────────────────────────────────────
    def _build_dup_tab(self):
        f = self.tab_dup
        toolbar = ctk.CTkFrame(f, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(15,5))

        self._dup_folder_var = tk.StringVar()
        ctk.CTkEntry(toolbar, textvariable=self._dup_folder_var,
                     placeholder_text="选择要检测的文件夹...", width=400).pack(side="left", padx=(0,8))
        ctk.CTkButton(toolbar, text="浏览...", command=self._browse_dup_folder,
                      width=80).pack(side="left", padx=(0,15))
        ctk.CTkButton(toolbar, text="🔍 开始检测", command=self._run_dup_check,
                      fg_color=COLORS["accent"], hover_color="#c0354e",
                      width=110).pack(side="right")

        self._dup_progress = ctk.CTkProgressBar(f, progress_color=COLORS["accent"])
        self._dup_progress.pack(fill="x", padx=15, pady=(0,5))
        self._dup_progress.set(0)

        list_frame = ctk.CTkFrame(f, fg_color=COLORS["surface"], corner_radius=8)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(5,10))

        cols = ("文件名", "大小", "路径", "MD5")
        self._dup_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                      style="Dark.Treeview", selectmode="extended")
        for col in cols:
            self._dup_tree.heading(col, text=col)
            self._dup_tree.column(col, width=200)
        scroll = ttk.Scrollbar(list_frame, command=self._dup_tree.yview)
        self._dup_tree.configure(yscrollcommand=scroll.set)
        self._dup_tree.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        scroll.pack(side="right", fill="y", padx=(0,5), pady=5)

        btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0,5))
        ctk.CTkButton(btn_frame, text="🗑 删除选中", command=self._delete_dup,
                      fg_color="#c0392b", hover_color="#962d22",
                      width=120).pack(side="left")

    def _browse_dup_folder(self):
        folder = filedialog.askdirectory(title="选择要检测重复文件的文件夹")
        if folder:
            self._dup_folder_var.set(folder)

    def _run_dup_check(self):
        folder = self._dup_folder_var.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("提示", "请先选择文件夹")
            return
        if not enforce_trial(9999):
            return

        self._dup_progress.set(0)
        self._status_var.set("正在扫描文件...")
        self._dup_results = []
        thread = threading.Thread(target=self._dup_check_thread, args=(folder,))
        thread.start()

    def _dup_check_thread(self, folder):
        files = []
        for root, dirs, filenames in os.walk(folder):
            for fn in filenames:
                fp = os.path.join(root, fn)
                info = get_file_info(fp)
                if info:
                    info["path"] = fp
                    files.append(info)

        total = len(files)
        if total == 0:
            self.after(0, lambda: self._dup_done([]))
            return

        hash_map = {}
        for i, info in enumerate(files):
            h = md5(info["path"])
            if h in hash_map:
                hash_map[h].append(info)
            else:
                hash_map[h] = [info]
            self.after(0, lambda p=i/total: self._dup_progress.set(p))

        dups = [group for group in hash_map.values() if len(group) > 1]
        flat = []
        for group in dups:
            for item in group:
                flat.append(item)
        self.after(0, lambda: self._dup_done(flat[:50]))

    def _dup_done(self, results):
        for row in self._dup_tree.get_children():
            self._dup_tree.delete(row)
        self._dup_results = results
        limit = TRIAL_DUP_LIMIT if not is_paid() else len(results)
        for i, info in enumerate(results[:limit]):
            h = md5(info["path"])
            self._dup_tree.insert("", "end", values=(
                info["name"], format_size(info["size"]),
                info["dir"], h[:12]+"..."
            ))
        self._dup_progress.set(1)
        self._status_var.set(f"发现 {len(results)} 个重复文件（显示前 {limit} 个）")

    def _delete_dup(self):
        selected = self._dup_tree.selection()
        if not selected:
            return
        if not messagebox.askyesno("确认", f"确定删除选中的 {len(selected)} 个文件？此操作不可恢复！"):
            return
        deleted = 0
        for item in selected:
            path = self._dup_tree.item(item)["values"][2] + "\\" + self._dup_tree.item(item)["values"][0]
            try:
                os.remove(path)
                self._dup_tree.delete(item)
                deleted += 1
            except Exception as e:
                pass
        self._status_var.set(f"已删除 {deleted} 个文件")

    # ── Tab: 规则管理 ─────────────────────────────────────────
    def _build_rules_tab(self):
        f = self.tab_rules
        toolbar = ctk.CTkFrame(f, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(15,5))
        ctk.CTkButton(toolbar, text="➕ 新建规则", command=self._new_rule,
                      width=120).pack(side="left", padx=(0,8))
        ctk.CTkButton(toolbar, text="💾 保存规则", command=self._save_rules,
                      fg_color=COLORS["success"], hover_color="#3baa87",
                      width=120).pack(side="right")

        frame = ctk.CTkFrame(f, fg_color=COLORS["surface"], corner_radius=8)
        frame.pack(fill="both", expand=True, padx=15, pady=(5,10))

        cols = ("规则名称", "匹配条件", "目标文件夹")
        self._rules_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                        style="Dark.Treeview")
        for col in cols:
            self._rules_tree.heading(col, text=col)
            self._rules_tree.column(col, width=280)
        scroll = ttk.Scrollbar(frame, command=self._rules_tree.yview)
        self._rules_tree.configure(yscrollcommand=scroll.set)
        self._rules_tree.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        scroll.pack(side="right", fill="y", padx=(0,5), pady=5)

    def _new_rule(self):
        win = ctk.CTkToplevel(self)
        win.title("新建规则")
        win.geometry("500x280")
        win.grab_set()
        ctk.CTkLabel(win, text="规则名称", text_color=COLORS["text"]).place(x=20, y=20)
        name_entry = ctk.CTkEntry(win, width=440)
        name_entry.place(x=20, y=48)

        ctk.CTkLabel(win, text="匹配条件（扩展名/关键词/大小范围）").place(x=20, y=85)
        cond_entry = ctk.CTkEntry(win, width=440, placeholder_text="如: .pdf 或 关键词:报告 或 size>10MB")
        cond_entry.place(x=20, y=113)

        ctk.CTkLabel(win, text="目标文件夹").place(x=20, y=150)
        target_entry = ctk.CTkEntry(win, width=360)
        target_entry.place(x=20, y=178)
        ctk.CTkButton(win, text="浏览", width=60,
                      command=lambda: target_entry.insert(0, filedialog.askdirectory() or "")).place(x=390, y=178)

        def save():
            name = name_entry.get().strip()
            cond = cond_entry.get().strip()
            target = target_entry.get().strip()
            if not name or not target:
                messagebox.showwarning("提示", "请填写规则名称和目标文件夹")
                return
            self._rules.append({"name": name, "condition": cond, "target": target})
            self._refresh_rules()
            win.destroy()

        ctk.CTkButton(win, text="保存", command=save, fg_color=COLORS["accent"],
                      hover_color="#c0354e", width=200).place(x=150, y=230)

    def _refresh_rules(self):
        for row in self._rules_tree.get_children():
            self._rules_tree.delete(row)
        for r in self._rules:
            self._rules_tree.insert("", "end", values=(r["name"], r["condition"], r["target"]))

    def _save_rules(self):
        path = filedialog.asksaveasfilename(defaultextension=".fsrule",
                                             filetypes=[("规则文件","*.fsrule")],
                                             title="保存规则")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._rules, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("完成", f"规则已保存到:\n{path}")

    # ── 付费对话框 ─────────────────────────────────────────────
    def _show_pay_dialog(self):
        if self._paid:
            messagebox.showinfo("已授权", "您已购买正式版，感谢支持！")
            return
        win = ctk.CTkToplevel(self)
        win.title("授权解锁")
        win.geometry("520x420")
        win.grab_set()
        win.resizable(False, False)

        ctk.CTkLabel(win, text="💎 FolderSorter Pro 授权解锁",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20,5))
        ctk.CTkLabel(win, text="一次付费，终身使用，后续版本免费升级",
                     text_color=COLORS["subtext"]).pack()

        box = ctk.CTkFrame(win, fg_color=COLORS["surface"], corner_radius=10)
        box.pack(fill="x", padx=30, pady=15)

        ctk.CTkLabel(box, text="¥9.9", font=ctk.CTkFont(size=36, weight="bold"),
                     text_color=COLORS["accent"]).pack(pady=(15,0))
        ctk.CTkLabel(box, text="终身授权 · 无文件数限制 · 永久免费更新",
                     text_color=COLORS["subtext"], font=ctk.CTkFont(size=11)).pack(pady=(0,15))

        steps = ctk.CTkFrame(win, fg_color="transparent")
        steps.pack(fill="x", padx=30, pady=(0,10))
        for i, step in enumerate([
            "① 转账 ¥9.9 到支付宝",
            "② 联系支付宝反馈转账截图",
            "③ 收到授权码后填入下方并激活"
        ]):
            ctk.CTkLabel(steps, text=step, text_color=COLORS["text"]).pack(anchor="w", pady=2)

        # 支付宝收款码（留空让用户自己填）
        ctk.CTkLabel(win, text="↓ 支付宝收款码截图（请联系我发送）↓",
                     text_color=COLORS["subtext"], font=ctk.CTkFont(size=10)).pack()

        ctk.CTkLabel(win, text="输入授权码:", anchor="w").pack(padx=30, fill="x")
        code_entry = ctk.CTkEntry(win, placeholder_text="FSP-XXXX-XXXX-XXXX", width=460)
        code_entry.pack(padx=30, pady=(5,0))

        def do_activate():
            code = code_entry.get().strip()
            if activate_paid(code):
                self._paid = True
                self._paid_btn.configure(text="💎 已授权", fg_color=COLORS["success"])
                win.destroy()
                messagebox.showinfo("授权成功", "感谢您的支持！所有功能已解锁。")
                self._status_var.set("已授权正版，解锁全部功能")
            else:
                messagebox.showerror("授权失败", "授权码无效，请检查后重试。")

        ctk.CTkButton(win, text="🔓 激活授权", command=do_activate,
                      fg_color=COLORS["accent"], hover_color="#c0354e",
                      width=460, height=38).pack(pady=15)

        ctk.CTkLabel(win, text="或联系微信/支付宝: support@foldersorter.com",
                     text_color=COLORS["subtext"], font=ctk.CTkFont(size=10)).pack(pady=(0,15))

# ── 入口 ──────────────────────────────────────────────────────
if __name__ == "__main__":
    app = FolderSorterApp()
    app.mainloop()
