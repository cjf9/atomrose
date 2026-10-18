# Atomrose（QY博客）

个人博客 / 电子简历。纯静态，托管在 GitHub Pages，域名 `atomrose.com`。

**仓库根目录就是网站根目录** —— 根下的 `index.html` 会被 GitHub Pages 直接发布。

## 目录结构

```
index.html          首页：简介 + 搜索框 + 最新文章列表（列表区由脚本生成）
work/               工作：卡片式索引 + 每篇文章
essays/             随笔：标题列表 + 每篇文章
collection/         自选集：标题列表 + 每篇文章
assets/             样式、脚本，以及每篇文章的资源目录
  style.css         全站样式（卡片、列表、深色模式、图片与正文版式都在这里）
  search.js         首页搜索框
  new-tag.js        new 标签，浏览器里现算
  img-view.js       点文章里的图片看原图（仅文章页引入）
  <文章文件名>/      该文章的配图，例如 assets/2f2c730f86/cover.png
tools/              所有脚本，不是网页
  sitecore.py                    公共底座：扫目录、解析时间、排序、标记圈、写盘、链接体检
  update_essay_index.py          随笔列表
  update_collection_index.py     自选集列表
  update_work_index.py           工作卡片
  update_home_index.py           首页列表 + 搜索清单
  update_all_index.pyw           ★ 总入口，平时只用这个
  build_and_update.pyw           编辑器 + 生成 html（不产生 .md 文件）
  delete_and_update.pyw          删文章（连资源目录），删完自动刷索引
  drafts/_images/                编辑器插图时放原图的地方（.gitignore 忽略）
CNAME  .nojekyll
```

## 三个入口

| 要做什么 | 跑哪个 |
|---|---|
| 加了/删了/搬了文章，或改了标题 | `tools/update_all_index.pyw`（双击） |
| 写文章 / 生成网页 | `tools/build_and_update.pyw`（双击 = 编辑器：写正文、打标题、居中、插图、点「生成」落盘并自动刷索引） |
| 删文章 | `tools/delete_and_update.pyw`（双击，删完自动刷索引） |

四个 `update_*_index.py` 是子脚本，由 `update_all_index.pyw` 依次调用。**它们不双击、不弹框、没有 `.pyw` 后缀**，这是故意的。生成/删除时也会按 随笔 → 自选集 → 工作 → 首页 的顺序直接调它们的 `run()`。

## 硬约定（动它们之前先读）

1. **标记圈**：四个 index 页里 `<!-- atomrose:list:start -->` 和 `<!-- atomrose:list:end -->` 之间由脚本整段重写，**圈内手改会被覆盖**。圈外随便改。
2. **class 契约**——改名必须同时改三处（生成方 Python、`assets/style.css`、`assets/new-tag.js`）：
   - `posts`：列表容器，`new-tag.js` 靠它找列表
   - `cards`：卡片布局开关（work 页）
   - `card` / `card-title` / `card-desc`：卡片结构
   - `tag-new`：由 `new-tag.js` 动态插入，**Python 里不要生成它**
   改名不会报错，只会静默失效。
3. **文件名 = 发表时间的十六进制**（10 位，精确到分钟；老文件可能带 `-2` 这类后缀）。排序、new 标签、资源目录名全依赖它。改命名规则要同步三处：`tools/sitecore.py` 的 `parse_stem()`、`tools/build_and_update.pyw`、`assets/new-tag.js`。
4. **链接一律用从根算的绝对路径**（`/assets/...`、`/essays/...`）。因为文章可能在栏目间挪动，相对路径一挪就断。代价：本地不能双击 html 预览，必须起 http 服务——用户自己开着 `127.0.0.1:8080`。
5. **每篇文章的资源放在 `assets/<文章文件名>/`**。删文章时连目录一起删，`delete_and_update.pyw` 已处理。
6. **work 卡片的内容全自动**：标题取 `<title>`，封面取正文第一张 `<img>`，摘要取 `<meta name="description">`（没有才退回正文第一段）。所以"改某张卡片"= 改那篇文章的配图和描述，不要改脚本。
7. **图片最多占版心 70%**（`article img { max-width: 70% }`），高度自动、居中；原图比 70% 还小就按原尺寸显示，**不放大**；窄于 640px 的屏幕放宽到 100%。点图看原图靠 `assets/img-view.js`，文章页底部必须引入它（模板已带；手写的文章页要手动加）。不要在 md 或 HTML 里写死宽度。
8. **正文版式由 `<body>` 上的 class 决定**：
   - `prose`（随笔、自选集）：仿宋、两端对齐、段首缩进两字、标题居中
   - `doc`（工作）：无衬线，原样
   - `lined`（编辑器生成的页面都带）：段落和标题的外边距清零，**块间距完全由空行决定**
   映射表在 `tools/build_and_update.pyw` 的 `SECTIONS`。class 是生成时写死的，改 `SECTIONS` 不会影响已有文章。
9. **编辑器是行模型**：内存里是「每行文字 + 属性表（级别/居中/缩进）」，界面上不出现 markdown 标记；空行会变成 `<div class="gap">`，一行一个 `<p>`。生成时直接把模型转 HTML，**不落 .md**。
10. **写盘要幂等**：index 相关脚本走 `sitecore.write_if_changed()`，内容没变就不写文件。
11. **样式表链接带 `?v=N`**（当前值见任意 html 的 head）。浏览器按完整 URL 缓存 CSS，**改完 CSS 后页面没变化就把 N 加一**（所有 HTML + `build_and_update.pyw` 模板）。

## 不要做

- **不要改三个栏目目录名**（`essays` / `collection` / `work`）。目录名就是网址，改了所有文章链接全断。
- 不要在 `tools/` 之外新增脚本。
- 不要给四个 `update_*_index.py` 加弹框或改成 `.pyw`。
- 不要引入第三方依赖（脚本只用标准库；`assets/` 里的 JS 是原生 JS，没有构建步骤）。
- 不要把 `tools/drafts/` 提交进仓库（插图原图在那里）。

## 现状

- 已有真实内容在写，但仍有占位文章（`work/` 里的"示例项目""第二个项目"）。
- 页脚只写 `© QY`，邮箱只在首页简介里出现（atomrose@163.com）。
- 目录页顶部原来那句"这里放栏目说明（占位）"已删，改用 `.lede-gap` 占位留白。
- OG 标签（分享预览）讨论过，**决定暂不做**。
- GitHub Pages / 自定义域名 DNS 尚未配置；仓库只有一个初始提交，之后的重构还未提交。
- `AGENTS.md` 本身也会被发布到站点上（可公开访问），不要往里写敏感信息。

## 验证方式

没有测试框架，靠实跑：

```
python tools/update_all_index.pyw --no-gui     # 连跑两次，第二次应全部「未变化」
python -m py_compile tools/sitecore.py tools/build_and_update.pyw tools/delete_and_update.pyw
node --check assets/new-tag.js
```

链接体检每次跑总脚本都会自动做，报告"干净，没发现死链"才算好。

## 协作约定

- 先说明方案再动手，改动范围严格按用户说的来，不要顺手"优化"。
- 发现别的问题，列出来问，不要直接改。
