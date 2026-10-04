# 项目状态、续译与报告

状态清单是工作记录，不是脚本自动生成的完成证明。代理创建并在每个阶段后更新；哈希必须来自实际文件，不能填占位值后声明通过。

## 清单模板

以下是结构示例，替换示例值后使用。稳定章 ID 与展示文件名分离；原文和译文的 SHA-256 均针对文件原始字节。

```json
{
  "schema_version": 1,
  "source": {"path": "source/book.epub", "sha256": "ACTUAL_SHA256", "opf": "EPUB/package.opf"},
  "target_language": "zh-CN",
  "scope": "full-book",
  "chapters": [
    {
      "id": "ch-001",
      "spine_indices": [0],
      "source_hrefs": ["EPUB/text/chapter.xhtml"],
      "source_path": "chapters/001_original.md",
      "source_sha256": "ACTUAL_SHA256",
      "translation_path": "translation/001_章节.md",
      "translation_sha256": null,
      "first_pass": "pending",
      "second_pass": "pending",
      "reviewed_translation_sha256": null,
      "completed_ranges": [],
      "issues": []
    }
  ],
  "exclusions": [],
  "builds": []
}
```

阶段可用 `pending`、`in_progress`、`complete`、`blocked`、`stale`。`complete` 需对应覆盖范围和实际文件；第二遍记录核对时的译稿哈希。细分范围可用稳定段落 ID，或“源文件+起止段落+该源文件哈希”，防止源文变化后旧段号被误用。

## 恢复决策

- 原书哈希相同：核对现有源章、译稿和已校对哈希，从未完成范围继续。
- 原书哈希改变：检查 spine/资源/文本变化，重新确认映射；受影响的提取、翻译、校对和构建标记 `stale`，不覆盖无关人工修改。
- 译稿改变：保留修改；第二遍校对哈希不匹配则需要复核。不能仅因文件非空就视作完整。
- 只有旧项目无清单：根据文件与报告重建映射，无法证明的校对状态标为待核对，不凭猜测补成 `complete`。
- 替换输出前确认它确实是本次可重建产物。记录构建命令、Pandoc 版本、输入译稿/资源/metadata/CSS 哈希和成品哈希。

脚本 `inspect` 会给出原 EPUB 和 spine 资源哈希。其他文件可用 Python `hashlib.sha256(Path(path).read_bytes()).hexdigest()`，或本机文件哈希工具。清单自身不放进正文合并目录的编号文件集合。

## 校对报告模板

```markdown
# 校对报告

- 原书及 SHA-256：
- 目标语言与本次承诺范围：
- 已提取范围 / 排除项及理由：
- 第一遍完成范围 / 未完成范围：
- 第二遍实际对照范围 / 未完成范围：
- 术语表版本和重大决定：

| 位置 | 问题 | 修订或决定 | 状态 |
|---|---|---|---|

## 构建与验收

| 检查 | 对应成品 SHA-256 | 结果/证据 | 未检查原因 |
|---|---|---|---|
| 脚本 QC | | | |
| 章节/注释/图片覆盖 | | | |
| 标准版/手机版文本比较 | | | |
| EPUBCheck | | | |
| 阅读器、设备及版式检查 | | | |

## 剩余问题与交付范围
```

状态使用“通过 / 失败 / 未运行 / 不适用”，并附命令、报告路径或可定位证据。修复后结果关联新成品哈希，旧报告不能代替新输出验收。
