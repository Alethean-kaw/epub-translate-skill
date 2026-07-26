# EPUB Translate Skill

EPUB Translate Skill 是一个面向 EPUB 图书翻译项目的可复用流程包。它用于将源 EPUB 按阅读顺序提取为 Markdown 分章，维护译名表和校对报告，执行“两遍翻译”流程，并辅助生成电脑端与手机优化版 EPUB。

## 功能

- 按 `content.opf` 的 spine 顺序提取 EPUB 内容。
- 生成稳定排序的分章文件，例如 `00_...md`、`01_...md`。
- 为每本书维护独立的 glossary / `译名表.md` 与 proofreading report / `校对报告.md`。
- 固化两遍流程：第一遍完成全书译稿，第二遍逐段对照原文校订。
- 将手机端短段优化限制在构建稿中，不污染正式分章译文。
- 提供清洁合并、手机短段拆分和 EPUB 结构校验脚本。

## 文件结构

```text
epub-translate-skill/
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── LICENSE
├── agents/
│   └── openai.yaml
├── references/
│   └── workflow.md
└── scripts/
    └── epub_project_tools.py
```

## 使用示例

将此文件夹复制或安装到兼容的智能体或工作流环境中，然后在图书项目中使用该 EPUB 翻译流程。

辅助脚本示例：

```powershell
python .\scripts\epub_project_tools.py merge --input "<translation-folder>" --output "_epub_build\clean.md"
python .\scripts\epub_project_tools.py mobile --input "_epub_build\clean.md" --output "_epub_build\mobile.md"
python .\scripts\epub_project_tools.py qc --epub "<translated-book>.epub" --json "_epub_build\qc.json"
```

生成 EPUB 仍需要安装 Pandoc。如果 `pandoc` 不在 PATH 中，请在你的机器上使用自己的本地可执行文件路径：

```text
<pandoc-path>
```

## 版权提醒

此仓库应只包含流程包、参考说明和辅助脚本。除非你拥有发布权或已获得授权，不要提交受版权保护的源 EPUB、提取章节、生成译文、封面或图书图片。

本仓库的许可证只覆盖这个流程包本身，不授予任何第三方图书或译文内容的权利。

## 许可证

MIT License。见 `LICENSE`。
