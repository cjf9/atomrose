#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_home_index.py —— 只刷首页 index.html。

由 update_all_index.pyw 调用，你也可以单独在命令行跑：
    python update_home_index.py

它干两件事，数据来源都是"所有栏目里除了 index.html 之外的全部文章"：

  1. 按发表时间倒序取最新 10 篇，填进首页的列表标记圈
  2. 把全部文章的标题+链接+栏目，内嵌进首页的搜索清单（给搜索框用）

注意：它扫的是三个栏目目录（essays/ collection/ work/），
不是去读那三个 index.html —— 所以四个脚本的先后顺序无所谓。
"""

import json
import sys

import sitecore as sc

TOP_N = 10                 # 首页放几篇（不够就有多少放多少）


def render(items):
    """首页的列表长什么样 —— 标题列表。"""
    return sc.plain_entries(items[:TOP_N])


def search_payload(items):
    return json.dumps(
        [{"t": it["title"], "u": it["url"], "s": it["section_cn"]} for it in items],
        ensure_ascii=False, separators=(",", ":"),
    ).replace("</", "<\\/")


def run(dry=False):
    idx = sc.SITE_ROOT / "index.html"
    if not idx.is_file():
        return ["！ 找不到首页 %s" % sc.rel(idx)]

    site = sc.collect()                    # 三个栏目全扫
    items = [it for key, _ in sc.SECTIONS for it in site[key]]
    items.sort(key=sc.sort_key, reverse=True)

    text = idx.read_text(encoding="utf-8")
    text = sc.splice_list(text, idx, render(items))
    text = sc.splice_search(text, idx, search_payload(items))
    changed = sc.write_if_changed(idx, text, dry)

    lines = ["首页：推荐 %d 篇，搜索清单 %d 条"
             % (min(TOP_N, len(items)), len(items))]
    lines.append("  %s %s" % ("(dry-run) 会更新" if dry else "已更新",
                              sc.rel(idx)) if changed else "  未变化   %s" % sc.rel(idx))
    return lines


if __name__ == "__main__":
    print("\n".join(run(dry="--dry-run" in sys.argv)))
