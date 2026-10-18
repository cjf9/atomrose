#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_essay_index.py —— 只刷随笔栏目的 essays/index.html。

由 update_all_index.pyw 调用，你也可以单独在命令行跑：
    python update_essay_index.py

它只管"随笔这一栏的列表长什么样"。排序、时间解析、标记圈、写盘
全在 sitecore.py 里，别在这儿重复实现。
"""

import sys

import sitecore as sc

SECTION = "essays"
NAME = "随笔"


def render(items):
    """随笔的列表长什么样 —— 标题列表。想改成别的样式就改这里。"""
    return sc.plain_entries(items)


def run(dry=False):
    idx = sc.SITE_ROOT / SECTION / "index.html"
    if not idx.is_file():
        return ["！ %s/ 里没有 index.html，跳过。" % SECTION]

    items = sc.section_items(SECTION)
    text = sc.splice_list(idx.read_text(encoding="utf-8"), idx, render(items))
    changed = sc.write_if_changed(idx, text, dry)

    lines = ["%s：%d 篇" % (NAME, len(items))]
    lines.append("  %s %s" % ("(dry-run) 会更新" if dry else "已更新",
                              sc.rel(idx)) if changed else "  未变化   %s" % sc.rel(idx))
    return lines


if __name__ == "__main__":
    print("\n".join(run(dry="--dry-run" in sys.argv)))
