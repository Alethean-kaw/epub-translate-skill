# EPUB 双遍翻译技能

[English](README.md)

用于 EPUB 书籍翻译的代理技能：按阅读顺序整理原文，维护译名表与可恢复的章节状态，先完成完整译稿，再逐段对照原文校订，最后构建标准版和手机优化版 EPUB。

提取转换、翻译和校对由代理结合可用工具完成。内置 Python 脚本提供离线检查、合并、手机排版准备和部分质量检查，**不是一键全自动翻译器**。

## 一条命令安装

需要 Node.js 和 npm（包含 `npx`）。安装命令已用 Skills CLI 1.7.0 验证，该版本要求 Node.js 22.20.0 或更新版本。直接在终端运行，无需下载 ZIP 再解压。

**安装到当前项目**：在项目根目录执行。

```sh
npx --yes skills@latest add Alethean-kaw/epub-translate-skill --skill epub-translate-skill --agent universal --yes
```

安装位置：当前项目的 `.agents/skills/epub-translate-skill/`。

**安装到全局**：在任意目录执行。

```sh
npx --yes skills@latest add Alethean-kaw/epub-translate-skill --skill epub-translate-skill --agent universal --global --yes
```

安装位置：`~/.agents/skills/epub-translate-skill/`。Windows 的 `~` 指用户主目录。`--agent universal` 使用共享技能目录；其他读取路径的代理需按其规则配置。安装后未被发现时，重新启动或刷新代理会话。

**更新**：重新运行对应范围的安装命令。若修改过本地技能文件，先保存改动，重装可能覆盖。需要固定安装器版本时，将 `skills@latest` 换成 `skills@1.7.0`。其他选项见 [Skills CLI 官方说明](https://github.com/vercel-labs/skills)。

## 使用方式

可直接向代理说：

> 使用 $epub-translate-skill 把这本 EPUB 翻译成简体中文。先检查并续接已有章节，维护译名表，完成第一遍翻译和第二遍逐段对校，再生成标准版与手机优化版。明确记录未校对范围和未运行的检查。

技能入口为 [SKILL.md](SKILL.md)，详细参考按任务分开：

| 任务 | 文档 |
|---|---|
| 从新书到交付 | [完整流程](references/workflow.md) |
| 阅读顺序、图片、脚注、复杂版式 | [提取与资源](references/extraction.md) |
| 术语与逐段双遍校对 | [翻译规则](references/translation.md) |
| 续译、哈希、状态失效、报告模板 | [项目状态](references/project-state.md) |
| Pandoc、资源路径、标准版与手机版 | [构建指南](references/build.md) |
| 退出码、验收、故障与能力边界 | [检查指南](references/validation.md) |

## 内置脚本

需要 Python 3.9+，无第三方 Python 依赖。在已安装技能的项目根目录中执行：

```sh
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py inspect --epub source/book.epub --json _epub_build/source.json
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py merge --input translation --output _epub_build/clean.md
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py mobile --input _epub_build/clean.md --output _epub_build/mobile.md
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py qc --epub dist/translated.epub --json _epub_build/qc.json
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py compare --left dist/translated.epub --right dist/translated-mobile.epub
```

先用 Pandoc 构建成品，才运行最后两条检查命令。[构建指南](references/build.md) 提供完整命令、PowerShell 和全局安装路径写法。安装技能不会附带安装 Python、Pandoc、Java 或 EPUBCheck。

合并按章节编号的整数排序；重复编号、未经确认的缺号、空章会报错。已有输出需明确 `--force` 才可替换，输入文件禁止覆盖。手机处理保护代码、公式和带标记结构，无法安全拆分的普通长段会报告。退出码：`0` 为命令自身检查通过，`1` 为有待处理问题，`2` 为参数或输入输出错误；成功时也要阅读警告。

## 检查边界

内置 QC 检查部分 ZIP/OPF/XML 结构、manifest 资源、内部链接、工作字段和指定必需文本。两版对比按 spine 读取正文并忽略空白。这些检查不能证明完整 EPUB 合规、视觉效果或翻译忠实度，还需要 EPUBCheck、原文对校和实际阅读器验收。

固定版式、扫描 OCR、加密正文、多媒体、多 rendition 等需要额外处理；具体限制见 [检查指南](references/validation.md)。

## 开发与测试

在仓库目录运行：

```sh
python tools/validate_skill.py
python -m unittest discover -s tests -v
```

测试动态生成原创 EPUB 样本，不包含第三方书籍。有 Pandoc 时，测试还会实际构建两版 EPUB 并核对正文。GitHub Actions 配置 Linux/Windows、Python 3.9/3.13，以及独立的 Pandoc 集成任务；无需翻译 API 或密钥。

## 内容与许可

除非拥有公开发布权限，不要把原书、提取章节、译文、封面或书籍图片提交到技能仓库。[MIT 许可证](LICENSE) 仅适用于技能包，不授予第三方书籍或其译本的权利。
