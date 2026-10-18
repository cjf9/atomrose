#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
delete_and_update.pyw —— 删文章，删得放心。

【功能】
列出 essays/ collection/ work/ 里的全部文章，你挑一篇，它给你看标题和摘要，
可以在浏览器里打开确认，确认后连页面带资源目录一起删掉。

【注意：这是真删，不进回收站，删了就没了。】
所以流程里有两道确认：先在浏览器里看一眼，再在弹框里点"是"。
不想删就别点那个"是"。

双击运行会开一个窗口：上面列文章，下面显示这一篇的摘要，底下几个按钮。

删完会自动刷新四个索引页（随笔 → 自选集 → 工作 → 首页）。

【命令行】
    python delete_and_update.pyw            开窗口（双击就是这条）
    python delete_and_update.pyw --cli      不开窗口，在终端里问答
    python delete_and_update.pyw --no-open  配合 --cli：不自动开浏览器，只打出地址
    python delete_and_update.pyw --help     看这份说明

【预览】
"在浏览器里看"走 http://127.0.0.1:8080/（你自己起的预览服务）。
那个服务没开着的话，会退而用 file:// 打开 —— 页面没样式，但内容看得见。
"""

import re
import shutil
import socket
import sys
import webbrowser
from datetime import datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent    # 站点根目录（tools/ 的上一层）

# 三个栏目都要能删。work 的文章也是文章，资源同样在 assets/<文章文件名>/ 下。
SECTIONS = [
    ("essays", "随笔"),
    ("collection", "自选集"),
    ("work", "工作"),
]

ASSETS = ROOT / "assets"

PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 8080              # 跟你自己起的预览服务保持一致
PREVIEW_LINES = 2                # 摘要显示几个文本块
PREVIEW_CHARS = 64               # 摘要最多显示多少字

try:
    import tkinter as tk
    from tkinter import messagebox
    HAVE_TK = True
except Exception:                # 极少数没带 tkinter 的环境
    HAVE_TK = False

HAS_CONSOLE = sys.stdout is not None   # 双击 .pyw 时是 None


# ── 弹框 ────────────────────────────────────────────────────────────

def _dialog(kind, title, msg):
    if not HAVE_TK:
        return
    root = tk.Tk()
    root.withdraw()
    try:
        getattr(messagebox, kind)(title, msg, parent=root)
    finally:
        root.destroy()


def show_error(title, msg):
    if HAS_CONSOLE:
        print("[错误] %s\n%s" % (title, msg))
    _dialog("showerror", title, msg)


def show_help(text):
    if HAS_CONSOLE:
        print(text)
    else:
        _dialog("showinfo", "delete_and_update.pyw 用法", text)


# ── 认文件名里的时间 ────────────────────────────────────────────────

STEM = re.compile(r"^([0-9a-fA-F]+)(?:-(\d+))?$")


def parse_stem(stem):
    m = STEM.match(stem)
    if not m:
        return None, 0
    try:
        raw = str(int(m.group(1), 16)).rjust(12, "0")
        return datetime.strptime(raw, "%Y%m%d%H%M"), int(m.group(2) or 1)
    except ValueError:
        return None, 0


# ── 从页面里读标题和摘要 ────────────────────────────────────────────

TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|blockquote|tr|section|article)>", re.I)
ANY_TAG = re.compile(r"<[^>]+>")


def clean_html(chunk):
    chunk = SCRIPT.sub("", chunk)
    chunk = BLOCK_END.sub("\n", chunk)
    chunk = ANY_TAG.sub("", chunk)
    return unescape(chunk)


def page_title(html, fallback):
    for pattern in (TITLE, H1):
        m = pattern.search(html)
        if m:
            text = re.sub(r"\s+", " ", clean_html(m.group(1))).strip()
            if text:
                return text
    return fallback


def page_summary(html, title):
    body = html
    for tag in ("article", "main"):
        m = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), html, re.I | re.S)
        if m:
            body = m.group(1)
            break
    blocks = []
    for line in clean_html(body).split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        # 正文第一块通常就是大标题，跟上面已经显示的标题重复，跳过
        if title and (line == title or (len(line) >= 6 and (line in title or title in line))):
            continue
        blocks.append(line)
        if len(blocks) >= PREVIEW_LINES:
            break
    text = " / ".join(blocks)
    return text[:PREVIEW_CHARS] + ("..." if len(text) > PREVIEW_CHARS else "")


# ── 收集文章 ────────────────────────────────────────────────────────

def collect():
    items = []
    for key, cn in SECTIONS:
        d = ROOT / key
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.html")):
            if p.name == "index.html" or p.name.startswith("."):
                continue
            try:
                html = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                html = ""
            when, seq = parse_stem(p.stem)
            title = page_title(html, p.stem)
            items.append({
                "section": key,
                "section_cn": cn,
                "file": p,
                "stem": p.stem,
                "rel": "%s/%s" % (key, p.name),
                "title": title,
                "summary": page_summary(html, title),
                "when": when,
                "seq": seq,
            })
    items.sort(key=lambda a: (a["when"] is not None, a["when"] or datetime.min, a["seq"], a["stem"]),
               reverse=True)
    return items


def describe(item):
    """删除前给人看的清单。"""
    lines = ["标题：%s" % item["title"], "页面：%s" % item["rel"]]
    assets = ASSETS / item["stem"]
    if assets.is_dir():
        files = [f for f in assets.rglob("*") if f.is_file()]
        size = sum(f.stat().st_size for f in files)
        lines.append("资源：assets/%s/（%d 个文件，%.1f KB）"
                     % (item["stem"], len(files), size / 1024.0))
    else:
        lines.append("资源：无")
    return lines


# ── 浏览器预览 ──────────────────────────────────────────────────────

def server_alive():
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect((PREVIEW_HOST, PREVIEW_PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def preview_url(item):
    if server_alive():
        return "http://%s:%d/%s" % (PREVIEW_HOST, PREVIEW_PORT, item["rel"]), True
    return item["file"].as_uri(), False


# ── 删除 ────────────────────────────────────────────────────────────

def inside(path):
    p = path.resolve()
    return p == ROOT or ROOT in p.parents


def do_delete(item):
    """直接永久删除（不进回收站），返回一串给人看的说明。"""
    page = item["file"]
    assets = ASSETS / item["stem"]

    if not inside(page) or (assets.exists() and not inside(assets)):
        return ["路径不在站点目录里，拒绝删除。"]

    lines = []
    page.unlink()
    lines.append("已删除 %s" % page.relative_to(ROOT).as_posix())
    if assets.is_dir():
        shutil.rmtree(assets)
        lines.append("已删除 assets/%s/" % assets.name)
    return lines


def refresh_indexes():
    """删完按 随笔 → 自选集 → 工作 → 首页 的顺序刷新索引，返回说明行。"""
    out = []
    tools_root = str(Path(__file__).resolve().parent)
    if tools_root not in sys.path:
        sys.path.insert(0, tools_root)
    for modname in ("update_essay_index", "update_collection_index",
                    "update_work_index", "update_home_index"):
        try:
            mod = __import__(modname)
            res = mod.run()
            if isinstance(res, (list, tuple)):
                out.extend(str(x) for x in res)
        except Exception as e:
            out.append("× %s 失败：%s" % (modname, e))
    return out


# ── 图形界面（双击走这条） ──────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root = root
        self.items = []

        top = tk.Frame(root)
        top.pack(fill="x", padx=14, pady=(14, 6))
        self.count = tk.Label(top, text="", anchor="w")
        self.count.pack(side="left")
        tk.Button(top, text="重新扫描", width=10, command=self.reload).pack(side="right")

        box = tk.Frame(root)
        box.pack(fill="both", expand=True, padx=14)
        sb = tk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        self.list = tk.Listbox(box, yscrollcommand=sb.set, activestyle="none",
                               exportselection=False)
        self.list.pack(side="left", fill="both", expand=True)
        sb.config(command=self.list.yview)
        self.list.bind("<<ListboxSelect>>", self.on_select)

        tk.Label(root, text="这一篇长这样：", anchor="w").pack(fill="x", padx=14, pady=(12, 3))
        self.preview = tk.Text(root, height=7, wrap="word", relief="solid", borderwidth=1,
                               background="#fbfbfb")
        self.preview.pack(fill="x", padx=14)
        self.preview.config(state="disabled")

        bar = tk.Frame(root)
        bar.pack(fill="x", padx=14, pady=12)
        tk.Label(bar, text="删除是永久的，不进回收站。", anchor="w",
                 foreground="#b91c1c").pack(side="left")
        tk.Button(bar, text="在浏览器里看", width=15, command=self.open_preview).pack(side="right")
        tk.Button(bar, text="删除选中", width=12, command=self.delete).pack(side="right", padx=10)

        self.reload()

    # ── 列表 ──
    def reload(self):
        self.items = collect()
        self.list.delete(0, "end")
        for i, it in enumerate(self.items, 1):
            self.list.insert("end", "【%d】%s   %s" % (i, it["rel"], it["title"]))
        self.count.config(text="共 %d 篇" % len(self.items))
        if self.items:
            self.list.selection_clear(0, "end")
            self.list.selection_set(0)
            self.list.activate(0)
            self.on_select()
        else:
            self.set_preview("栏目里一篇文章都没有。")

    def current(self):
        sel = self.list.curselection()
        if not sel:
            return None
        return self.items[sel[0]]

    def set_preview(self, text):
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("end", text)
        self.preview.config(state="disabled")

    def on_select(self, event=None):
        it = self.current()
        if not it:
            self.set_preview("在左边选一篇。")
            return
        lines = [it["title"], "", it["summary"]]
        lines += [""] + describe(it)[1:]
        self.set_preview("\n".join(lines))

    # ── 按钮 ──
    def open_preview(self):
        it = self.current()
        if not it:
            messagebox.showinfo("没选", "先在上面选一篇。", parent=self.root)
            return
        url, live = preview_url(it)
        webbrowser.open(url)
        if not live:
            messagebox.showinfo(
                "预览服务没开",
                "本地预览服务 %s:%d 没开着，改用文件方式打开了，页面会没样式。\n\n"
                "想看正常样式，先把预览服务起起来再点一次。" % (PREVIEW_HOST, PREVIEW_PORT),
                parent=self.root)

    def delete(self):
        it = self.current()
        if not it:
            messagebox.showinfo("没选", "先在上面选一篇。", parent=self.root)
            return
        lines = describe(it) + ["", "这是永久删除，不进回收站，删了就没了。", "确定吗？"]
        if not messagebox.askyesno("确认删除", "\n".join(lines),
                                   parent=self.root, default="no", icon="warning"):
            return
        do_delete(it)
        refresh_indexes()
        self.reload()


def run_gui():
    if not HAVE_TK:
        print("这台机器的 Python 没带 tkinter，开不了窗口。")
        print("改用命令行模式：python delete_and_update.pyw --cli")
        return
    root = tk.Tk()
    root.title("删除文章 - Atomrose")
    root.geometry("780x580")
    root.minsize(640, 460)
    App(root)
    root.mainloop()


# ── 命令行问答（python delete_and_update.pyw --cli） ───────────────────────────

def run_cli(no_open=False):
    if not HAS_CONSOLE:
        show_error("没有控制台", "命令行模式需要有控制台。直接双击就是用窗口模式。")
        return

    items = collect()
    if not items:
        print("栏目里一篇文章都没有。")
        return

    while True:
        print()
        print("  共 %d 篇（永久删除，不进回收站）" % len(items))
        print()
        for i, it in enumerate(items, 1):
            print("  【%d】%s   %s" % (i, it["rel"], it["title"]))
            if it["summary"]:
                print("        %s" % it["summary"])

        try:
            choice = input("\n  删哪一篇？（编号 / q 退出 / r 重新列出）：").strip().lower()
        except EOFError:
            print()
            return
        if choice in ("", "q", "quit", "exit"):
            return
        if choice in ("r", "refresh"):
            items = collect()
            if not items:
                print("栏目里已经没有文章了。")
                return
            continue
        if not choice.isdigit() or not 1 <= int(choice) <= len(items):
            print("\n  没这个编号，重新选。")
            continue

        it = items[int(choice) - 1]
        print()
        print("  ── 你选的是这一篇 ──")
        for line in describe(it):
            print("  %s" % line)

        url, live = preview_url(it)
        print("\n  预览：%s" % url)
        if not live:
            print("  ! 预览服务 %s:%d 没开着，页面会没样式。" % (PREVIEW_HOST, PREVIEW_PORT))
        if not no_open:
            webbrowser.open(url)

        print("\n  看完把页面关掉，再回这里回答。")
        try:
            ans = input("  确认删除？输入 y 确认，其他任意键取消：").strip().lower()
        except EOFError:
            ans = ""
        if ans in ("y", "yes"):
            for line in do_delete(it):
                print("  %s" % line)
            print()
            for line in refresh_indexes():
                print("  %s" % line)
        else:
            print("  取消，什么都没删。")

        items = collect()
        if not items:
            print("\n栏目里已经没有文章了。")
            return


# ── 主流程 ──────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    if any(a in ("-h", "--help", "-?", "/?") for a in argv):
        show_help(__doc__)
        return
    if "--cli" in argv:
        run_cli(no_open="--no-open" in argv)
    else:
        run_gui()


if __name__ == "__main__":
    if HAS_CONSOLE:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        main()
    except Exception:
        import traceback
        show_error("脚本出错了", traceback.format_exc())
