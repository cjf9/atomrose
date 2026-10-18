#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sitecore.py —— 四个 update_* 脚本的公共底座。不是给双击用的，别删。

放这里的都是"每个栏目都要干一遍"的活：

  · 站点根目录在哪
  · 栏目表（目录名 ↔ 显示名）
  · 从文件名解出发表时间、排序
  · 扫目录里的文章，读出标题、摘要、首图
  · 改写 index.html 里的标记圈
  · 内容有变化才写盘
  · 全站链接体检

改排序规则、改标记圈格式、加栏目 —— 都只改这个文件。
各个 update_* 脚本只负责"这一栏的列表长什么样"。
"""

import re
from datetime import datetime
from html import unescape
from pathlib import Path

# tools/ 的上一层就是站点根目录
TOOLS_ROOT = Path(__file__).resolve().parent
SITE_ROOT = TOOLS_ROOT.parent
ASSETS = SITE_ROOT / "assets"

# 栏目表：目录名 -> 索引里显示的名字。加栏目就在这儿加一行，并建好目录和 index.html。
SECTIONS = [
    ("essays", "随笔"),
    ("collection", "自选集"),
    ("work", "工作"),
]

HEX_WIDTH = 10
LIST_START = "<!-- atomrose:list:start -->"
LIST_END = "<!-- atomrose:list:end -->"
SEARCH_ID = "atomrose-search-index"
LIST_INDENT = "      "


# ── 路径显示用 ──────────────────────────────────────────────────────

def rel(path):
    """站点内的相对路径，打印用。"""
    try:
        return path.relative_to(SITE_ROOT).as_posix()
    except ValueError:
        return str(path)


# ── 文件名 <-> 时间 ─────────────────────────────────────────────────

STEM = re.compile(r"^([0-9a-fA-F]+)(?:-(\d+))?$")


def parse_stem(stem):
    """时间十六进制文件名 -> (datetime, 序号)；认不出来就返回 (None, 0)。

    这个约定被两边依赖，改格式要一起改：
      · assets/new-tag.js —— 浏览器里从 href 文件名反解发表时间，用来决定 new 标签
      · tools/build_and_update.pyw   —— 生成文件名时用的是同一套编码
    """
    m = STEM.match(stem)
    if not m:
        return None, 0
    try:
        raw = str(int(m.group(1), 16)).rjust(12, "0")
        return datetime.strptime(raw, "%Y%m%d%H%M"), int(m.group(2) or 1)
    except ValueError:
        return None, 0


def sort_key(item):
    """旧的排后面，新的排前面（外面用 reverse=True）。"""
    return (item["when"] is not None, item["when"] or datetime.min,
            item["seq"], item["stem"])


# ── 从页面里读标题 / 摘要 / 首图 ────────────────────────────────────

TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TAGS = re.compile(r"<[^>]+>")
SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|blockquote|tr|section|article)>", re.I)
IMG = re.compile(r'<img[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', re.I)


def clean_text(chunk):
    chunk = SCRIPT_STYLE.sub("", chunk)
    chunk = BLOCK_END.sub("\n", chunk)
    chunk = TAGS.sub("", chunk)
    return unescape(chunk)


def article_body(html):
    """优先取 <article>，其次 <main>，再不行整页。"""
    for tag in ("article", "main"):
        m = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), html, re.I | re.S)
        if m:
            return m.group(1)
    return html


def page_title(html, fallback):
    for pattern in (TITLE, H1):
        m = pattern.search(html)
        if m:
            text = re.sub(r"\s+", " ", clean_text(m.group(1))).strip()
            if text:
                return text
    return fallback


META_DESC = re.compile(
    r'<meta[^>]*\bname\s*=\s*["\']description["\'][^>]*\bcontent\s*=\s*["\'](.*?)["\']',
    re.I | re.S)


def page_summary(html, title, limit=80):
    """摘要：优先用页面声明的 <meta name="description">，没有再退回正文第一段。

    开头那个大标题会被跳过；结果截到 limit 个字。
    """
    m = META_DESC.search(html)
    if m:
        text = re.sub(r"\s+", " ", unescape(m.group(1))).strip()
        if text:
            return text[:limit] + ("…" if len(text) > limit else "")

    for line in clean_text(article_body(html)).split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if title and (line == title or (len(line) >= 6 and (line in title or title in line))):
            continue
        return line[:limit] + ("…" if len(line) > limit else "")
    return ""


def page_cover(html):
    """正文里第一张图的地址；没有就返回空字符串。"""
    m = IMG.search(article_body(html)) or IMG.search(html)
    return m.group(1) if m else ""


# ── 收集文章 ────────────────────────────────────────────────────────

def collect(keys=None):
    """返回 {栏目目录名: [文章信息, ...]}，每个列表已按时间倒序排好。"""
    out = {}
    for key, cn in SECTIONS:
        if keys is not None and key not in keys:
            continue
        d = SITE_ROOT / key
        items = []
        if d.is_dir():
            for p in sorted(d.glob("*.html")):
                if p.name == "index.html" or p.name.startswith("."):
                    continue
                try:
                    html = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    html = ""
                when, seq = parse_stem(p.stem)
                items.append({
                    "section": key,
                    "section_cn": cn,
                    "file": p,
                    "stem": p.stem,
                    "title": page_title(html, p.stem),
                    "html": html,
                    "url": "/%s/%s" % (key, p.name),
                    "when": when,
                    "seq": seq,
                })
        items.sort(key=sort_key, reverse=True)
        out[key] = items
    return out


def section_items(key):
    return collect([key])[key]


# ── 通用列表渲染（标题列表） ────────────────────────────────────────

def plain_entries(items):
    """标题列表：左边标题，右边日期（从文件名里的时间解析，精确到日）。"""
    out = []
    for it in items:
        when = it.get("when")
        date = when.strftime("%Y-%m-%d") if when else ""
        span = ('<span class="item-date">%s</span>' % date) if date else ""
        out.append('%s<li><a href="%s">%s%s</a></li>'
                   % (LIST_INDENT, it["url"], it["title"], span))
    return out


# ── 改写标记圈 ──────────────────────────────────────────────────────

def splice_list(text, path, entries):
    i, j = text.find(LIST_START), text.find(LIST_END)
    if i == -1 or j == -1 or j < i:
        raise ValueError(
            "%s 里找不到标记圈，没动它。需要这两行（顺序别反）：\n  %s\n  %s"
            % (rel(path), LIST_START, LIST_END))
    nl = text.rfind("\n", 0, i)
    indent = text[nl + 1:i] if nl != -1 else ""
    if indent.strip():              # 起始标记不在行首，就按标准缩进处理
        indent = LIST_INDENT
    body = "\n".join(entries)
    block = LIST_START + (("\n" + body) if body else "") + "\n" + indent + LIST_END
    return text[:i] + block + text[j + len(LIST_END):]


_SCRIPT_RE = None


def splice_search(text, path, payload):
    global _SCRIPT_RE
    if _SCRIPT_RE is None:
        _SCRIPT_RE = re.compile(
            r'(<script[^>]*\bid\s*=\s*["\']%s["\'][^>]*>)(.*?)(</script>)'
            % re.escape(SEARCH_ID), re.I | re.S)
    m = _SCRIPT_RE.search(text)
    if not m:
        raise ValueError("%s 里找不到 <script id=\"%s\">，搜索清单没写进去。"
                         % (rel(path), SEARCH_ID))
    return text[: m.end(1)] + "\n" + payload + "\n" + text[m.end(2):]


def write_if_changed(path, text, dry=False):
    """内容没变就不写。返回 True 表示"确实需要改"。"""
    old = path.read_text(encoding="utf-8") if path.is_file() else None
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
        return SITE_ROOT / "index.html"
    p = SITE_ROOT / t.lstrip("/")
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
