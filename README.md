# EPUB Translate Skill

EPUB Translate Skill is a reusable workflow package for EPUB book translation projects. It turns a source EPUB into ordered Markdown chapters, maintains a glossary and proofreading report, supports a two-pass translation workflow, and helps build both desktop and phone-optimized EPUB outputs.

## What It Does

- Extracts EPUB content by `content.opf` spine order.
- Keeps sortable chapter files such as `00_...md`, `01_...md`.
- Maintains a book-specific glossary and proofreading report.
- Enforces a two-pass workflow: first complete the full draft, then perform paragraph-by-paragraph source verification.
- Keeps mobile paragraph splitting in build artifacts instead of canonical translation drafts.
- Provides helper commands for clean Markdown merging, mobile paragraph splitting, and EPUB package QA.

## Folder Structure

```text
epub-translate-skill/
├── SKILL.md
├── README.md
├── LICENSE
├── agents/
│   └── openai.yaml
├── references/
│   └── workflow.md
└── scripts/
    └── epub_project_tools.py
```

## Usage

Copy or install this folder in a compatible agent or workflow environment, then use the EPUB translation workflow on a book project.

Helper script examples:

```powershell
python .\scripts\epub_project_tools.py merge --input "<translation-folder>" --output "_epub_build\clean.md"
python .\scripts\epub_project_tools.py mobile --input "_epub_build\clean.md" --output "_epub_build\mobile.md"
python .\scripts\epub_project_tools.py qc --epub "<translated-book>.epub" --json "_epub_build\qc.json"
```

Pandoc is still required for EPUB generation. If `pandoc` is not available on PATH, use your own local executable path:

```text
<pandoc-path>
```

## Important Copyright Note

This repository should contain only the skill, workflow notes, and helper scripts. Do not commit copyrighted source EPUB files, extracted book chapters, generated translations, covers, or book images unless you own the rights or have permission to publish them.

The license below applies to this skill package only. It does not grant rights to any third-party books or translated book content processed with the skill.

## License

MIT License. See `LICENSE`.
