#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并补全已生成的网页的统计代码.pyw

【怎么用】
双击就行：扫一遍站点里所有已生成的 html，缺统计代码的在 </body> 前补一份，
补了几个、跳过几个，最后弹框告诉你。已经有了就跳过，所以可以反复双击。

命令行也能用：

    python tools/检查并补全已生成的网页的统计代码.pyw            补全
    python tools/检查并补全已生成的网页的统计代码.pyw --dry-run  只说要改哪些，不写盘

【注意】
这个脚本是独立的：别的脚本（build_and_update / delete_and_update / update_*）
都不会调用它。新生成的文章要补统计代码，需要自己再双击一次。

【不扫哪些目录】
.git、_backup、tools（脚本目录不是网页）
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

SNIPPET = ('<script defer src="https://ana.qbzlw.com/track.js" '
           'data-key="b5611733164bf3688965889e8021091b"></script>')

# 认这一串就说明已经加过了（域名或 key 任一对得上都算）
MARKERS = ("ana.qbzlw.com", "b5611733164bf3688965889e8021091b")

SKIP_DIRS = {".git", "_backup", "tools", "node_modules"}

HAS_CONSOLE = sys.stdout is not None      # 双击 .pyw 时是 None

try:
    import tkinter as tk
    from tkinter import messagebox
    HAVE_TK = True
except Exception:
    HAVE_TK = False


def say(msg=""):
    if HAS_CONSOLE:
        print(msg)


def finish(title, msg):
    """双击时用弹框报结果；有控制台就只打日志。"""
    if HAS_CONSOLE or not HAVE_TK:
        return
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showinfo(title, msg, parent=root)
    root.destroy()


def targets():
    """找出所有该检查的 html 文件。"""
    out = []
    for p in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts[:-1]):
            continue
        out.append(p)
    return sorted(out)


def has_snippet(text):
    return any(m in text for m in MARKERS)


def insert_snippet(text):
    """插在 </body> 前面；找不到 </body> 就返回 None。"""
    i = text.rfind("</body>")
    if i == -1:
        return None
    line_start = text.rfind("\n", 0, i) + 1
    indent = text[line_start:i]
    if indent.strip():                      # </body> 前面有别的东西，用标准缩进
        indent = "  "
    return text[:i] + indent + SNIPPET + "\n" + text[i:]


def main():
    dry = "--dry-run" in sys.argv

    files = targets()
    if not files:
        say("没找到任何 html 文件。")
        finish("没有网页", "站点里一个 html 都没找到。")
        return

    added, skipped, failed = [], 0, []

    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8")
        if has_snippet(text):
            skipped += 1
            continue
        new = insert_snippet(text)
        if new is None:
            failed.append(rel + "（没有 </body>）")
            continue
        added.append(rel)
        if not dry:
            p.write_text(new, encoding="utf-8", newline="\n")

    lines = ["检查 %d 个页面" % len(files)]
    if dry:
        lines.append("（dry-run，没有写盘）")
    if added:
        lines.append("%s %d 个：" % ("会补上" if dry else "已补上", len(added)))
        lines.extend("  " + r for r in added)
    if skipped:
        lines.append("已有，跳过 %d 个" % skipped)
    if failed:
        lines.append("跳过 %d 个：" % len(failed))
        lines.extend("  " + r for r in failed)
    if not added:
        lines.append("全站统计代码都齐了。")

    for line in lines:
        say(line)
    finish("统计代码检查", "\n".join(lines))


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
        detail = traceback.format_exc()
        say(detail)
        finish("脚本出错了", detail)
