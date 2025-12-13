# Repository Guidelines

## Project Structure & Module Organization
- Entry point is `run.py`, which wires an `Agent` and `Runner` from the installed OpenAI Agents SDK and loads environment variables via `.env`.
- Keep secrets only in `.env`; never commit it. Use `.venv/` for local Python environments.
- Add new Python modules under a dedicated package directory (e.g., `src/` or `praxis/`) and import from there to avoid name collisions with third-party packages.
- Keep top-level files minimal: `README.md` for high-level notes, `LICENSE` for legal terms, and `AGENTS.md` for contributor guidance.

## Build, Test, and Development Commands
- Create a virtual environment: `python -m venv .venv && source .venv/bin/activate` (Windows: `.\.venv\Scripts\activate`).
- Install runtime deps: `pip install -U openai python-dotenv` (add others as needed).
- Run the sample agent: `python run.py` (uses `input="Hello"` to confirm SDK wiring).
- Freeze dependencies when adding packages: `pip freeze > requirements.txt`.

## Coding Style & Naming Conventions
- Use Python 3.10+ and PEP 8 with 4-space indentation, type hints where practical, and f-strings for formatting.
- Name files and modules in `snake_case`; classes in `PascalCase`; functions/variables in `snake_case`.
- Keep functions small and side-effect aware; log or return structured results instead of printing inside library code.
- Run format/lint before pushing (e.g., `black .` and `ruff .` if available).

## Testing Guidelines
- Prefer `pytest` for new tests; place them in `tests/` mirroring the source layout.
- Name test files `test_*.py` and use descriptive test names (e.g., `test_runner_handles_failure`).
- Keep tests isolated from network and secrets; mock SDK calls when possible.
- Run `python -m pytest` locally; add coverage flags (`--cov`) when the suite grows.

## Commit & Pull Request Guidelines
- Write commits in the imperative and keep scope narrow (e.g., `Add runner error handling`).
- PRs should describe intent, key changes, and validation steps; link issues if relevant.
- Include screenshots or logs when UI/behavior changes are involved (if applicable).
- Ensure PRs remain reviewable: minimal unrelated changes, clear error handling, and updated docs when behavior shifts.

## Security & Configuration Tips
- Do not hardcode API keys; load them via `.env` with names like `OPENAI_API_KEY`.
- Treat `.env` as local-only; provide `.env.example` when adding new required settings.
- Avoid committing artifacts or cache directories; update `.gitignore` if new tools add generated files.
