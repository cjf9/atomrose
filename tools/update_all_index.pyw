#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_all_index.pyw —— 总脚本：依次刷四个 index，只弹一次框。

双击运行就行。顺序是 随笔 -> 自选集 -> 工作 -> 首页。
顺序其实无所谓：首页是直接扫目录拿数据的，不读那三个 index.html。

平时你只需要跑这一个。四个子脚本都在 tools/ 里，不用单独双击，
真要单独调某一个，用命令行跑它们就行（它们不弹框，只往控制台打）。

可选参数：

    python update_all_index.pyw --dry-run   只说打算改什么，不写盘
    python update_all_index.pyw --no-gui    不弹框，只往控制台打
    python update_all_index.pyw --quiet     不打印链接体检
    python update_all_index.pyw --help      看这份说明
"""

import sys

import sitecore as sc
import update_collection_index
import update_essay_index
import update_home_index
import update_work_index

TASKS = [
    update_essay_index,
    update_collection_index,
    update_work_index,
    update_home_index,
]

try:
    import tkinter as tk
    from tkinter import messagebox
    HAVE_TK = True
except Exception:                      # 极少数没带 tkinter 的环境
    HAVE_TK = False

HAS_CONSOLE = sys.stdout is not None    # 双击 .pyw 时是 None
NO_GUI = False
OUT = []


def say(msg=""):
    OUT.append(msg)
    if HAS_CONSOLE:
        print(msg)


def _dialog(kind, title, msg):
    if NO_GUI or not HAVE_TK:
        return
    root = tk.Tk()
    root.withdraw()
    try:
        getattr(messagebox, kind)(title, msg, parent=root)
    finally:
        root.destroy()


def show_error(title, msg):
    say("[错误] %s" % title)
    say(msg)
    _dialog("showerror", title, msg)


def finish(title):
    """双击运行时没有控制台，把这次攒的输出一次性弹出来。"""
    if HAS_CONSOLE:
        return
    _dialog("showinfo", title, "\n".join(OUT))


def link_check():
    """全站链接体检：只报不改。"""
    pages = [sc.SITE_ROOT / "index.html"]
    for key, _ in sc.SECTIONS:
        pages += sorted((sc.SITE_ROOT / key).glob("*.html"))

    broken = sc.check_links(pages)
    say("")
    if broken:
        say("链接体检：%d 处指向不存在的文件（只报不改）" % len(broken))
        for page, target in broken:
            say("  %s  ->  %s" % (sc.rel(page), target))
    else:
        say("链接体检：干净，没发现死链。")


def main():
    global NO_GUI
    argv = sys.argv[1:]

    if any(a in ("-h", "--help", "-?", "/?") for a in argv):
        say(__doc__)
        if not HAS_CONSOLE:
            _dialog("showinfo", "update_all_index.pyw 用法", __doc__)
        return

    NO_GUI = "--no-gui" in argv
    dry = "--dry-run" in argv
    quiet = "--quiet" in argv

    try:
        for task in TASKS:
            for line in task.run(dry=dry):
                say(line)
    except ValueError as e:            # sitecore 里找不到标记圈之类的
        show_error("出错了", str(e))
        return
    except Exception:
        import traceback
        show_error("脚本出错了", traceback.format_exc())
        return

    if not quiet:
        link_check()

    if dry:
        say("")
        say("（dry-run，什么都没写盘）")

    finish("索引已刷新")


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
