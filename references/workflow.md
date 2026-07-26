# EPUB 双遍翻译流程参考

## 1. 项目边界

每本书都应有独立书籍目录。不要把分章、译文、构建稿或成品 EPUB 散落在工作区根目录。

标准产物：

- `<书名>-分章`：源语言 Markdown 分章，按 EPUB 阅读顺序生成。
- `<book-title>-<target-language>-translation`：正式目标语言分章译文，以及 glossary / proofreading report。
- `_epub_build`：清洁合并稿、手机短段稿、CSS、metadata、构建脚本、QC 结果。
- `<book-title>-<target-language>-translation.epub`：电脑端或标准阅读版。
- `<book-title>-<target-language>-translation-mobile.epub`：手机阅读优化版。

## 2. 提取与分章

读取 EPUB 时把 EPUB 当作 ZIP 包处理：

1. 找到 `META-INF/container.xml` 指向的 OPF。
2. 解析 OPF manifest、spine 和 metadata。
3. 以 spine itemref 顺序作为阅读顺序。
4. 用 `toc.ncx` 或 EPUB3 nav 核对目录标题和层级。
5. 复制正文图片到 `<书名>-分章/images` 或保留相对路径可解析的位置。

分章规则：

- 使用 `00_...md`、`01_...md` 或三位序号，保证排序稳定。
- 译文文件名和标题使用目标语言；源文分章可保留原题或目标语言逻辑标题。
- 不把纯封面图、logo、表格放大辅助页、重复目录页作为正文独立章节，除非它们在读者目录中具有实际内容。
- 遇到电子书错切或重复污染，应优先以 OPF、TOC 和 XHTML 内容重新核对，并在 `校对报告.md` 记录修复。

## 3. 翻译控制文件

glossary 文件至少记录：

```markdown
# Glossary

| 原文 | 固定译法 | 说明 |
|---|---|---|
| term | 译法 | 使用条件或上下文 |
```

proofreading report 文件至少记录：

```markdown
# 校对报告

## 当前状态

- 原文分章：`00-xx`
- 译文分章：`00-xx`
- 第一遍完成：`00-xx`
- 第二遍完成：`00-xx`
- 待处理：无 / `xx-yy`

## 主要修正

- 术语统一：
- 漏译补齐：
- 误译修正：
- 图片/公式/链接：

## 最终校验

- UTF-8 与非空：
- 序号连续：
- 图片可解析：
- 内部链接可解析：
- EPUB 包结构：
- 手机段落长度：
```

## 4. 第一遍：完整直译

第一遍目标是完整，不是完美。

要求：

- 所有正式分章都有对应译文。
- 正文只放目标语言译文，不做双语对照，除非用户明确要求。
- 保留标题层级、段落顺序、强调、引用、脚注标记、公式、表格、图片位置和索引/参考文献顺序。
- 术语、专名、作品名和核心概念进入 `译名表.md`。
- 不把未完成草稿伪装成正式分章；未完成状态写入 `校对报告.md`。

## 5. 第二遍：逐段对照校订

第二遍以 `<书名>-分章` 为权威来源。

逐段检查：

- 段落是否一一对应。
- 是否漏译、增译、反义、弱化语气或改写观点。
- 术语是否遵守 glossary。
- 人名、地名、作品名、机构名、年份、数字、ISBN、页码是否准确。
- 脚注、尾注、内部链接、锚点、公式和图片是否保留。
- 中文是否自然，但不得压缩成摘要。

完成后更新 proofreading report，明确第二遍覆盖范围和仍需人工判断的点。

## 6. 清洁合并与 EPUB

合并时只读取编号译文文件，排除辅助文档。清洁阅读稿必须去掉：

- `原文标题：`
- `来源文件：`
- `来源 EPUB：`
- 工作稿分隔线
- glossary
- proofreading report

推荐 Pandoc 参数：

```powershell
& "<pandoc-path>" "_epub_build\clean.md" `
  -o "<book-title>-<target-language>-translation.epub" `
  --metadata title="<书名>" `
  --metadata creator="<作者>" `
  --metadata lang="<target-language-code>" `
  --css "_epub_build\desktop.css" `
  --split-level=1
```

手机优化版：

- 基于独立 `mobile.md` 构建。
- `--split-level=2`。
- CSS 使用首行缩进、低段距、约 `1.5` 至 `1.6` 行高、克制标题间距。
- 只拆普通正文长段，不拆标题、图片、表格、公式、目录、索引、书目、地址、代码、Markdown 标记内部。

## 7. EPUB 验收

必须检查：

- ZIP 第一项是 `mimetype`，且未压缩。
- `META-INF/container.xml` 存在。
- OPF 存在，metadata 包含书名、作者、语言。
- nav 或 toc 存在。
- XHTML 均可用 XML 解析。
- 图片引用全部可解析。
- 内部链接和锚点全部可解析；封面作为 metadata 时不要错误要求 `00` 正文锚点。
- 正文不含工作稿说明。
- 桌面版与手机版正文去空白后等价。
- 手机版普通正文超过 300 个目标语言字符的段落为 0，特殊长书目/索引/公式另行说明。

## 8. 常见修复

- Pandoc 成功但 XHTML 无法解析：检查斜体、下标、HTML 标签是否交叉嵌套。
- 手机阅读段落过长：只重建 mobile 构建稿，不改正式译文。
- 图片断链：把译文中的图片路径改成相对译文目录可解析的路径，或在构建时复制资源并重写引用。
- 目录链接断裂：把 Markdown 文件名链接映射到 Pandoc 生成的章节锚点，封面链接要单独处理。
- 翻译工具不可用：停止承诺自动完成，记录环境限制，改为多轮人工/半自动推进。
