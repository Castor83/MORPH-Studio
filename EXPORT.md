# MORPH application source export — 2026-10-30

This local preparation replaces the scope of the earlier two-helper-script export. It has not yet been published. The existing audit PR #1 reviews the earlier snapshot and does not establish coverage of this application export.

## What is included

- The current MORPH Python backend, browser frontend, provider integrations and tests.
- Current workflow JSON files, including all six workflows referenced by the application catalogue.
- Project start/stop/setup and verification scripts, the LM Studio integration and its tests.
- The vendored ComfyUI MCP server source, tests and original MIT licence.
- Technical development reports, historical acceptance harnesses, dependency/version records and the Phase 2 model-source manifest.

The preparation contains 253 source/documentation files. All 150 files selected from the current application, workflow, integration, test and root-entrypoint areas are included. A further 103 files provide technical history and dependency information. These counts exclude the generated export metadata files.

The source is the current working tree at local application commit `dc1e7a6`, including existing uncommitted and untracked source files. It is not merely a copy of that commit. `PUBLIC-FILES.txt` lists every exported source/documentation file. `PUBLIC-SOURCE.json` records source and export SHA-256 hashes. Thirteen copies have personal username/path details replaced with placeholders; the original private files were not edited.

## Exclusions and boundaries

No image files are included, including generated or synthetic test images. No private input/output media, chats, saved pause/session state, raw runtime receipts, credentials, caches, downloaded packages, installed runtimes or model weights are included. Historical duplicate code snapshots and backup directories are excluded. Reports may reference excluded historical images and receipts; those references are not evidence that the referenced files are part of this export.

ComfyUI, its custom nodes, Python packages, Ollama/LM Studio and models remain external dependencies. The package lists and model manifest are historical records with limited scope, not a verified complete installer or a current model inventory. A checkout is not a complete runnable installation. The root README and older reports retain historical statements; for example, the UI README mentions port 8765 whereas the current Python entrypoint and server policy use 8877. This export does not repair application or documentation discrepancies.

The obsolete `correct-active-data-paths.py` and `correct-pause-paths.py` migration helpers remain removed. Saved pause files have not been changed.

## Verification scope

Source-to-export file coverage, SHA-256 comparisons, Python compilation without importing application modules, JSON parsing, JavaScript syntax checks and PowerShell parsing are used for this preparation. TypeScript execution/build, runtime integration, image quality and model operation are not claimed. No model, service, installer or download is started for this export. Historical test results in the included reports remain historical.

The static credential-pattern scan found no matching live-token patterns in the selected text. This is not an exhaustive privacy or security guarantee. Publication remains a separate step after the concrete file scope has been reviewed.
