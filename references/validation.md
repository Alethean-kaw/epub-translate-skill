# 命令行为、检查与限制

## 命令与退出码

所有命令支持 `--help`。脚本输出 JSON；参数解析错误按 argparse 常规写 stderr。

| 命令 | 核心参数 | 退出 1 的含义 |
|---|---|---|
| `inspect` | `--epub`，可选 `--json` | 包、OPF 或 spine 无法读取 |
| `merge` | `--input` 目录、`--output` Markdown | 无；输入/输出错误为 2 |
| `mobile` | `--input`、`--output`；可选 `--threshold 180 --target-min 120 --target-max 180` | 已生成草稿，但有不能安全拆分的超长普通段 |
| `qc` | `--epub`；可选 `--json`、可重复 `--must-contain TEXT`、`--max-paragraph-chars N` | 报告中存在检查错误 |
| `compare` | `--left`、`--right`；可选 `--json` | 正文不一致、正文为空或无法比较 |

退出 0 表示命令自身检查无错误，不表示整书已验收；2 表示参数、输入或输出写入错误。已有输出默认拒绝覆盖；`--force` 允许明确替换输出，但仍禁止覆盖输入，含路径别名。即便指定 `--json`，报告也打印 stdout。断言必需文本不存在、损坏 ZIP/XML 等不能作为成功返回。

`merge --allow-gaps` 允许经过核对的缺号，`--skip-first` 明确排除首个编号文件；都不应用于掩盖漏章。缺号报告按区间表示，不枚举任意巨大序号范围。

## 内置检查覆盖

- `inspect`：原文件 SHA-256、第一 rendition 的 OPF、基础元数据、spine 顺序/资源/linear/媒体类型与资源哈希。
- ZIP：条目数量和解压体积限制、重复/危险路径、符号链接、加密 ZIP 条目；QC 另查 mimetype 内容、首项和压缩方式。
- OPF：manifest ID、spine 引用、资源存在性、标题/语言/标识符及 unique-identifier；作者缺失为提醒，不误判其为 EPUB 必填字段。
- XML：按媒体类型或已知扩展名读取 XHTML，检查根/body、重复 ID；检查 EPUB3 nav 的 toc 导航或 EPUB2 NCX。
- 引用：检查支持的本地 href/src/xlink/poster/data 引用及 XML 片段；处理 URL 百分号编码。不联网验证外部 URL。
- 正文：追溯字段、`--must-contain` 必需文字；可选最长 `<p>` 检查。必需文字只是抽查，不能证明章节齐全。
- 对比：按 spine 读取 XHTML body 文本，排除 head/nav/script/style，去空白后比较；导航文件中的普通正文仍纳入比较。

大小上限：10000 个 ZIP 条目、单项 32 MiB、声明的总解压体积 512 MiB。超限或不支持的输入报告失败，必要时换专门工具处理；不要静默忽略。

## 必须说明的边界

这是一套**部分检查**，不实现完整 EPUB 规范验证。不能保证 CSS/字体/SVG 内部依赖、srcset、所有媒体关系、无障碍语义、媒体叠加、固定版式、压缩包所有资源 CRC 或多 rendition 均正确。XML 实体声明和含 NUL 的 XML（如 UTF-16）暂不支持。

`compare` 只支持 XHTML spine；不支持项或空正文失败。去空白可能掩盖空格/分词变化，它不核对图片、alt、布局、样式，也不证明译文忠实。空白变化和手机重排还需阅读器确认。

`mobile` 是保守的 Markdown 普通段处理器，不是完整解析器，也不理解“书目/诗歌/地址”等语义类别。先识别这些内容，在构建稿中跳过自动拆分或保留受保护结构，再人工核对。`qc --max-paragraph-chars 300` 是可选审查阈值，代码/数学 `<p>` 可豁免，表格/注释等仍可能列出；逐项记录合理例外，不能机械要求全部为零。

## 最终验收顺序

1. 核对状态清单：承诺范围的源章映射、第一遍和第二遍覆盖、所有排除理由；没有占位符或未登记漏章。
2. 对两版运行 `qc`，必要时重复 `--must-contain` 检查首尾及关键段，查明所有 error 和 warning。
3. 运行 `compare`，解释并修正非预期差异。
4. 用已安装的 [EPUBCheck](https://www.w3.org/publishing/epubcheck/docs/) 验证两版并保存报告；常见调用为 `java -jar /path/to/epubcheck.jar dist/translated.epub`。先检查该版本帮助与 Java 要求，不假定工具存在。
5. 实际用目标阅读器打开两版，检查目录/跳转、首尾章、图片/图注、表格/数学、脚注返回、字体与小屏长段；记录阅读器/设备和覆盖范围。
6. 关联成品哈希保存报告，明确未运行和不支持项目。EPUBCheck 通过也不能代替内容校对或视觉检查。

## 常见失败

| 现象 | 处理 |
|---|---|
| duplicate/missing chapter numbers | 检查重复草稿和遗漏章，再决定是否确需例外 |
| output exists | 确认是可重建文件后显式 `--force`，否则换路径 |
| XML parse failure | 定位相应文件；修复非法字符、交叉标签或不支持编码 |
| broken_images / broken_links | 从 OPF/文件所在目录解析引用，修正资源映射和锚点 |
| forbidden_hits | 在构建稿去除工作字段；正文引用这些字段时核实是否误报 |
| unresolved_blocks / long_paragraphs | 逐项审查，仅调整手机版构建稿并重建比较 |
| 文本比较失败 | 核对 spine、标题页、注释及转换丢失；不要当作普通格式差异略过 |

规范参考：[EPUB 3.3](https://www.w3.org/TR/epub-33/)。
