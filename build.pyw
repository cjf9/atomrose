#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.pyw —— 把 markdown 变成站内的一个 html 页面。

【功能】
读 markdown_source/ 里的 .md（可以带本地图片），在站点根目录生成一个
以时间命名的 html。之后由你手动归类到 work/ essays/ fiction/ 里去。

双击运行即可。下面是可选的命令行参数：

    python build.pyw                         处理（有多个 md 时弹框让你选）
    python build.pyw markdown_source/a.md    只处理这一个
    python build.pyw a.md --title "标题"      指定标题
    python build.pyw --dry-run               只说要生成什么，不写盘
    python build.pyw --no-gui                不弹框，只往控制台打
    python build.pyw --help                  看这份说明

【生成规则】
文件名 = 生成时间（精确到分钟）转十六进制、去掉 0x、补零到 10 位。
同一分钟内再生成，自动加 -2 / -3 后缀。
md 里引用的本地图片会被复制到 assets/<文章文件名>/，引用路径自动改写成
/assets/<文章文件名>/xxx.png。一篇文章的资源集中在自己那个目录里，
删文章时连它的资源目录一起删掉就行，不会留下孤儿文件。

段落里换行 = 硬换行（写诗直接一行一行写就行）。这是故意的，不是标准
markdown 行为；如果你更想要"换行当空格"，把下面的 <br> 换成空格即可。

只支持常用语法：标题、段落、粗体/斜体/删除线、行内代码、围栏代码块、
链接、图片、列表（含嵌套）、引用块、分隔线、表格。要更全的语法就
pip install markdown，我再接上去。

生成完记得跑一次 update.pyw。
"""

import re
import shutil
import sys
from datetime import datetime
from html import escape as _h
from html import unescape as _unh
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "markdown_source"
ASSETS_DIR = ROOT / "assets"
HEX_WIDTH = 10

SITE_NAME = "QY"
SITE_TAGLINE = ""  # 想加一句 slogan 就填这里

NAV = [
    ("/work.html", "工作", None),
    ("/essays/", "随笔", "essays"),
    ("/fiction/", "小说与诗", "fiction"),
]


# ── 输出与弹框 ──────────────────────────────────────────────────────
# 双击 .pyw 是用 pythonw 跑的，没有控制台：print 没地方去，input 会直接废。
# 所以凡是给用户看的东西都走这里的 say()，双击时最后用弹框显示一遍。

try:
    import tkinter as tk
    from tkinter import messagebox
    HAVE_TK = True
except Exception:                      # 极少数没带 tkinter 的环境
    HAVE_TK = False

HAS_CONSOLE = sys.stdout is not None    # 双击 .pyw 时是 None
NO_GUI = False                          # --no-gui 打开
OUT = []                                # 攒着，双击时一次性弹出来


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
    _dialog("showinfo", "build.pyw 用法", text)


# ── 命名 ────────────────────────────────────────────────────────────

def time_stem(taken):
    """生成时间(精确到分钟) -> 十六进制文件名主干，补零对齐，不带 0x。"""
    raw = datetime.now().strftime("%Y%m%d%H%M")
    base = format(int(raw), "x").rjust(HEX_WIDTH, "0")
    name, n = base, 2
    while name in taken or (ROOT / (name + ".html")).exists():
        name = "%s-%d" % (base, n)
        n += 1
    return name


# ── 正文里的行内语法 ────────────────────────────────────────────────

def inline(text):
    stash = []

    def keep(m):
        stash.append(m.group(1))
        return "\x00%d\x00" % (len(stash) - 1)

    text = re.sub(r"`([^`]+)`", keep, text)
    text = _h(text, quote=False)

    def img(m):
        alt, src, title = m.group(1), m.group(2), m.group(3)
        t = ' title="%s"' % _h(_unh(title)) if title else ""
        return '<img src="%s" alt="%s"%s>' % (src, _h(_unh(alt)), t)

    def link(m):
        txt, href, title = m.group(1), m.group(2), m.group(3)
        t = ' title="%s"' % _h(_unh(title)) if title else ""
        return '<a href="%s"%s>%s</a>' % (href, t, txt)

    text = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)', img, text)
    text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)', link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<![_\w])_([^_\n]+)_(?!_)", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)

    def put(m):
        return "<code>%s</code>" % _h(_unh(stash[int(m.group(1))]), quote=False)

    return re.sub(r"\x00(\d+)\x00", put, text)


# ── 正文里的块级语法 ────────────────────────────────────────────────

LIST_ITEM = re.compile(r"^([ \t]*)([-*+]|\d+[.)])\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
QUOTE = re.compile(r"^\s*>")
TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
TAGS = re.compile(r"<[^>]+>")


def render_list_items(items, pos, indent):
    ordered = items[pos][1]
    tag = "ol" if ordered else "ul"
    out = ["<%s>" % tag]
    while pos < len(items):
        ind, is_ordered, text = items[pos]
        if ind < indent:
            break
        if ind == indent and is_ordered != ordered:
            break
        if ind > indent:
            sub, pos = render_list_items(items, pos, ind)
            out.append(sub)
            continue
        out.append("<li>%s" % inline(text))
        pos += 1
        if pos < len(items) and items[pos][0] > indent:
            sub, pos = render_list_items(items, pos, items[pos][0])
            out.append(sub)
        out.append("</li>")
    out.append("</%s>" % tag)
    return "".join(out), pos


def read_list(lines, i, n):
    items = []
    while i < n:
        m = LIST_ITEM.match(lines[i])
        if not m:
            break
        indent = len(m.group(1).replace("\t", "    "))
        items.append((indent, bool(re.match(r"\d", m.group(2))), m.group(3)))
        i += 1
    if not items:
        return "", i
    html, _ = render_list_items(items, 0, items[0][0])
    return html, i


def md_to_html(md):
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out, i, n = [], 0, len(lines)

    while i < n:
        line = lines[i]

        if FENCE.match(line):
            lang = line.strip().strip("`~").strip()
            i += 1
            buf = []
            while i < n and not FENCE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = ' class="language-%s"' % _h(lang) if lang else ""
            out.append("<pre><code%s>%s</code></pre>" % (cls, _h("\n".join(buf), quote=False)))
            continue

        if not line.strip():
            i += 1
            continue

        if HR.match(line):
            out.append("<hr>")
            i += 1
            continue

        m = HEADING.match(line)
        if m:
            lv = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lv, inline(m.group(2)), lv))
            i += 1
            continue

        if QUOTE.match(line):
            buf = []
            while i < n and QUOTE.match(lines[i]):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = "".join("<p>%s</p>" % inline(x) for x in buf if x.strip())
            out.append("<blockquote>%s</blockquote>" % inner)
            continue

        if "|" in line and i + 1 < n and "-" in lines[i + 1] and TABLE_SEP.match(lines[i + 1]):
            head = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = ["<table><thead><tr>"]
            t += ["<th>%s</th>" % inline(c) for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>")
                t += ["<td>%s</td>" % inline(c) for c in r]
                t.append("</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue

        if LIST_ITEM.match(line):
            parts = []
            while i < n and LIST_ITEM.match(lines[i]):
                html, ni = read_list(lines, i, n)
                if ni == i:
                    break
                parts.append(html)
                i = ni
            out.append("".join(parts))
            continue

        buf = []
        while i < n and lines[i].strip() \
                and not HEADING.match(lines[i]) and not QUOTE.match(lines[i]) \
                and not FENCE.match(lines[i]) and not HR.match(lines[i]) \
                and not LIST_ITEM.match(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % "<br>\n".join(inline(x) for x in buf))

    return "\n".join(out) + "\n"


# ── 图片 ────────────────────────────────────────────────────────────

IMG_SRC = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')


def relocate_images(md, src_dir, stem, dry=False):
    folder = ASSETS_DIR / stem
    copied = []

    def repl(m):
        alt, src = m.group(1), m.group(2)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src) or src.startswith("//"):
            return m.group(0)
        p = (src_dir / src).resolve()
        if not p.is_file():
            say("  ! 图片找不到，引用保持原样：%s" % src)
            return m.group(0)
        target = folder / p.name
        n = 2
        while target.exists() and target.read_bytes() != p.read_bytes():
            target = folder / ("%s-%d%s" % (p.stem, n, p.suffix))
            n += 1
        if not target.exists():
            if not dry:
                folder.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
            copied.append(target.name)
            say("  · 图片 -> /assets/%s/%s" % (stem, target.name))
        return "![%s](/assets/%s/%s)" % (alt, stem, target.name)

    return IMG_SRC.sub(repl, md), copied


# ── 页面外壳 ────────────────────────────────────────────────────────

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>

<header class="site-head">
  <div class="wrap">
    <a class="brand" href="/"><span class="brand-name">QY的博客</span><small class="brand-site">AtomRose.com</small></a>
    <nav>
{nav}    </nav>
  </div>
</header>

<main class="wrap">
<article>
{body}</article>
</main>

<footer class="wrap">
  <p>© {site}</p>
</footer>

</body>
</html>
"""


def render_page(title, body):
    nav = "".join('      <a href="%s">%s</a>\n' % (u, t) for u, t, _ in NAV)
    plain = re.sub(r"\s+", " ", TAGS.sub("", body)).strip()
    if plain.startswith(title):
        plain = plain[len(title):].strip()
    return PAGE.format(title=_h(title, quote=False), desc=_h(plain[:120], quote=True),
                       site=SITE_NAME, nav=nav, body=body)


# ── markdown 文件的开头信息 ──────────────────────────────────────────

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def split_front(text):
    m = FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip("'\"")
    return meta, text[m.end():]


def pick_title(meta, body, fallback):
    if meta.get("title"):
        return meta["title"]
    m = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    if m:
        return m.group(1).strip()
    return fallback


# ── 主流程 ──────────────────────────────────────────────────────────

def build_one(path, title_override, dry, taken):
    src_dir = path.parent
    text = path.read_text(encoding="utf-8")
    meta, body_md = split_front(text)

    title = title_override or pick_title(meta, body_md, path.stem)
    stem = time_stem(taken)
    say("%s  ->  %s" % (path.name, title))

    body_md, images = relocate_images(body_md, src_dir, stem, dry=dry)
    html = render_page(title, md_to_html(body_md))

    out = ROOT / (stem + ".html")
    if dry:
        say("  (dry-run) 会写出 %s" % out.name)
    else:
        out.write_text(html, encoding="utf-8", newline="\n")
        say("  写出 %s" % out.name)
    taken.add(stem)
    return out.name


# ── 多个 md 时弹框让你挑 ────────────────────────────────────────────

def choose_files(mds):
    if not HAVE_TK or NO_GUI:
        return list(mds)
    root = tk.Tk()
    root.title("选一个 markdown 文件")
    root.geometry("640x400")
    tk.Label(root, text="markdown_source/ 里有 %d 个 .md，要处理哪个？" % len(mds),
             anchor="w").pack(fill="x", padx=14, pady=(14, 8))
    box = tk.Frame(root)
    box.pack(fill="both", expand=True, padx=14)
    sb = tk.Scrollbar(box)
    sb.pack(side="right", fill="y")
    lb = tk.Listbox(box, yscrollcommand=sb.set, selectmode="extended", activestyle="none")
    lb.pack(side="left", fill="both", expand=True)
    sb.config(command=lb.yview)
    for m in mds:
        lb.insert("end", m.name)
    lb.selection_set(0)
    chosen = {"paths": None}

    def take_selected(_=None):
        idx = lb.curselection()
        if not idx:
            return
        chosen["paths"] = [mds[i] for i in idx]
        root.destroy()

    def take_all():
        chosen["paths"] = list(mds)
        root.destroy()

    lb.bind("<Double-Button-1>", take_selected)
    bar = tk.Frame(root)
    bar.pack(fill="x", padx=14, pady=14)
    tk.Button(bar, text="处理选中的", width=14, command=take_selected).pack(side="left")
    tk.Button(bar, text="全部处理", width=12, command=take_all).pack(side="left", padx=10)
    tk.Button(bar, text="取消", width=10, command=root.destroy).pack(side="right")
    root.mainloop()
    return chosen["paths"] or []


# ── 主流程 ──────────────────────────────────────────────────────────

def main():
    global NO_GUI
    args = sys.argv[1:]

    if any(a in ("-h", "--help", "-?", "/?") for a in args):
        show_help(__doc__)
        return

    NO_GUI = "--no-gui" in args
    dry = "--dry-run" in args
    args = [a for a in args if a not in ("--dry-run", "--no-gui")]

    title_override = None
    if "--title" in args:
        k = args.index("--title")
        if k + 1 >= len(args):
            show_error("参数不对", "--title 后面要跟一个标题。")
            return
        title_override = args[k + 1]
        del args[k:k + 2]

    if args:
        targets = [Path(a) for a in args]
    else:
        if not SRC_DIR.is_dir():
            show_error(
                "找不到 markdown_source 目录",
                "没有这个目录：\n%s\n\n新建它，把 .md（有图片就一起）放进去，再运行一次。"
                % SRC_DIR)
            return
        mds = sorted(SRC_DIR.glob("*.md"))
        if not mds:
            show_error(
                "没有找到 md 文件",
                "markdown_source/ 里一个 .md 都没有。\n\n"
                "把你的 markdown 文件放进这个目录：\n%s\n\n"
                "有配图就一起放进去，然后再运行一次。" % SRC_DIR)
            return
        targets = mds if len(mds) == 1 else choose_files(mds)
        if not targets:
            say("取消了，什么都没生成。")
            return

    taken = set()
    made = []
    for t in targets:
        if not t.is_file():
            say("跳过（找不到）：%s" % t)
            continue
        try:
            made.append(build_one(t, title_override, dry, taken))
        except Exception as e:
            say("× %s 处理失败：%s" % (t.name, e))

    if not made:
        show_error("什么都没生成", "\n".join(OUT))
        return

    say("")
    if dry:
        say("(dry-run，什么都没写盘)")
    else:
        say("接下来：")
        say("  1. 把上面生成的 html 手动归类到 work/ essays/ fiction/")
        say("  2. 双击 update.pyw 刷新索引")
    finish("生成完成")


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
