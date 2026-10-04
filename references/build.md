# 构建标准版与手机版

## 依赖与工作目录

Python 3.9+ 用于内置脚本；Pandoc 用于实际 EPUB 生成，不随技能安装。先执行 `python --version`、`pandoc --version`，确认可执行文件与参数；不自动安装软件。必要时使用用户已有的 Pandoc 绝对路径。旧 Pandoc 不支持 `--split-level` 时查阅该版本帮助；下列命令不依赖这个可选参数。

以下 PowerShell 示例在**书籍项目根目录**执行，假定项目内已安装技能；若全局安装，改用注释中的 `$tool`。macOS/Linux shell 用相同 Python/Pandoc 参数并调整变量语法即可。每一步检查退出码，失败后先处理问题，不连跑到“成功交付”。

```powershell
$tool = Join-Path (Get-Location) '.agents/skills/epub-translate-skill/scripts/epub_project_tools.py'
# 全局安装时：$tool = Join-Path $HOME '.agents/skills/epub-translate-skill/scripts/epub_project_tools.py'
python $tool inspect --epub 'source/book.epub' --json '_epub_build/source-inspect.json'
python $tool merge --input 'translation' --output '_epub_build/clean.md'
python $tool mobile --input '_epub_build/clean.md' --output '_epub_build/mobile.md'
```

`merge` 只读目录顶层的数字编号 Markdown，按整数排序，不会从子目录捡入草稿；辅助文档用非编号文件名。重复编号、缺号或空章会失败。`--skip-first` 与 `--allow-gaps` 仅用于核对后明确排除的情况，记录原因，不当作修错快捷方式。只去除开头追溯块，不删除真实正文的 `---`。

## 资源和链接必须先修复

合并器不会重写图片路径、跨章链接或脚注 ID。构建前在 `_epub_build` 中复制/映射资源：

- 图片等引用统一为 `assets/...`，复制到 `_epub_build/assets/`；同名资源避免冲突。
- 源文件型章节链接改为唯一显式锚点，例如 `[第二章](#ch-002)`，标题设置 `{#ch-002}`。
- 全书脚注标签、HTML ID 唯一，并维护往返链接；检查译名更改是否影响自动锚点。
- CSS 中字体、背景图片及 SVG 依赖要单独检查；脚本不会完整遍历 CSS 或 `srcset`。

手机拆段完成不表示所有段落均小于阈值。脚本保护代码、数学块、缩进、列表、表格、链接和其他带标记块；原始 HTML 后续区域会被保守保留。无法安全拆分的普通段落列入 `unresolved_blocks` 并返回 1；保护块需人工查看。只在手机构建稿调整，不能回写正式译稿。

## 元数据与样式

创建 `_epub_build/metadata.yaml`（示例值应替换）：

```yaml
title: '译本书名'
author:
  - '原作者'
lang: zh-CN
rights: '按原作及译本实际授权填写'
```

Pandoc 的 `author` 生成作者元数据；不要用未核实的字段替代。译者、出版信息和封面按 Pandoc 当前文档设置。保留原书身份信息，但不要把原版 ISBN 错当新译本 ISBN，也不虚构出版机构。封面路径必须实际存在。

分别创建 `_epub_build/desktop.css` 和 `mobile.css`。可从简洁相对单位开始，例如：

```css
body { line-height: 1.6; }
img, svg { max-width: 100%; height: auto; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }
table { max-width: 100%; }
```

针对目标语言与阅读器调节段距、首行缩进和标题间距；不要为手机强设绝对字号或禁止读者改字体。复杂表格、竖排与 RTL 需单独验证。

## 生成与检查

确认 metadata、CSS 与资源已经准备好，再执行：

```powershell
New-Item -ItemType Directory -Force 'dist' | Out-Null
pandoc '_epub_build/clean.md' --from=markdown --to=epub3 --standalone --toc --metadata-file='_epub_build/metadata.yaml' --resource-path='_epub_build' --css='_epub_build/desktop.css' --output='dist/translated.epub'
pandoc '_epub_build/mobile.md' --from=markdown --to=epub3 --standalone --toc --metadata-file='_epub_build/metadata.yaml' --resource-path='_epub_build' --css='_epub_build/mobile.css' --output='dist/translated-mobile.epub'
python $tool qc --epub 'dist/translated.epub' --json '_epub_build/qc-desktop.json'
python $tool qc --epub 'dist/translated-mobile.epub' --json '_epub_build/qc-mobile.json'
python $tool compare --left 'dist/translated.epub' --right 'dist/translated-mobile.epub' --json '_epub_build/compare.json'
```

Pandoc 会覆盖同名输出，因此首次构建使用新路径；重建前确认文件属于本项目的可重建成品。脚本输出则默认拒绝覆盖，明确重建时附加 `--force`。可以用当前 Pandoc 的 `--split-level=1` 或 `2` 控制内部 XHTML 拆分，但该参数不控制手机正文段长。

若 compare 不一致，按 spine 定位缺失/新增文本，包括标题页、注释与图注；修正后重建两版，不能仅关闭检查。比较通过后继续 [验收](validation.md)。

参考：[Pandoc EPUB 教程](https://pandoc.org/epub.html)、[Pandoc 参数与元数据](https://pandoc.org/MANUAL.html)。
