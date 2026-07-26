# Project Rules for Codex

- Always respond in Japanese.
- This project is managed by the Windows version of `uv`. Read its path from
  `WUV` in `.env` when running project commands.
- Do not create, update, delete, or recreate `.venv`. The `.venv` directory is
  reserved for the Windows `uv` environment.
- Do not run Linux/WSL `uv run`, `uv sync`, or similar commands that may modify
  `.venv`.
- If a WSL/Linux-side verification environment is necessary, use `.venv-agent`
  instead of `.venv`.
- For app execution, builds, and real behavior checks, use the Windows `uv`
  path from `.env`, such as `$(WUV) run python earth_photo_manager.pyw`, or use
  the project `Makefile`.
- The app entry point is `earth_photo_manager.pyw`. Main modules live in `src/`.
