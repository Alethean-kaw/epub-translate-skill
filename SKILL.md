---
name: epub-translate-skill
description: Use when working on EPUB book translation projects that need spine-based extraction, sortable Markdown chapters, target-language translation drafts, glossary and proofreading reports, paragraph-by-paragraph source verification, clean desktop EPUB output, or separate phone-optimized EPUB output.
---

# EPUB Translate Skill

This package supports EPUB translation projects.

## Core Rule

Treat every book as a durable file-backed project. Preserve the source EPUB, split source chapters, canonical translation drafts, glossary, proofreading report, build-only artifacts, and final EPUB outputs as separate layers.

Use the two-pass standard:

1. First pass: complete the full translated draft without missing chapters or summarizing the source.
2. Second pass: compare source and translation paragraph by paragraph, then revise for fidelity, terminology, logic, tone, formatting, links, notes, formulas, and images.
3. Final build: generate desktop and mobile EPUBs only after second-pass status is recorded in `校对报告.md`.

Read `references/workflow.md` when starting a new book, resuming a partial book, rebuilding an EPUB, or deciding validation scope.

## Expected Project Layout

Create or reuse this structure under the book folder:

```text
<书籍目录>/
├── <原书>.epub
├── <书名>-分章/
├── <book-title>-<target-language>-translation/
│   ├── 00_....md
│   ├── 01_....md
│   ├── glossary.md / 译名表.md
│   └── proofreading-report.md / 校对报告.md
├── _epub_build/
├── <book-title>-<target-language>-translation.epub
└── <book-title>-<target-language>-translation-mobile.epub
```

Use sortable numeric chapter filenames. Use target-language-facing filenames and H1 titles for translated files, while keeping traceability headers in the project's preferred language:

```markdown
# Target-language title

原文标题：Original Title

来源文件：00_original.md

---
```

## Workflow

1. Inventory the EPUB and existing folders.
   - Locate the source EPUB.
   - Check for existing split chapters, translations, glossary, proofreading report, and `_epub_build`.
   - Do not overwrite canonical drafts unless the user asked for in-place correction.

2. Extract by EPUB reading order.
   - Use `content.opf` spine as the authority.
   - Cross-check `toc.ncx` or EPUB nav when available.
   - Preserve images and rewrite image links so translated files can resolve them.
   - Exclude cover/logo/helper pages from body chapters only when they are not reader-facing content.

3. Build source Markdown chapters.
   - Generate consecutive `00_...md`, `01_...md` or three-digit filenames.
   - Preserve title hierarchy, paragraphs, emphasis, block quotes, footnote markers, tables, formulas, and image positions.
   - Normalize layout-only breaks and spaces without changing meaning.

4. Create translation control artifacts.
   - Maintain a glossary file, such as `glossary.md` or `译名表.md`, for recurring terms, names, works, institutions, and context-sensitive choices.
   - Maintain a proofreading report, such as `proofreading-report.md` or `校对报告.md`, for progress and second-pass coverage.

5. Translate in the first pass.
   - Keep source order and formatting.
   - Do not summarize, omit, modernize, or add commentary unless the user requests it.
   - Keep legal, bibliographic, index, appendix, and reference details faithful.

6. Proofread in the second pass.
   - Compare the source chapter and translation paragraph by paragraph.
   - Fix mistranslation, missing text, added meaning, reversed logic, terminology drift, broken references, and unnatural target-language syntax.
   - Record completion in the proofreading report before producing final EPUBs.

7. Build clean EPUB variants.
   - Use only numbered translated chapter files.
   - Exclude glossary files, proofreading reports, temporary drafts, and work notes.
   - Strip `原文标题：`, `来源文件：`, and work separators from the clean build draft.
   - Use Pandoc from PATH when available; otherwise use a local `<pandoc-path>` supplied by the user or project configuration.
   - Build a separate mobile draft for paragraph splitting; never apply phone-only short paragraphs to canonical translation files.

8. Validate before completion.
   - EPUB existence alone is not enough.
   - Check ZIP structure, OPF metadata, XML-parseable XHTML, images, internal links, forbidden work headers, chapter presence, and desktop/mobile text equivalence.
   - For mobile builds, ordinary body paragraphs over 300 target-language characters should be zero unless they are formulas, indexes, references, tables, or other protected material.

## Bundled Script

Use `scripts/epub_project_tools.py` for repeatable build-prep and QA:

```powershell
python .\epub-translate-skill\scripts\epub_project_tools.py merge --input "<translation-folder>" --output "_epub_build\clean.md"
python .\epub-translate-skill\scripts\epub_project_tools.py mobile --input "_epub_build\clean.md" --output "_epub_build\mobile.md"
python .\epub-translate-skill\scripts\epub_project_tools.py qc --epub "<translated-book>.epub" --json "_epub_build\qc.json"
```

Adapt scripts when a book has unusual tables, formulas, anchors, or cover handling.

## Pitfalls

- Do not trust filesystem order, Pandoc order, or visual ZIP order over `content.opf` spine.
- Do not leave partial chapter drafts in the formal translation folder.
- Do not let mobile paragraph splitting pollute canonical drafts.
- Do not count a book as complete until `校对报告.md` explicitly says first pass and second pass are complete.
- Do not accept a Pandoc EPUB without XML-level XHTML validation.
- Do not silently change historical facts, legal metadata, ISBNs, page numbers, or reference entries.
