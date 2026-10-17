#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update.pyw —— 对账工具，只刷新三个 index.html（首页 + 随笔 + 小说与诗）。

【功能】
它不管页面是谁生成的：build.pyw 生成的、AI 生成的、你手写的，一律只看
"目录里有哪些 .html"。

它做四件事：
  1. essays/ 和 fiction/ 各目录下的文章 -> 填进该栏目自己的 index.html
  2. 这两个栏目里的全部文章 -> 按文件名时间倒序取最新 10 篇，填进外层 index.html
     （最新那一篇带 new 标签）
  3. 全站文章的标题清单 -> 内嵌进外层 index.html，供搜索框使用
  4. 顺手体检：所有页面里指向站内的链接，指向不存在的文件就报出来（只报不改）

【work.html 不归它管】
工作那一页是手写的展示页（项目直接铺开），不是文章列表，所以脚本不碰它，
只把它算进链接体检。加项目、改文案，你在 work.html 里直接改。

它只改标记圈里的内容：

    <!-- atomrose:list:start -->  ...  <!-- atomrose:list:end -->

圈外面你自己写的东西（栏目说明、友情链接、手写段落）一律不碰。

双击运行即可。下面是可选的命令行参数：

    python update.pyw             直接更新
    python update.pyw --dry-run   只说打算改什么，不写盘
    python update.pyw --quiet     不打印体检结果
    python update.pyw --no-gui    不弹框，只往控制台打
    python update.pyw --help      看这份说明

【什么时候要跑】
加了文章、搬了文章、删了文章、改了文章标题，都跑一次。
"""

import json
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 栏目：目录名 -> 索引里显示的名字。加栏目就在这里加一行，并建好目录和 index.html。
# 注意 work 不在列表里 —— 工作那一页是手写的 work.html，不参与自动列表。
SECTIONS = [
    ("essays", "随笔"),
    ("fiction", "小说与诗"),
]

TOP_N = 10                     # 首页放几篇（不够就有多少放多少）
HEX_WIDTH = 10                 # 文件名时间戳的十六进制位数
LIST_START = "<!-- atomrose:list:start -->"
LIST_END = "<!-- atomrose:list:end -->"
SEARCH_ID = "atomrose-search-index"
LIST_INDENT = "      "


# ── 输出与弹框 ──────────────────────────────────────────────────────
# 双击 .pyw 是用 pythonw 跑的，没有控制台：print 没地方去。
# 所以输出都走 say()，双击时最后用弹框把这次结果显示一遍。

try:
    import tkinter as tk
    from tkinter import messagebox
    HAVE_TK = True
except Exception:                      # 极少数没带 tkinter 的环境
    HAVE_TK = False

HAS_CONSOLE = sys.stdout is not None    # 双击 .pyw 时是 None
NO_GUI = False                          # --no-gui 打开
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
    """双击运行时没有控制台，把这次攒的输出用弹框显示一遍。"""
    if HAS_CONSOLE:
        return
    _dialog("showinfo", title, "\n".join(OUT))


def show_help(text):
    say(text)
    if HAS_CONSOLE:
        return
    _dialog("showinfo", "update.pyw 用法", text)


# ── 文件名 -> 时间 ──────────────────────────────────────────────────

STEM = re.compile(r"^([0-9a-fA-F]+)(?:-(\d+))?$")


def parse_stem(stem):
    """时间十六进制文件名 -> (datetime, 序号)；认不出来就返回 (None, 0)。"""
    m = STEM.match(stem)
    if not m:
        return None, 0
    try:
        raw = str(int(m.group(1), 16)).rjust(12, "0")
        return datetime.strptime(raw, "%Y%m%d%H%M"), int(m.group(2) or 1)
    except ValueError:
        return None, 0


# ── 从页面里读标题 ──────────────────────────────────────────────────

TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TAGS = re.compile(r"<[^>]+>")


def page_title(path, fallback):
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fallback
    for pattern in (TITLE, H1):
        m = pattern.search(html)
        if m:
            text = unescape(TAGS.sub("", m.group(1)))
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return text
    return fallback


# ── 收集文章 ────────────────────────────────────────────────────────

def sort_key(a):
    return (a["when"] is not None, a["when"] or datetime.min, a["seq"], a["stem"])


def collect():
    site = {}
    for key, cn in SECTIONS:
        d = ROOT / key
        items = []
        if not d.is_dir():
            print("！ 没有目录 %s/，先建好再跑。" % key)
            site[key] = items
            continue
        for p in sorted(d.glob("*.html")):
            if p.name == "index.html" or p.name.startswith("."):
                continue
            when, seq = parse_stem(p.stem)
            items.append({
                "section": key,
                "section_cn": cn,
                "file": p,
                "stem": p.stem,
                "title": page_title(p, p.stem),
                "url": "/%s/%s" % (key, p.name),
                "when": when,
                "seq": seq,
            })
        items.sort(key=sort_key, reverse=True)
        site[key] = items
    return site


# ── 改写标记圈 ──────────────────────────────────────────────────────

def splice_list(text, path, entries):
    i, j = text.find(LIST_START), text.find(LIST_END)
    if i == -1 or j == -1 or j < i:
        raise SystemExit(
            "× %s 里找不到标记圈，没动它。需要这两行（顺序别反）：\n  %s\n  %s"
            % (path.relative_to(ROOT).as_posix(), LIST_START, LIST_END)
        )
    nl = text.rfind("\n", 0, i)
    indent = text[nl + 1:i] if nl != -1 else ""
    if indent.strip():          # 起始标记不在行首，就按标准缩进处理
        indent = LIST_INDENT
    body = "\n".join(entries)
    block = LIST_START + (("\n" + body) if body else "") + "\n" + indent + LIST_END
    return text[:i] + block + text[j + len(LIST_END):]


SCRIPT = None


def splice_search(text, path, payload):
    global SCRIPT
    if SCRIPT is None:
        SCRIPT = re.compile(
            r'(<script[^>]*\bid\s*=\s*["\']%s["\'][^>]*>)(.*?)(</script>)' % re.escape(SEARCH_ID),
            re.I | re.S,
        )
    m = SCRIPT.search(text)
    if not m:
        raise SystemExit(
            "× %s 里找不到 <script id=\"%s\">，搜索清单没写进去。"
            % (path.relative_to(ROOT).as_posix(), SEARCH_ID)
        )
    return text[: m.end(1)] + "\n" + payload + "\n" + text[m.end(2):]


def write_if_changed(path, text, dry):
    old = None
    if path.is_file():
        old = path.read_text(encoding="utf-8")
    if old == text:
        return False
    if not dry:
        path.write_text(text, encoding="utf-8", newline="\n")
    return True


# ── 链接体检 ────────────────────────────────────────────────────────

LINK = re.compile(r'\b(?:href|src)\s*=\s*["\'](/[^"\']*)["\']', re.I)


def resolve(target):
    t = target.split("#")[0].split("?")[0]
    if t in ("", "/"):
        return ROOT / "index.html"
    p = ROOT / t.lstrip("/")
    return (p / "index.html") if t.endswith("/") else p


def check_links(pages):
    broken = []
    for page in pages:
        try:
            html = page.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        seen = set()
        for target in LINK.findall(html):
            if target in seen:
                continue
            seen.add(target)
            if not resolve(target).is_file():
                broken.append((page, target))
    return broken


# ── 主流程 ──────────────────────────────────────────────────────────

def main():
    global NO_GUI
    argv = sys.argv[1:]

    if any(a in ("-h", "--help", "-?", "/?") for a in argv):
        show_help(__doc__)
        return

    NO_GUI = "--no-gui" in argv
    dry = "--dry-run" in argv
    quiet = "--quiet" in argv

    site = collect()
    root_index = ROOT / "index.html"
    if not root_index.is_file():
        show_error("找不到首页", "没有这个文件：\n%s" % root_index)
        return

    changed, kept = [], []
    total = 0

    # 1. 两个栏目的索引
    for key, cn in SECTIONS:
        items = site[key]
        total += len(items)
        d = ROOT / key
        idx = d / "index.html"
        if not idx.is_file():
            say("！ %s/ 里没有 index.html，跳过。" % key)
            continue
        entries = [
            '%s<li><a href="%s">%s</a></li>' % (LIST_INDENT, it["url"], it["title"])
            for it in items
        ]
        text = splice_list(idx.read_text(encoding="utf-8"), idx, entries)
        (changed if write_if_changed(idx, text, dry) else kept).append(idx)

    # 2. 外层首页：推荐 + 搜索清单
    all_items = [it for key, _ in SECTIONS for it in site[key]]
    all_items.sort(key=sort_key, reverse=True)

    entries = []
    for i, it in enumerate(all_items[:TOP_N]):
        new = '<span class="tag-new">new</span>' if i == 0 else ""
        entries.append('%s<li><a href="%s">%s%s</a></li>' % (LIST_INDENT, it["url"], it["title"], new))

    text = root_index.read_text(encoding="utf-8")
    text = splice_list(text, root_index, entries)

    payload = json.dumps(
        [{"t": it["title"], "u": it["url"], "s": it["section_cn"]} for it in all_items],
        ensure_ascii=False, separators=(",", ":"),
    ).replace("</", "<\\/")
    text = splice_search(text, root_index, payload)
    (changed if write_if_changed(root_index, text, dry) else kept).append(root_index)

    # 3. 摘要
    say("文章：" + "  ".join("%s %d 篇" % (cn, len(site[k])) for k, cn in SECTIONS)
        + "  共 %d 篇" % total)
    say("首页：推荐 %d 篇（最新一篇带 new）；搜索清单 %d 条"
        % (min(TOP_N, len(all_items)), len(all_items)))
    for p in changed:
        say("  %s %s" % ("(dry-run) 会更新" if dry else "已更新", p.relative_to(ROOT).as_posix()))
    for p in kept:
        say("  未变化   %s" % p.relative_to(ROOT).as_posix())

    # 4. 体检
    if not quiet:
        pages = [root_index, ROOT / "work.html"]
        pages += [p for k, _ in SECTIONS for p in (ROOT / k).glob("*.html")]
        broken = check_links(pages)
        if broken:
            say("")
            say("链接体检：%d 处指向不存在的文件（只报不改）" % len(broken))
            for page, target in broken:
                say("  %s  ->  %s" % (page.relative_to(ROOT).as_posix(), target))
        else:
            say("")
            say("链接体检：干净，没发现死链。")

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
    except SystemExit as e:
        show_error("出错了", str(e))
    except Exception:
        import traceback
        show_error("脚本出错了", traceback.format_exc())
