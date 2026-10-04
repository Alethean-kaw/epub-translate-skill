# EPUB Translate Skill

[简体中文](README.zh-CN.md)

A reusable agent skill for translating EPUB books through a complete first draft and a separate, paragraph-by-paragraph source review. It keeps source material, canonical translations and build artifacts separate, supports resumable chapter work, and guides the creation of standard and mobile EPUB editions.

The agent performs extraction, translation and proofreading with available tools. The bundled Python script provides offline inspection, merge, mobile formatting and partial quality checks; it is not an automatic book translator.

## One-command installation

Requires Node.js and npm (`npx`). Skills CLI 1.7.0, used to verify these commands, requires Node.js 22.20.0 or newer. Install from a terminal; no ZIP download is needed.

**Project installation** — run from your project root:

```sh
npx --yes skills@latest add Alethean-kaw/epub-translate-skill --skill epub-translate-skill --agent universal --yes
```

Destination: `.agents/skills/epub-translate-skill/` in the current project.

**Global installation** — run from any directory:

```sh
npx --yes skills@latest add Alethean-kaw/epub-translate-skill --skill epub-translate-skill --agent universal --global --yes
```

Destination: `~/.agents/skills/epub-translate-skill/`. On Windows, `~` is your user profile directory. `--agent universal` targets the shared skill location; agents with different discovery paths may need their own configuration. Restart or reload the agent if it does not immediately discover the skill.

To update, rerun the installation command for the same scope. Save any local edits first: reinstalling can replace skill files. For a reproducible installer version, substitute `skills@1.7.0` for `skills@latest`. See the [Skills CLI documentation](https://github.com/vercel-labs/skills) for CLI options.

## Use the skill

Example request:

> Use $epub-translate-skill to translate this EPUB into Simplified Chinese. Resume any existing chapters, keep a glossary, complete both translation passes, then build standard and mobile EPUBs. Report unreviewed sections and checks that could not be run.

Start with [SKILL.md](SKILL.md). Detailed guidance covers [workflow](references/workflow.md), [extraction and resources](references/extraction.md), [translation](references/translation.md), [project state](references/project-state.md), [building](references/build.md) and [validation](references/validation.md).

## Offline helpers

Python 3.9+; no third-party Python dependencies. From a project with the skill installed:

```sh
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py inspect --epub source/book.epub --json _epub_build/source.json
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py merge --input translation --output _epub_build/clean.md
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py mobile --input _epub_build/clean.md --output _epub_build/mobile.md
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py qc --epub dist/translated.epub --json _epub_build/qc.json
python .agents/skills/epub-translate-skill/scripts/epub_project_tools.py compare --left dist/translated.epub --right dist/translated-mobile.epub
```

`qc` and `compare` run **after** building the EPUBs with Pandoc; see [complete build instructions](references/build.md), including PowerShell and global-install paths. Installing the skill does not install Python, Pandoc, Java or EPUBCheck.

Numbered chapter files are merged in numeric order. Duplicate numbers, unreviewed gaps and empty chapters fail. Existing outputs require `--force`; inputs cannot be overwritten. Mobile formatting preserves protected structures and reports prose it cannot safely split. Exit codes: `0` command checks passed, `1` reported checks/issues, `2` usage or input/output error. Read JSON warnings even on success.

## Quality boundaries

QC covers selected ZIP/OPF/XML, manifest resources, internal links, work headers and required-text checks. Text comparison follows the spine and ignores whitespace. These do not establish complete EPUB conformance, visual quality or translation fidelity. Use EPUBCheck, source review and an actual reader as described in [validation](references/validation.md). Complex layouts, DRM, OCR, multimedia and multi-rendition books need additional handling.

## Development and tests

From a repository checkout:

```sh
python tools/validate_skill.py
python -m unittest discover -s tests -v
```

Tests generate synthetic EPUBs without third-party book content. If Pandoc is installed, the suite builds real standard/mobile EPUBs and verifies their body text. GitHub Actions runs Python 3.9 and 3.13 on Linux and Windows, plus a dedicated Pandoc integration job. No translation service or API key is required.

## Content and license

Keep source books, extracted chapters, translations and book assets outside this skill repository unless you have permission to publish them. The [MIT license](LICENSE) covers this skill package, not third-party books or their translations.
