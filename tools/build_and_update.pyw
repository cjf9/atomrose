#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
build_and_update.pyw —— 把 markdown 变成站内的一个 html 页面。

【功能】
双击 = 一个编辑器窗口：写正文 → 选栏目 / 排版 / 时间 → 生成，直接落到栏目目录。
窗口里可以打开已有 md、插入图片（自动拷进 assets 并写好引用）、Ctrl+S 生成。

带参数运行则走命令行模式，不弹编辑器：给 md 路径 + --to / --date / --poetry 直接生成。
md 放哪都行，图片照旧自动搬进 assets/<文章文件名>/。

【四种版式】
  工作                     文档版式：系统无衬线字
  随笔 / 自选集 · 传统排版  仿宋、段首缩进两字、段间不留空（文章、小说）
  随笔 / 自选集 · 全文居中  仿宋、整篇居中、段间留白（诗歌）
样式都在 assets/style.css 的 body.prose / body.prose.poetry 下。

双击运行即可。下面是可选的命令行参数：

    python build_and_update.pyw                         处理（有多个 md 时弹框让你选）
    python build_and_update.pyw markdown_source/a.md    只处理这一个
    python build_and_update.pyw a.md --title "标题"      指定标题
    python build_and_update.pyw a.md --date 202610170335   直接指定时间，不弹框
    python build_and_update.pyw a.md --to collection    直接指定栏目，不弹框
    python build_and_update.pyw a.md --poetry           文学栏目用全文居中（诗歌）
    python build_and_update.pyw a.md --article          文学栏目用传统排版（文章）
    python build_and_update.pyw --dry-run               只说要生成什么，不写盘
    python build_and_update.pyw --no-gui                不弹框，只往控制台打
    python build_and_update.pyw --help                  看这份说明

【生成规则】
文件名 = 你输入的时间（精确到分钟）转十六进制、去掉 0x、补零到 10 位。

每次 build 都会问你一次时间，格式是**年月日时分连写 12 位**——比如
202610170335 就是 2026-10-17 03:35，不用敲 - 和 :。
默认填当前时间，直接确定就是"现在发布"；要发一篇早先写好的文章，
把它改成那篇文章的发表日期就行。
首页和栏目列表的排序就按这个时间，所以"什么时候发的"由你说了算。

同名文件已存在时会问你要不要覆盖，不会悄悄替换你已有的文章。
重建同一篇文章时填同一个时间，就是原地覆盖，不会产生多余文件。
填了一个比现在还晚的时间，会多问你一次"这是未来时间，确认吗"——
敲错年份（比如 2026 敲成 2062）当场就能发现。
md 里引用的图片会被复制到 assets/<文章文件名>/，引用路径自动改写成
/assets/<文章文件名>/xxx.png。一篇文章的资源集中在自己那个目录里，
删文章时连它的资源目录一起删掉就行，不会留下孤儿文件。

图片路径不用挑写法，下面这些都能搬：
    相对路径        img/x.png      ../img/x.png
    Windows 绝对    C:\a\b\x.png   C:/a/b/x.png
    file 地址       file:///C:/a/b/x.png
    带空格          ![x](<a b.png>)
    URL 编码        a%20b.png
    网络图片        https://example.com/x.png   会下载一份存到本地
搬不了的两种（原样保留，不报错）：data: 这种内联数据、//host/x.png 协议相对地址。

段落里换行 = 硬换行（写诗直接一行一行写就行）。这是故意的，不是标准
markdown 行为；如果你更想要"换行当空格"，把下面的 <br> 换成空格即可。

只支持常用语法：标题、段落、粗体/斜体/删除线、行内代码、围栏代码块、
链接、图片、列表（含嵌套）、引用块、分隔线、表格。要更全的语法就
pip install markdown，我再接上去。

生成完记得跑一次 update_all_index.pyw。
"""

import json
import re
import shutil
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html import escape as _h
from html import unescape as _unh
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent    # 站点根目录（tools/ 的上一层）
TOOLS_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
HEX_WIDTH = 10

SITE_NAME = "QY"
SITE_TAGLINE = ""  # 想加一句 slogan 就填这里

NAV = [
    ("/work/", "工作", None),
    ("/essays/", "随笔", "essays"),
    ("/collection/", "自选集", None),
]

# 栏目表：(目录名, 显示名, 正文风格)
#   prose = 文学版式（衬线字、两端对齐），给随笔和自选集
#   doc   = 文档版式（无衬线，就是原来的样子），给工作
# 想改哪个栏目用什么风格，只改这张表。样式本身在 assets/style.css 的 body.prose 下。
SECTIONS = [
    ("essays", "随笔", "prose"),
    ("collection", "自选集", "prose"),
    ("work", "工作", "doc"),
]


# ── 输出与弹框 ──────────────────────────────────────────────────────
# 双击 .pyw 是用 pythonw 跑的，没有控制台：print 没地方去，input 会直接废。
# 所以凡是给用户看的东西都走这里的 say()，双击时最后用弹框显示一遍。

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
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
    _dialog("showinfo", "build_and_update.pyw 用法", text)


# ── 命名 ────────────────────────────────────────────────────────────

DATE_FORMATS = (
    "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M", "%Y-%m-%d", "%Y/%m/%d",
)


def parse_date(text):
    """认几种常见写法，返回 datetime；认不出来返回 None。"""
    text = (text or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    for width, fmt in ((12, "%Y%m%d%H%M"), (8, "%Y%m%d")):
        if len(digits) == width:
            try:
                return datetime.strptime(digits, fmt)
            except ValueError:
                return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def date_stem(dt):
    """datetime -> 精确到分钟的十六进制串（补零到 10 位，不带 0x）。"""
    return format(int(dt.strftime("%Y%m%d%H%M")), "x").rjust(HEX_WIDTH, "0")


# ── 问时间 / 问覆盖 ─────────────────────────────────────────────────

def ask_when(filename, default):
    """问这次用哪个时间做文件名。返回 datetime；取消返回 None。"""
    hint = default.strftime("%Y%m%d%H%M")            # 年月日时分，连写 12 位
    pretty = default.strftime("%Y-%m-%d %H:%M")

    if HAVE_TK and not NO_GUI:
        while True:
            text = simpledialog.askstring(
                "文件名用哪个时间？",
                "%s\n\n按这个时间生成文件名，精确到分钟。\n"
                "格式：%s 就是 %s\n（年月日时分连写 12 位，不用敲 - 和 :）\n"
                "默认是现在，直接点确定就行。\n" % (filename, hint, pretty),
                initialvalue=hint,
            )
            if text is None:
                return None
            when = parse_date(text)
            if when:
                return when
            _dialog("showerror", "时间看不懂",
                    "看不懂这个时间：%s\n\n照 %s 这样写：年月日时分连写 12 位。" % (text, hint))

    while True:
        try:
            text = input("  文件名用哪个时间？[%s]：" % hint).strip()
        except EOFError:
            return None
        if not text:
            return default
        when = parse_date(text)
        if when:
            return when
        say("  看不懂，照 %s 这样写（12 位连写）。" % hint)


def confirm_overwrite(name):
    msg = "已经有一个同名文件了：\n%s\n\n要覆盖它吗？" % name
    if HAVE_TK and not NO_GUI:
        return messagebox.askyesno("要覆盖吗？", msg, default="no", icon="warning")
    try:
        return input("  %s (y/N)：" % name).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def confirm_future(when):
    msg = ("你输入的时间是 %s，比现在还晚。\n\n"
           "确认就用这个未来时间吗？\n"
           "（手滑敲错年份的话，这里选「否」回去改）"
           % when.strftime("%Y-%m-%d %H:%M"))
    if HAVE_TK and not NO_GUI:
        return messagebox.askyesno("这是未来时间", msg, default="no", icon="warning")
    try:
        return input("  未来时间，确认？(y/N)：").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def pick_out_file(md_path, date_override, section_key):
    """返回 (时间, 输出路径)；取消返回 (None, None)。

    直接落到栏目目录里（essays/ collection/ work/），不用再手动搬。
    """
    while True:
        when = date_override if date_override else ask_when(md_path.name, datetime.now())
        if when is None:
            return None, None

        # 未来时间是敲错年份最常见的样子，在这里当场拦住
        if when > datetime.now() and not confirm_future(when):
            if date_override:
                return None, None
            say("  回去改时间。")
            continue

        out = ROOT / section_key / (date_stem(when) + ".html")
        if not out.exists():
            return when, out
        if confirm_overwrite(out.name):
            return when, out
        if date_override:
            return None, None
        say("  换个时间再来。")


# ── 正文里的行内语法 ────────────────────────────────────────────────

def inline(text):
    stash = []

    def keep(m):
        stash.append(m.group(1))
        return "\x00%d\x00" % (len(stash) - 1)

    text = re.sub(r"`([^`]+)`", keep, text)
    text = _h(text, quote=False)
    # 转义会把 <路径> 变成 &lt;路径&gt;，先把图片/链接目的地里的还原回来
    text = re.sub(r"(?<=\]\()&lt;([^&]*?)&gt;(?=\))", r"<\1>", text)

    def img(m):
        alt = m.group(1)
        src = (m.group(2) or m.group(3) or "").strip()
        # 文本前面已经被 HTML 转义过，<路径> 会变成 &lt;路径&gt;
        if src.startswith("&lt;") and src.endswith("&gt;"):
            src = src[4:-4]
        title = m.group(4)
        t = ' title="%s"' % _h(_unh(title)) if title else ""
        return '<img src="%s" alt="%s"%s>' % (src, _h(_unh(alt)), t)

    def link(m):
        txt, href, title = m.group(1), m.group(2), m.group(3)
        t = ' title="%s"' % _h(_unh(title)) if title else ""
        return '<a href="%s"%s>%s</a>' % (href, t, txt)

    text = re.sub(r'!\[([^\]]*)\]\(\s*(?:<([^>]+)>|([^)\s]+))(?:\s+"([^"]*)")?\s*\)', img, text)
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


def md_to_html(md, line_mode=False):
    """line_mode=True 时每一行独立成段（编辑器用）；否则连续行用 <br> 连成一段（md 文件用）。"""
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

        if line.strip() == GAP_ON:
            out.append('<div class="gap"></div>')
            i += 1
            continue

        # ::: center … ::: 包住的块单独居中（编辑器里的「居中」按钮就是写这个）
        if line.strip().startswith("::: "):
            kind = line.strip()[4:].strip() or "center"
            i += 1
            buf = []
            while i < n and lines[i].strip() != ":::":
                buf.append(lines[i])
                i += 1
            i += 1
            inner = md_to_html("\n".join(buf)).strip()
            out.append('<div class="%s">%s</div>' % (_h(kind, quote=True), inner))
            continue

        if line_mode:
            out.append("<p>%s</p>" % inline(line.strip()))
            i += 1
            continue

        buf = []
        while i < n and lines[i].strip() \
                and not HEADING.match(lines[i]) and not QUOTE.match(lines[i]) \
                and not FENCE.match(lines[i]) and not HR.match(lines[i]) \
                and not LIST_ITEM.match(lines[i]) \
                and not lines[i].strip().startswith("::: "):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % "<br>\n".join(inline(x) for x in buf))

    return "\n".join(out) + "\n"


# ── 图片 ────────────────────────────────────────────────────────────

# 支持三种写法：
#   ![alt](path.png)          ![alt](<path with space.png>)      ![alt](path.png "标题")
IMG_SRC = re.compile(r'!\[([^\]]*)\]\(\s*(?:<([^>]+)>|([^)\s]+))(?:\s+"([^"]*)")?\s*\)')

# Windows 盘符路径（C:\... 或 C:/...）必须先认出来，否则会被 URL scheme 规则
# 误判成外链 —— "C:" 长得太像一个协议名，这是踩过的坑。
WINDOWS_ABS = re.compile(r"^[a-zA-Z]:[\\/]")
URL_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def classify(src):
    """把 md 里的图片地址分成三类，决定怎么处理。

    返回 ("local", 本地路径文本) / ("remote", 可下载的网址) / ("keep", 原样保留)
    """
    s = (src or "").strip()
    low = s.lower()

    # file:///C:/x.png 这种，剥成本地路径
    if low.startswith("file://"):
        p = urllib.parse.unquote(s[7:])
        if re.match(r"^/[a-zA-Z]:", p):
            p = p[1:]
        return "local", p

    if low.startswith("http://") or low.startswith("https://"):
        return "remote", s

    # 协议相对地址 //example.com/x.png 当外链；\\server\share 这种 UNC 当本地
    if s.startswith("//"):
        return "keep", s

    # 站内绝对路径（/assets/...）已经是最终地址，不用再找文件
    if s.startswith("/") and not WINDOWS_ABS.match(s):
        return "keep", s

    if WINDOWS_ABS.match(s):            # C:\... 或 C:/...
        return "local", s

    if URL_SCHEME.match(s):             # data: / ftp: 等，原样保留
        return "keep", s

    # 普通相对路径：可能带 %20 这种编码，解一下
    return "local", urllib.parse.unquote(s)


def fetch(url):
    """下载网络图片，返回字节。失败抛异常，调用方负责兜底。"""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (atomrose build)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def guess_ext(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def remote_name(url, data):
    """从网址里取个能用的文件名。"""
    base = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    base = re.sub(r"[^\w.\-]+", "_", base).strip("_")
    if not base:
        base = "img"
    if not Path(base).suffix:
        base += guess_ext(data)
    return base


def free_name(folder, name, data):
    """目标名被占了、而且内容不一样，就加 -2 / -3 换个名。"""
    target = folder / name
    n = 2
    while target.exists() and target.read_bytes() != data:
        target = folder / ("%s-%d%s" % (Path(name).stem, n, Path(name).suffix))
        n += 1
    return target


def relocate_images(md, src_dir, stem, dry=False):
    """把 md 引用的图片统统搬进 assets/<文章文件名>/，并把引用改写成 /assets/...

    支持：相对路径、Windows 绝对路径（反斜杠/正斜杠都行）、file:// 地址、
    URL 编码的空格、<带空格的路径>、以及 http(s) 网络图片（下载一份存本地）。

    唯一不处理的是 data: 这类没法落到文件的协议，以及协议相对地址 //host/x.png，
    这两种原样保留。
    """
    folder = ASSETS_DIR / stem
    copied = []

    def repl(m):
        alt = m.group(1)
        src = (m.group(2) or m.group(3) or "").strip()
        if not src:
            return m.group(0)

        kind, value = classify(src)

        if kind == "keep":
            return m.group(0)

        if kind == "remote":
            if dry:
                copied.append("(网络图)")
                say("  · (dry-run) 会下载 %s" % value)
                return "![%s](/assets/%s/%s)" % (alt, stem, "（dry-run）")
            try:
                data = fetch(value)
            except Exception as e:
                say("  ! 网络图片下载失败，引用原样保留：%s（%s）" % (value, e))
                return m.group(0)
            name = remote_name(value, data)
        else:
            p = (src_dir / value).resolve()
            if not p.is_file():
                say("  ! 图片找不到，引用原样保留：%s" % value)
                return m.group(0)
            try:
                data = p.read_bytes()
            except OSError as e:
                say("  ! 图片读不出来，引用原样保留：%s（%s）" % (value, e))
                return m.group(0)
            name = p.name

        target = free_name(folder, name, data)
        if not target.exists():
            if not dry:
                folder.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
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
<link rel="stylesheet" href="/assets/style.css?v=25">
  <link rel="icon" type="image/png" href="/assets/songshu.png">
</head>
<body{classattr}>

<header class="site-head">
  <div class="wrap">
    <a class="brand" href="/"><span class="brand-name">QY博客</span><small class="brand-site">AtomRose.com</small></a>
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

<script src="/assets/img-view.js"></script>
</body>
</html>
"""


def render_page(title, body, style="doc"):
    nav = "".join('      <a href="%s">%s</a>\n' % (u, t) for u, t, _ in NAV)
    plain = re.sub(r"\s+", " ", TAGS.sub("", body)).strip()
    if plain.startswith(title):
        plain = plain[len(title):].strip()
    return PAGE.format(title=_h(title, quote=False), desc=_h(plain[:120], quote=True),
                       site=SITE_NAME, nav=nav, body=body,
                       classattr=' class="%s"' % style)


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

def build_one(path, title_override, dry, date_override, section, style):
    src_dir = path.parent
    key, label, base_style = section
    text = path.read_text(encoding="utf-8")
    meta, body_md = split_front(text)

    title = title_override or pick_title(meta, body_md, path.stem)
    if style == "doc":
        kind = "文档版式（无衬线）"
    elif "poetry" in style:
        kind = "文学版式 · 全文居中"
    else:
        kind = "文学版式 · 传统排版"
    say("%s  ->  %s  （放 %s，%s）" % (path.name, title, label, kind))

    when, out = pick_out_file(path, date_override, key)
    if when is None:
        say("  取消了，这篇没生成。")
        return None
    say("  时间 %s  ->  %s" % (when.strftime("%Y-%m-%d %H:%M"),
                              out.relative_to(ROOT).as_posix()))
    stem = out.stem

    body_md, images = relocate_images(body_md, src_dir, stem, dry=dry)
    html = render_page(title, md_to_html(body_md), style)

    if dry:
        say("  (dry-run) 会写出 %s" % out.relative_to(ROOT).as_posix())
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")
        say("  写出 %s" % out.relative_to(ROOT).as_posix())
    return out.relative_to(ROOT).as_posix()


# ── 选 markdown 文件 ────────────────────────────────────────────────
# 不再固定去某个目录找：启动就弹文件对话框，md 放哪都行。
# 图片跟着 md 走 —— 谁引用的图就相对哪个 md 的目录去找。

def pick_md_file():
    """弹文件对话框选 md；取消返回 None。"""
    if HAVE_TK and not NO_GUI:
        path = filedialog.askopenfilename(
            title="选一个 markdown 文件",
            initialdir=str(Path.home() / "Desktop"),
            filetypes=[("Markdown 文件", "*.md"), ("所有文件", "*.*")],
        )
        return Path(path) if path else None

    try:
        raw = input("  markdown 文件路径：").strip().strip('"')
    except EOFError:
        return None
    return Path(raw) if raw else None


# ── 问放哪个栏目 ────────────────────────────────────────────────────

def find_section(name):
    """按目录名或中文名找栏目；找不到返回 None。"""
    name = (name or "").strip().lower()
    for sec in SECTIONS:
        if name == sec[0] or name == sec[1]:
            return sec
    return None


def choose_section():
    """弹框问这篇放哪个栏目。返回 SECTIONS 里的一项；取消返回 None。"""
    if not HAVE_TK or NO_GUI:
        return None

    root = tk.Tk()
    root.title("放到哪个栏目？")
    root.geometry("520x230")

    tk.Label(root, text="这篇生成到哪个栏目下？",
             anchor="w", font=("", 12)).pack(fill="x", padx=18, pady=(18, 2))
    tk.Label(root, text="栏目决定正文版式：随笔 / 自选集用仿宋（文学感），工作用系统无衬线（文档感）。",
             anchor="w", justify="left", wraplength=470,
             fg="#777777").pack(fill="x", padx=18, pady=(0, 14))

    picked = {"sec": None}

    def take(sec):
        picked["sec"] = sec
        root.destroy()

    bar = tk.Frame(root)
    bar.pack(fill="x", padx=18)
    for sec in SECTIONS:
        key, label, style = sec
        note = "仿宋 · 文学" if style == "prose" else "无衬线 · 文档"
        tk.Button(bar, text="%s\n%s" % (label, note), width=15, height=2,
                  command=lambda s=sec: take(s)).pack(side="left", padx=(0, 8))

    tk.Button(root, text="取消", width=10, command=root.destroy).pack(pady=(16, 0))
    root.mainloop()
    return picked["sec"]


# ── 问排版方式（只对文学栏目） ──────────────────────────────────────

def ask_poetry():
    """问这篇用哪种排版。返回 True=全文居中（诗歌）／False=传统文章／None=取消。"""
    if not HAVE_TK or NO_GUI:
        return False

    root = tk.Tk()
    root.title("排版方式")
    root.geometry("560x240")
    root.resizable(False, False)

    tk.Label(root, text="这篇怎么排？", anchor="w", font=("", 12)).pack(
        fill="x", padx=18, pady=(18, 2))
    tk.Label(root,
             text="全文居中：适合诗歌，标题和每一行都居中，段间留白。\n"
                  "传统排版：适合文章/小说，段首缩进两字，段与段之间不留空。",
             anchor="w", justify="left", wraplength=510,
             fg="#777777").pack(fill="x", padx=18, pady=(0, 14))

    picked = {"v": None}

    def take(v):
        picked["v"] = v
        root.destroy()

    bar = tk.Frame(root)
    bar.pack(fill="x", padx=18)
    tk.Button(bar, text="全文居中\n（诗歌）", width=16, height=2,
              command=lambda: take(True)).pack(side="left", padx=(0, 10))
    tk.Button(bar, text="传统排版\n（文章 / 小说）", width=18, height=2,
              command=lambda: take(False)).pack(side="left")

    tk.Button(root, text="取消", width=10, command=root.destroy).pack(pady=(16, 0))
    root.mainloop()
    return picked["v"]


# ── 编辑器（双击就是它） ────────────────────────────────────────────
#
# 编辑器不把 markdown 当模型：内存里是「逐行的属性表」——
#   lines = ["第一行", "", "第二行", ...]        正文内容（不含任何标记）
#   meta  = [{"level":0,"center":False,"indent":1}, ...]  与 lines 一一对应
# 只有 build 的那一刻才序列化成交给转换器的文本。

EDIT_W = 627
EDIT_PAD = 12
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
IMG_LINE = re.compile(r"^!\[[^\]]*\]\((?:<([^>]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\)$")
TMP_DIR = TOOLS_ROOT / "drafts" / "_images"   # 放 md 里引用的原图，持久保存


# ── 剪贴板 / 拖放 / 图片编码 ────────────────────────────────────────

def _clip_files():
    """剪贴板里的文件列表（资源管理器里复制图片后粘贴用）。"""
    if not sys.platform.startswith("win"):
        return []
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        # 64 位下句柄必须显式声明，否则会被截成 int，取不到数据
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.restype = wintypes.BOOL
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT,
                                           ctypes.c_wchar_p, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT

        if not user32.OpenClipboard(None):
            return []
        try:
            h = user32.GetClipboardData(15)          # CF_HDROP
            if not h:
                return []
            n = shell32.DragQueryFileW(h, 0xFFFFFFFF, None, 0)
            out = []
            for k in range(n):
                buf = ctypes.create_unicode_buffer(32768)
                shell32.DragQueryFileW(h, k, buf, 32768)
                out.append(buf.value)
            return out
        finally:
            user32.CloseClipboard()
    except Exception:
        return []


def _clip_dib():
    """剪贴板里的位图（截图、右键复制图片）。返回 DIB 字节。"""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalSize.argtypes = [wintypes.HANDLE]
        kernel32.GlobalSize.restype = ctypes.c_size_t
        kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]

        if not user32.OpenClipboard(None):
            return None
        try:
            h = user32.GetClipboardData(8)           # CF_DIB
            if not h:
                return None
            ptr = kernel32.GlobalLock(h)
            if not ptr:
                return None
            try:
                size = kernel32.GlobalSize(h)
                if not size:
                    return None
                return ctypes.string_at(ptr, size)
            finally:
                kernel32.GlobalUnlock(h)
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def _dib_to_rgb(data):
    """BITMAPINFOHEADER 的 DIB -> (宽, 高, RGB 字节)。只处理未压缩 24/32 位。"""
    import struct
    if not data or len(data) < 40:
        return None
    try:
        bi_size, w, h, _planes, bits, comp = struct.unpack_from("<IiiHHI", data, 0)
    except Exception:
        return None
    if w <= 0 or h == 0 or comp not in (0, 3) or bits not in (24, 32):
        return None
    topdown = h < 0
    h = abs(h)
    step = bits // 8
    stride = ((w * step + 3) // 4) * 4
    need = bi_size + stride * h
    if len(data) < need:
        return None
    rows = []
    for y in range(h):
        src = bi_size + (y if topdown else (h - 1 - y)) * stride
        row = bytearray()
        for x in range(w):
            o = src + x * step
            b, g, r = data[o], data[o + 1], data[o + 2]
            row += bytes((r, g, b))
        rows.append(bytes(row))
    return w, h, b"".join(rows)


def _png_write(path, w, h, rgb):
    import struct
    import zlib

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    stride = w * 3
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw.extend(rgb[y * stride:(y + 1) * stride])
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 6)))
        f.write(chunk(b"IEND", b""))


# ── 借 Windows 的 GDI+ 把 JPG 等格式转成 PNG（Tk 只认 PNG/GIF） ──

def _gdiplus_to_png(src):
    """用系统自带的 GDI+ 把图片转存成临时 PNG；失败返回 None。"""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes as ct

        class StartupInput(ct.Structure):
            _fields_ = [("GdiplusVersion", ct.c_uint32),
                        ("DebugEventCallback", ct.c_void_p),
                        ("SuppressBackgroundThread", ct.c_int),
                        ("SuppressExternalCodecs", ct.c_int)]

        class GUID(ct.Structure):
            _fields_ = [("Data1", ct.c_uint32), ("Data2", ct.c_uint16),
                        ("Data3", ct.c_uint16), ("Data4", ct.c_ubyte * 8)]

        clsid = GUID(0x557CF406, 0x1A04, 0x11D3,
                     (ct.c_ubyte * 8)(0x9A, 0x73, 0x00, 0x00, 0xF8, 0x1E, 0xF3, 0x2E))

        gu = ct.WinDLL("gdiplus")
        token = ct.c_void_p()
        si = StartupInput(1, None, 0, 0)
        if gu.GdiplusStartup(ct.byref(token), ct.byref(si), None) != 0:
            return None
        try:
            img = ct.c_void_p()
            if gu.GdipLoadImageFromFile(ct.c_wchar_p(str(src)),
                                        ct.byref(img)) != 0:
                return None
            try:
                TMP_DIR.mkdir(parents=True, exist_ok=True)
                out = TMP_DIR / ("preview-%s.png" % Path(src).stem)
                if gu.GdipSaveImageToFile(img, ct.c_wchar_p(str(out)),
                                          ct.byref(clsid), None) != 0:
                    return None
                return out
            finally:
                gu.GdipDisposeImage(img)
        finally:
            gu.GdiplusShutdown(token)
    except Exception:
        return None


def _save_clip_image():
    """把剪贴板位图存成临时 PNG，返回路径；没有就返回 None。"""
    rgb = _dib_to_rgb(_clip_dib())
    if not rgb:
        return None
    w, h, data = rgb
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    dest = TMP_DIR / ("clip-%s.png" % time.strftime("%Y%m%d-%H%M%S"))
    i = 2
    while dest.exists():
        dest = TMP_DIR / ("clip-%s-%d.png" % (time.strftime("%Y%m%d-%H%M%S"), i))
        i += 1
    _png_write(dest, w, h, data)
    return dest


def _enable_drop(root, on_files):
    """接受从资源管理器拖进来的文件（纯 ctypes，不引第三方库）。"""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        WM_DROPFILES, GWLP_WNDPROC = 0x0233, -4

        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        if not hwnd:
            return False
        user32.DragAcceptFiles(wintypes.HWND(hwnd), True)

        LR = ctypes.c_ssize_t
        PROC = ctypes.WINFUNCTYPE(LR, wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.CallWindowProcW.restype = LR
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND,
                                           wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT,
                                           ctypes.c_wchar_p, wintypes.UINT]

        def proc(h, msg, wp, lp):
            try:
                if msg == WM_DROPFILES:
                    n = shell32.DragQueryFileW(wintypes.HANDLE(wp), 0xFFFFFFFF, None, 0)
                    paths = []
                    for k in range(n):
                        buf = ctypes.create_unicode_buffer(32768)
                        shell32.DragQueryFileW(wintypes.HANDLE(wp), k, buf, 32768)
                        paths.append(buf.value)
                    shell32.DragFinish(wintypes.HANDLE(wp))
                    if paths:
                        root.after(0, lambda: on_files(paths))
                    return 0
            except Exception:
                pass
            return user32.CallWindowProcW(old, h, msg, wp, lp)

        new = PROC(proc)
        old = user32.SetWindowLongPtrW(wintypes.HWND(hwnd), GWLP_WNDPROC,
                                       ctypes.cast(new, ctypes.c_void_p))
        root._drop_proc = new        # 保住引用，否则回调被回收会崩
        root._drop_old = old
        return True
    except Exception:
        return False


# ── 文档模型 <-> 文本的序列化 ────────────────────────────────────────

CENTER_ON, CENTER_OFF = "::: center", ":::"
GAP_ON = "::: gap"
NOINDENT_ON, NOINDENT_OFF = "::: noindent", ":::"


def doc_serialize(lines, meta):
    """把「逐行 + 属性」变成转换器能吃的文本。只在 build/保存时调用。"""
    out = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i]
        m = meta[i]
        if not s.strip():
            out.append(GAP_ON)
            i += 1
            continue
        j = i
        while j + 1 < n and lines[j + 1].strip() and meta[j + 1] == m:
            j += 1
        body = lines[i:j + 1]
        head = body[0]
        if m["level"]:
            head = "#" * m["level"] + " " + head
        out.append(head)
        out.extend(body[1:])
        if m["center"]:
            out.insert(len(out) - len(body), CENTER_ON)
            out.append(CENTER_OFF)
        elif m["indent"] == 0:
            out.insert(len(out) - len(body), NOINDENT_ON)
            out.append(NOINDENT_OFF)
        i = j + 1
    return "\n".join(out) + "\n"


def doc_parse(md):
    """把保存下来的文本还原成「逐行 + 属性」。标记行不进正文。"""
    lines, meta = [], []
    center = noindent = False
    for raw in md.replace("\r\n", "\n").split("\n"):
        s = raw.rstrip("\n")
        t = s.strip()
        if t == CENTER_ON:
            center = True
            continue
        if t == NOINDENT_ON:
            noindent = True
            continue
        if t == GAP_ON:
            lines.append("")
            meta.append({"level": 0, "center": center, "indent": 0 if noindent else 1})
            continue
        if t == ":::":
            center = noindent = False
            continue
        level = 0
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            level, s = len(m.group(1)), m.group(2)
        lines.append(s)
        meta.append({"level": level, "center": center, "indent": 0 if noindent else 1})
    # 序列化时末尾多写了一个换行，还原时去掉对应的空行
    if md.endswith("\n") and lines and not lines[-1].strip():
        lines.pop()
        meta.pop()
    return lines, meta


def run_editor(default_section, dry):
    """一个窗口：写正文 → 选栏目/排版/时间 → 生成到对应目录。"""
    if not HAVE_TK:
        show_error("没有图形界面", "这个环境没有 tkinter，只能用命令行模式。")
        return

    root = tk.Tk()
    root.title("写文章 · QY博客")
    root.geometry("1040x800")
    root.minsize(940, 520)

    state = {"draft": None, "tmp": []}
    doc = {"lines": [""], "meta": [{"level": 0, "center": False, "indent": 1}]}

    bar = tk.Frame(root)
    bar.pack(fill="x", padx=12, pady=(10, 4))

    tk.Label(bar, text="栏目").pack(side="left")
    sec_var = tk.StringVar(value=default_section[1])
    sec_box = ttk.Combobox(bar, textvariable=sec_var, width=7, state="readonly",
                           values=[s[1] for s in SECTIONS])
    sec_box.pack(side="left", padx=(4, 14))

    tk.Label(bar, text="时间").pack(side="left")
    time_var = tk.StringVar(value=datetime.now().strftime("%Y%m%d%H%M"))
    tk.Entry(bar, textvariable=time_var, width=14).pack(side="left", padx=(4, 14))

    body = tk.Frame(root)
    body.pack(fill="both", expand=True, padx=12)

    # 滚动条必须先 pack，否则会被后面 expand 的正文挤成一条缝
    sb = tk.Scrollbar(body, width=14)
    sb.pack(side="right", fill="y", padx=(6, 0))

    holder = tk.Frame(body, width=EDIT_W + EDIT_PAD * 2 + 2, bg="#fbfaf8")
    holder.pack(side="left", expand=True, fill="y")
    holder.pack_propagate(False)

    text = tk.Text(holder, wrap="char", undo=True, font=("Microsoft YaHei", 12),
                   padx=EDIT_PAD, pady=10, spacing1=2, spacing3=10,
                   relief="flat", borderwidth=0, yscrollcommand=sb.set)
    text.pack(fill="both", expand=True)
    sb.config(command=text.yview)

    for lv in range(1, 7):
        text.tag_configure("h%d" % lv, background="#f6c9c9")
    text.tag_configure("center", justify="center")
    text.tag_configure("indent", lmargin1=32)
    text.tag_configure("imgref", elide=True)
    text.tag_configure("imgbad", background="#fff3cd")        # 图片引用那行藏起来，只显示图

    status = tk.Label(root, text="", anchor="w", fg="#777777")
    status.pack(fill="x", padx=12, pady=(6, 0))

    photos = {}
    img_frames = []

    # ── 模型同步 ──

    def read_lines():
        return text.get("1.0", "end-1c").split("\n")

    def default_meta(prev=None):
        return {"level": 0, "center": bool(prev and prev["center"]), "indent": 1}

    def resync():
        new = read_lines()
        old, old_meta = doc["lines"], doc["meta"]
        if len(new) == len(old):
            doc["lines"] = new
            return
        p = 0
        while p < min(len(old), len(new)) and old[p] == new[p]:
            p += 1
        s = 0
        while s < min(len(old), len(new)) - p and old[-1 - s] == new[-1 - s]:
            s += 1
        mid = len(new) - p - s
        prev = old_meta[p - 1] if p else None
        doc["lines"] = new
        doc["meta"] = (old_meta[:p] + [default_meta(prev) for _ in range(mid)]
                       + (old_meta[len(old_meta) - s:] if s else []))

    def img_path(line):
        m = IMG_LINE.match(line.strip())
        if not m:
            return None
        p = Path((m.group(1) or m.group(2)).strip())
        return p if p.is_file() else None

    def thumb(path):
        key = str(path)
        if key in photos:
            return photos[key]
        try:
            img = tk.PhotoImage(file=key)
        except Exception:
            png = _gdiplus_to_png(path)
            if png is None:
                return None
            try:
                img = tk.PhotoImage(file=str(png))
            except Exception:
                return None
        while img.width() > 430:
            img = img.subsample(2)
        photos[key] = img
        return img

    def paint():
        for lv in range(1, 7):
            text.tag_remove("h%d" % lv, "1.0", "end")
        text.tag_remove("center", "1.0", "end")
        text.tag_remove("indent", "1.0", "end")
        text.tag_remove("imgref", "1.0", "end")
        text.tag_remove("imgbad", "1.0", "end")
        for fr in img_frames:
            try:
                fr.destroy()
            except Exception:
                pass
        del img_frames[:]
        for i, m in enumerate(doc["meta"]):
            if i >= len(doc["lines"]):
                break
            ln = i + 1
            s = doc["lines"][i]
            if not s.strip():
                continue
            rng = ("%d.0" % ln, "%d.end" % ln)
            if IMG_LINE.match(s.strip()):
                p = img_path(s)
                im = thumb(p) if p is not None else None
                if im is not None:
                    text.tag_add("imgref", *rng)
                    fr = tk.Frame(text, width=EDIT_W, height=im.height() + 8)
                    fr.pack_propagate(False)
                    tk.Label(fr, image=im, bd=0).pack()
                    text.window_create("%d.0" % ln, window=fr)
                    img_frames.append(fr)
                else:
                    # 认得出是图片，但没法预览（JPG/WebP 或文件没了）——把路径留着并标出来
                    text.tag_add("imgbad", *rng)
                continue
            if m["level"]:
                text.tag_add("h%d" % m["level"], *rng)
            if m["center"]:
                text.tag_add("center", *rng)
            if m["indent"]:
                text.tag_add("indent", *rng)

    def selected_span():
        try:
            a = int(text.index("sel.first").split(".")[0])
            b = int(text.index("sel.last").split(".")[0])
        except tk.TclError:
            a = b = int(text.index("insert").split(".")[0])
        return min(a, b), max(a, b)

    def paragraph_span():
        a, b = selected_span()
        lines = doc["lines"]
        while a > 1 and lines[a - 2].strip():
            a -= 1
        while b < len(lines) and lines[b].strip():
            b += 1
        return a, b

    def apply_heading(level):
        resync()
        a, b = selected_span()
        for i in range(a - 1, b):
            if doc["lines"][i].strip():
                doc["meta"][i]["level"] = 0 if doc["meta"][i]["level"] == level else level
        paint()

    def toggle_center():
        resync()
        a, b = selected_span()
        rows = [i for i in range(a - 1, b) if doc["lines"][i].strip()]
        if not rows:
            return
        turn_on = not all(doc["meta"][i]["center"] for i in rows)
        for i in rows:
            doc["meta"][i]["center"] = turn_on
        paint()

    def toggle_indent():
        resync()
        a, b = selected_span()
        rows = [i for i in range(a - 1, b) if doc["lines"][i].strip()]
        if not rows:
            return
        turn_on = not all(doc["meta"][i]["indent"] for i in rows)
        for i in rows:
            doc["meta"][i]["indent"] = 1 if turn_on else 0
        paint()

    def clear_blank():
        """一键删掉所有空行（编辑器里真的删掉，build 出来也就没有空段了）"""
        resync()
        keep = [i for i, s in enumerate(doc["lines"]) if s.strip()]
        if len(keep) == len(doc["lines"]):
            return
        doc["lines"] = [doc["lines"][i] for i in keep]
        doc["meta"] = [doc["meta"][i] for i in keep]
        text.delete("1.0", "end")
        text.insert("1.0", "\n".join(doc["lines"]))
        paint()

    # ── 悬停提示 ──

    tip = {"win": None, "lbl": None}

    def hide_tip():
        if tip["win"] is not None:
            tip["win"].destroy()
            tip["win"] = None

    def on_motion(e):
        idx = text.index("@%d,%d" % (e.x, e.y))
        ln = int(idx.split(".")[0])
        lv = doc["meta"][ln - 1]["level"] if 0 < ln <= len(doc["meta"]) else 0
        if not lv:
            hide_tip()
            return
        if tip["win"] is None:
            w = tk.Toplevel(root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            lbl = tk.Label(w, text="", bg="#333333", fg="#ffffff", padx=6, pady=2,
                           font=("Microsoft YaHei", 9))
            lbl.pack()
            tip["win"], tip["lbl"] = w, lbl
        tip["lbl"].config(text="h%d" % lv)
        tip["win"].geometry("+%d+%d" % (e.x_root + 14, e.y_root + 14))

    text.bind("<Motion>", on_motion)
    text.bind("<Leave>", lambda e: hide_tip())

    # ── 插图片（临时目录，build 时复制走） ──

    def add_image(src_path):
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        src = Path(src_path)
        dest = TMP_DIR / src.name
        i = 2
        while dest.exists() and dest.read_bytes() != src.read_bytes():
            dest = TMP_DIR / ("%s-%d%s" % (src.stem, i, src.suffix))
            i += 1
        if not dest.exists():
            shutil.copy2(src, dest)
        state["tmp"].append(str(dest))
        return dest

    def insert_images(paths):
        refs = []
        for raw in paths:
            p = Path(raw)
            if p.is_file() and p.suffix.lower() in IMG_EXT:
                refs.append("![](<%s>)" % add_image(p))
        if refs:
            text.insert("insert", "\n" + "\n".join(refs) + "\n")
            resync()
            paint()

    def do_paste():
        files = [f for f in _clip_files() if Path(f).suffix.lower() in IMG_EXT]
        if files:
            insert_images(files)
            return
        png = _save_clip_image()
        if png is not None:
            insert_images([str(png)])
            return
        try:
            text.event_generate("<<Paste>>")
        except Exception:
            pass

    def do_image():
        p = filedialog.askopenfilename(
            title="选图片", initialdir=str(Path.home() / "Desktop"),
            filetypes=[("图片", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                       ("所有文件", "*.*")])
        if p:
            insert_images([p])

    # ── 生成：直接在内存里转成 HTML，不落 markdown 文件 ──

    def refresh_status():
        root.title("写文章 · QY博客")
        status.config(text=("草稿：%s" % state["draft"]) if state["draft"] else "新建文章")

    def do_build():
        resync()
        if not "".join(doc["lines"]).strip():
            messagebox.showwarning("没内容", "正文是空的。")
            return
        when = parse_date(time_var.get())
        if when is None:
            messagebox.showerror("时间不对", "照 202610170335 这样写：年月日时分连写 12 位。")
            return
        sec = find_section(sec_var.get())
        if sec is None:
            return
        key, label, base = sec
        # lined = 行模式生成的页面，间距完全由空行决定
        style = ("doc" if base == "doc" else "prose") + " lined"

        md = doc_serialize(doc["lines"], doc["meta"])
        title = pick_title({}, md, "无标题")
        stem = date_stem(when)
        out = ROOT / key / (stem + ".html")
        rel = out.relative_to(ROOT).as_posix()

        if out.exists() and not dry and not confirm_overwrite(rel):
            return

        try:
            body_md, _imgs = relocate_images(md, Path.home() / "Desktop", stem, dry=dry)
            html = render_page(title, md_to_html(body_md, line_mode=True), style)
        except Exception as e:
            messagebox.showerror("生成失败", str(e))
            return

        if dry:
            messagebox.showinfo("dry-run", "会写出 %s" % rel)
            return

        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8", newline="\n")
        except Exception as e:
            messagebox.showerror("写盘失败", str(e))
            return

        # 顺手刷新索引：随笔 → 自选集 → 工作 → 首页
        idx_log = []
        if str(TOOLS_ROOT) not in sys.path:
            sys.path.insert(0, str(TOOLS_ROOT))
        for modname in ("update_essay_index", "update_collection_index",
                        "update_work_index", "update_home_index"):
            try:
                mod = __import__(modname)
                res = mod.run()
                if isinstance(res, (list, tuple)):
                    idx_log.extend(str(x) for x in res)
            except Exception as e:
                idx_log.append("× %s 失败：%s" % (modname, e))

        # 图片已经复制进 assets/<文件名>/，草稿目录里的原图删掉
        img_dir = TOOLS_ROOT / "drafts" / "_images"
        if img_dir.is_dir():
            for ln in doc["lines"]:
                mm = IMG_LINE.match(ln.strip())
                if not mm:
                    continue
                pth = Path((mm.group(1) or mm.group(2)).strip())
                try:
                    if pth.is_file() and pth.parent.resolve() == img_dir.resolve():
                        pth.unlink()
                except Exception:
                    pass
            for junk in img_dir.glob("preview-*.png"):
                try:
                    junk.unlink()
                except Exception:
                    pass

        messagebox.showinfo("生成完成",
                            "已写出 %s\n\n%s" % (rel, "\n".join(idx_log)))

    # ── 按钮：全部排在顶部一行 ──
    tk.Label(bar, text="标题").pack(side="left")
    for lv in range(1, 7):
        tk.Button(bar, text="H%d" % lv, width=3,
                  command=lambda l=lv: apply_heading(l)).pack(side="left", padx=(2, 0))
    tk.Button(bar, text="居中", width=6,
              command=toggle_center).pack(side="left", padx=(10, 3))
    tk.Button(bar, text="缩进", width=6,
              command=toggle_indent).pack(side="left", padx=(0, 4))
    tk.Button(bar, text="清除空段", width=8,
              command=clear_blank).pack(side="left", padx=(0, 10))

    def do_open():
        drafts = TOOLS_ROOT / "drafts"
        p = filedialog.askopenfilename(
            title="打开草稿",
            initialdir=str(drafts if drafts.is_dir() else Path.home()),
            filetypes=[("草稿", "*.json"), ("Markdown", "*.md"), ("所有文件", "*.*")])
        if not p:
            return
        path = Path(p)
        try:
            if path.suffix.lower() == ".json":
                d = json.loads(path.read_text(encoding="utf-8"))
                lines, meta = d["lines"], d["meta"]
                state["draft"] = path.stem
            else:
                lines, meta = doc_parse(path.read_text(encoding="utf-8"))
                state["draft"] = None
        except Exception as e:
            messagebox.showerror("打不开", str(e))
            return
        doc["lines"], doc["meta"] = lines, meta
        text.delete("1.0", "end")
        text.insert("1.0", "\n".join(lines))
        paint()
        refresh_status()

    tk.Button(bar, text="插入图片", width=9, command=do_image).pack(side="left")
    tk.Button(bar, text="生成", width=11, command=do_build).pack(side="left", padx=(8, 0))

    # Tk 在 Windows 上默认没绑这三组，自己接上
    def do_select_all(_ev=None):
        text.tag_add("sel", "1.0", "end-1c")
        text.mark_set("insert", "1.0")
        text.see("insert")
        return "break"

    def do_undo(_ev=None):
        try:
            text.edit_undo()
        except tk.TclError:
            pass
        resync()
        paint()
        return "break"

    def do_redo(_ev=None):
        try:
            text.edit_redo()
        except tk.TclError:
            pass
        resync()
        paint()
        return "break"

    for seq in ("<Control-a>", "<Control-A>"):
        text.bind(seq, do_select_all)
    for seq in ("<Control-z>", "<Control-Z>"):
        text.bind(seq, do_undo)
    for seq in ("<Control-y>", "<Control-Y>"):
        text.bind(seq, do_redo)

    text.bind("<KeyRelease>", lambda e: (resync(), paint()))
    text.bind("<<Paste>>", lambda e: root.after(30, lambda: (resync(), paint())))
    text.bind("<Return>", lambda e: root.after(1, lambda: (resync(), paint())))
    text.bind("<BackSpace>", lambda e: root.after(1, lambda: (resync(), paint())))
    text.bind("<Delete>", lambda e: root.after(1, lambda: (resync(), paint())))

    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="粘贴（文字 / 图片）", command=do_paste)
    menu.add_command(label="插入图片…", command=do_image)
    menu.add_separator()
    menu.add_command(label="生成", command=do_build)

    def popup(e):
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()
        return "break"

    text.bind("<Button-3>", popup)

    def on_ctrl_v(_ev=None):
        files = [f for f in _clip_files() if Path(f).suffix.lower() in IMG_EXT]
        if files:
            insert_images(files)
            return "break"
        png = _save_clip_image()
        if png is not None:
            insert_images([str(png)])
            return "break"
        text.event_generate("<<Paste>>")
        return "break"

    text.bind("<Control-v>", on_ctrl_v)
    text.bind("<Control-V>", on_ctrl_v)

    _enable_drop(root, insert_images)

    paint()
    refresh_status()
    root.mainloop()


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

    date_override = None
    if "--date" in args:
        k = args.index("--date")
        if k + 1 >= len(args):
            show_error("参数不对", "--date 后面要跟一个时间，比如 2026-09-10 12:02")
            return
        date_override = parse_date(args[k + 1])
        if date_override is None:
            show_error("时间看不懂",
                       "看不懂这个时间：%s\n\n照 202610170335 这样写：年月日时分连写 12 位。"
                       % args[k + 1])
            return
        del args[k:k + 2]

    section = None
    if "--to" in args:
        k = args.index("--to")
        if k + 1 >= len(args):
            show_error("参数不对", "--to 后面要跟栏目名：essays / collection / work")
            return
        section = find_section(args[k + 1])
        if section is None:
            show_error("没有这个栏目",
                       "看不懂：%s\n\n可选：%s"
                       % (args[k + 1],
                          " / ".join("%s（%s）" % (s[0], s[1]) for s in SECTIONS)))
            return
        del args[k:k + 2]

    poetry = None
    if "--poetry" in args:
        poetry = True
        args = [a for a in args if a != "--poetry"]
    elif "--article" in args:
        poetry = False
        args = [a for a in args if a != "--article"]

    # 不带文件、也不是 --no-gui：开编辑器，一切在窗口里做完
    if not args and not NO_GUI and HAVE_TK:
        run_editor(section or SECTIONS[0], dry)
        return

    if args:
        targets = [Path(a) for a in args]
    else:
        chosen = pick_md_file()
        if chosen is None:
            say("没选文件，退出。")
            return
        targets = [chosen]

    if section is None:
        section = choose_section()
        if section is None:
            say("没选栏目，取消了。")
            return

    # 文学栏目还要问一句：全文居中（诗歌）还是传统排版（文章）
    if poetry is None:
        poetry = ask_poetry() if section[2] == "prose" else False
        if poetry is None:
            say("没选排版方式，取消了。")
            return
    if section[2] != "prose":
        poetry = False
    style = ("prose poetry" if poetry else "prose") if section[2] == "prose" else "doc"

    made = []
    for t in targets:
        if not t.is_file():
            say("跳过（找不到）：%s" % t)
            continue
        try:
            name = build_one(t, title_override, dry, date_override, section, style)
            if name:
                made.append(name)
        except Exception as e:
            say("× %s 处理失败：%s" % (t.name, e))

    if not made:
        show_error("什么都没生成", "\n".join(OUT))
        return

    say("")
    if dry:
        say("(dry-run，什么都没写盘)")
    else:
        say("接下来：双击 tools/update_all_index.pyw 刷新索引")
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
