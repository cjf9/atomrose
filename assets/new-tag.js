/* new 标签：在浏览器里现算，所以永远不会过期。
 *
 * 四个 index 页（首页 / 随笔 / 自选集 / 工作）都靠这个文件，
 * 底部加 <script src="/assets/new-tag.js"></script> 就好，页面里不用写任何标签。
 *
 * 【两个硬约定，改任一个都要同步改别处】
 *   1. 列表容器必须有 class="posts" —— 本文件靠它找列表。
 *      work 页的卡片是 class="posts cards"，一样能被选中。
 *   2. 文章文件名 = 发表时间的十六进制，解析逻辑在 tools/sitecore.py 的 parse_stem()。
 *      例：2f2c81d9c7.html 解出来是 2026-10-17 03:11。
 *
 * 拿发表日期跟"此刻"比，WINDOW_DAYS 天内的全部挂上 new。
 * 想改时间窗，只改下面这个数字。
 * 浏览器禁了 JS：页面照常，只是没有 new 标签 —— 不会误标。
 */

(function () {
  'use strict';

  var WINDOW_DAYS = 7;
  var LIMIT = WINDOW_DAYS * 24 * 60 * 60 * 1000;

  /* 链接里的文件名主干：10 位十六进制，老文件可能带 -2 这种序号后缀 */
  var STEM = /\/([0-9a-fA-F]{10}(?:-\d+)?)\.html(?:[?#]|$)/;

  function publishedAt(href) {
    var m = STEM.exec(href || '');
    if (!m) return null;

    /* 取第一段，把十六进制还原成 202610170311 这样的 12 位十进制 */
    var dec = String(parseInt(m[1].split('-')[0], 16));
    if (dec.length !== 12) return null;

    var t = new Date(
      +dec.slice(0, 4),
      +dec.slice(4, 6) - 1,
      +dec.slice(6, 8),
      +dec.slice(8, 10),
      +dec.slice(10, 12)
    ).getTime();

    return isNaN(t) ? null : t;
  }

  function mark(link) {
    var t = publishedAt(link.getAttribute('href'));
    if (t === null) return;
    if (Date.now() - t >= LIMIT) return;
    if (link.querySelector('.tag-new')) return;

    var tag = document.createElement('span');
    tag.className = 'tag-new';
    tag.textContent = 'new';
    link.appendChild(tag);
  }

  var links = document.querySelectorAll('.posts li a[href]');
  Array.prototype.forEach.call(links, mark);
})();
