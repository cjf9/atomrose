#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_work_index.py —— 只刷工作栏目的 work/index.html。

由 update_all_index.pyw 调用，你也可以单独在命令行跑：
    python update_work_index.py

跟随笔、自选集的区别只有一处：列表不是一行标题，而是卡片
（封面图 + 标题 + 一句摘要），整张卡片点进文章。

卡片里的东西全是从每篇文章自己的页面里读出来的：
  · 标题  <- 页面的 <title>
  · 封面  <- 正文里第一张 <img>（文章资源在 /assets/<文章文件名>/ 下）
  · 摘要  <- 正文第一段文字，截到 80 个字
所以想让某张卡片好看，改那篇文章的配图和开头段落就行，不用碰这个脚本。

想改卡片的 HTML 结构或样式 —— 改下面的 render()，样式在 assets/style.css。

【给以后改这个文件的人 / AI】
  · 卡片的结构在这里定，就是下面 render() 拼出来的 HTML。
  · 卡片的外观不在这里，在 assets/style.css 的 .card 那组规则。
  · 下面这些 class 名被别处依赖，改名要同时改 CSS 和 JS：
        posts        assets/new-tag.js 用它找列表
        cards        assets/style.css 用它切卡片布局
        card         卡片容器
        card-title   卡片标题
        card-desc    卡片摘要
        tag-new      new 标签（由 new-tag.js 动态插入，这里绝对不要生成它）
  · 卡片内容全部来自 sitecore，不在这里写死：
        标题 <- 页面 <title>
        封面 <- 正文第一张 <img>
        摘要 <- <meta name="description">，没有才退回正文第一段
    想让某张卡片好看，改那篇文章的配图和描述，不用动这个脚本。
  · 改完跑：tools/update_all_index.pyw
"""

import sys
from html import escape

import sitecore as sc

SECTION = "work"
NAME = "工作"
SUMMARY_CHARS = 80          # 卡片摘要最多显示多少字


def render(items):
    """工作栏目的列表长什么样 —— 卡片。想改卡片结构就改这里。"""
    if not items:
        return []

    out = []
    for it in items:
        cover = sc.page_cover(it["html"])
        desc = sc.page_summary(it["html"], it["title"], SUMMARY_CHARS)

        parts = ['%s<li class="card"><a href="%s">' % (sc.LIST_INDENT, it["url"])]
        if cover:
            parts.append('<img src="%s" alt="" loading="lazy">' % escape(cover))
        if desc:
            parts.append('<span class="card-desc">%s</span>' % escape(desc))
        parts.append('<span class="card-title">%s</span>' % escape(it["title"]))
        parts.append("</a></li>")
        out.append("".join(parts))

    return out


def run(dry=False):
    idx = sc.SITE_ROOT / SECTION / "index.html"
    if not idx.is_file():
        return ["！ %s/ 里没有 index.html，跳过。" % SECTION]

    items = sc.section_items(SECTION)
    text = sc.splice_list(idx.read_text(encoding="utf-8"), idx, render(items))
    changed = sc.write_if_changed(idx, text, dry)

    lines = ["%s：%d 张卡片" % (NAME, len(items))]
    lines.append("  %s %s" % ("(dry-run) 会更新" if dry else "已更新",
                              sc.rel(idx)) if changed else "  未变化   %s" % sc.rel(idx))
    return lines


if __name__ == "__main__":
    print("\n".join(run(dry="--dry-run" in sys.argv)))
