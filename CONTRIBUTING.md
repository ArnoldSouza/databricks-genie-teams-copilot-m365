# Contributing

Thanks for your interest in contributing! This repository follows a documentation‑first approach. **Do not change runtime logic** unless explicitly requested.

## Workflow
- **Branching:** feature branches from `main` using the prefix `feat/`, `fix/`, `docs/`, or `chore/`.
- **Commits:** use concise, imperative messages. Conventional commits are encouraged (e.g., `docs: add README badges`).  
- **Pull Requests:** keep them small and focused; add screenshots/outputs when relevant.

## Code style
- **Docstrings:** use docstrings for modules, classes, and functions.  
- **Typing:** add type hints where possible (no runtime changes required).  
- **Comments:** English only, concise and actionable.

## Pre‑commit
This project includes a basic pre‑commit configuration to enforce whitespace and EOF hygiene. Install and run locally:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Security
- Never commit secrets or `.env` files.
- Never commit the folder `/infra/secrets` files.
- For security concerns, see `SECURITY.md`.
