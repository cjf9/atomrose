/* 搜索框：数据由 update.py 内嵌在 index.html 的
   <script id="atomrose-search-index" type="application/json"> 里。
   没有数据、或浏览器禁了 JS，就不显示搜索框，页面照常可用。 */

(function () {
  'use strict';

  var dataEl = document.getElementById('atomrose-search-index');
  var box = document.querySelector('.search');
  if (!dataEl || !box) return;

  var input = box.querySelector('input');
  var list = box.querySelector('.search-results');
  if (!input || !list) return;

  var items;
  try {
    items = JSON.parse(dataEl.textContent || '[]');
  } catch (e) {
    return;
  }
  if (!Array.isArray(items) || items.length === 0) return;

  box.classList.add('on');

  var MAX_HITS = 20;
  var lower = items.map(function (it) {
    return String(it.t || '').toLowerCase();
  });

  function clear() {
    while (list.firstChild) list.removeChild(list.firstChild);
  }

  function render(query) {
    var q = query.trim().toLowerCase();
    clear();
    if (!q) return;

    var hits = 0;
    for (var i = 0; i < items.length && hits < MAX_HITS; i++) {
      if (lower[i].indexOf(q) === -1) continue;
      hits++;

      var it = items[i];
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = it.u;
      a.appendChild(document.createTextNode(it.t || it.u));
      if (it.s) {
        var sec = document.createElement('span');
        sec.className = 'sec';
        sec.textContent = it.s;
        a.appendChild(sec);
      }
      li.appendChild(a);
      list.appendChild(li);
    }

    if (hits === 0) {
      var none = document.createElement('li');
      none.className = 'none';
      none.textContent = '没有匹配的标题';
      list.appendChild(none);
    }
  }

  input.addEventListener('input', function () { render(input.value); });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      input.value = '';
      render('');
    }
  });
})();
