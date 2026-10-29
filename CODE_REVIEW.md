# Code review scope

This export contains only two path-correction helper scripts, not the MORPH application. Review path replacement correctness, accidental overwrites, idempotence and failure handling. Do not claim application or image-quality coverage.

This repository is a sanitized publication snapshot dated 2026-10-29, not the authoritative private development workspace. PUBLIC-FILES.txt identifies exported source paths. Dependencies and private runtime configuration may be absent. No build or runtime acceptance of the export is claimed.

## One-time baseline review

The review PR targets a dedicated minimal baseline branch so the existing source appears as additions. Its head contains the exact published source plus this guide and .coderabbit.yaml. It is an audit vehicle, not a functional update to main. Do not merge it into main or use the baseline as a development branch. Keep main and the original private workspaces unchanged.

Report actionable findings with code evidence and severity. Clearly distinguish confirmed defects, hypotheses, missing export context and untested behavior. Do not automatically implement findings or activate paused projects. Accepted fixes must be checked in the authoritative original workspace and republished deliberately.

## Ongoing work

Develop in the original project workspace. Keep this repository as a sanitized publication target; do not maintain independent implementations in both places. No automatic synchronization or cleanup is configured. CodeRabbit must be connected to this repository through its GitHub App; configuration alone does not install the App or prove that a review ran.
