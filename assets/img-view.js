/* 点文章里的图片，看原图。
 *
 * 配合 assets/style.css 里的 article img（默认缩到 70% 宽居中）和 .img-view 遮罩。
 * 文章页底部加 <script src="/assets/img-view.js"></script> 即可，
 * 不用给 <img> 加任何东西 —— 这里自己给 article 里的图片绑点击。
 *
 * 关掉的方式：点遮罩任意处，或按 Esc。
 * 浏览器禁了 JS：图片照常显示（还是 70%），只是点不开原图 —— 不会坏。
 */

(function () {
  'use strict';

  var imgs = document.querySelectorAll('article img');
  if (!imgs.length) return;

  var box = document.createElement('div');
  box.className = 'img-view';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', '查看原图');

  var big = document.createElement('img');
  box.appendChild(big);
  document.body.appendChild(box);

  function close() {
    box.classList.remove('on');
    document.body.classList.remove('no-scroll');
    big.removeAttribute('src');
  }

  function open(src, alt) {
    big.src = src;
    big.alt = alt || '';
    box.classList.add('on');
    document.body.classList.add('no-scroll');
  }

  Array.prototype.forEach.call(imgs, function (img) {
    img.classList.add('zoomable');
    img.addEventListener('click', function () {
      open(img.getAttribute('src'), img.getAttribute('alt'));
    });
  });

  box.addEventListener('click', close);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });
})();
