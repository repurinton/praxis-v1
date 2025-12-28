# Praxis — Verification-Aware Autonomous CFO

Praxis is an evidence-first, verification-aware scaffold for generating and releasing “Autonomous CFO” style outputs under explicit release gates.

The current implementation includes:
- Canonical **Claim / Evidence** data model
- Dataset-grounded **Generator** that emits a configurable number of claims per run with controlled per-run variation
- **Verification** gate (evidence/attribution coverage)
- **Release** gate (hold/release decision based on verification)
- Local **Evaluation** smoke harness
- **Streamlit GUI** that orchestrates the workflow, visualizes the flow, and displays terminal-style output
- Append-only **Run Artifacts** written by both the CLI runner and the GUI for reproducibility and traceability

---

## Repository layout

- `src/`
  - `praxis_core/` — claim model, generator, verification, release gating, run artifacts
  - `praxis_agents/` — Planner + Controller agents (optional; requires OpenAI credentials + network)
- `praxis_evals/` — local evaluation harness (smoke runner + cases)
- `praxis_gui.py` — Streamlit GUI orchestration app
- `run.py` — CLI-style end-to-end runner (agents optional)
- `praxis_runs/` — runtime output; immutable per-run JSON artifacts + `latest.json`

---

## Requirements

- Python **3.10+** (3.11 recommended)
- macOS/Linux supported (commands below assume macOS/zsh)

---

## Install and setup

### 1) Create and activate a virtual environment

From the repo root:

```bash
cd praxis-v1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2) Install project dependencies

Install the package in editable mode plus common dev dependencies:

```bash
pip install -e ".[dev]"
```

Install Streamlit for the GUI:

```bash
pip install streamlit
```

If you intend to run Planner/Controller agents, ensure the agent dependencies are installed (if defined in your packaging):

```bash
pip install -e ".[agents]"
```

---

## Configure environment variables (.env)

Create `.env` in the repo root (same directory as `run.py` and `praxis_gui.py`):

```bash
cat > .env <<'ENV'
# Required to run Planner/Controller agents (optional; GUI/CLI will skip if missing)
OPENAI_API_KEY=sk-REPLACE_ME

# Optional: dataset root used by the Generator (if you have prepared synthetic data)
# PRAXIS_DATASET_ROOT=./data/latest

# Optional: where run artifacts are written (default: praxis_runs)
# PRAXIS_RUNS_DIR=praxis_runs
ENV
```

Notes:
- If `OPENAI_API_KEY` is missing, the system still runs **Generator → Verification → Release**, but skips Planner/Controller agent calls.
- If `PRAXIS_DATASET_ROOT` is unset, the generator falls back to defaults.

---

## Verify the installation

### Compile (syntax check)

```bash
python3 -m py_compile run.py praxis_gui.py
```

### Run unit tests

```bash
make test
```

### Run evaluation smoke (tests + local eval)

```bash
make eval
```

---

## Run the CLI pipeline

The CLI runner (`run.py`) executes:
- Planner + Controller (only if `OPENAI_API_KEY` is set and agents are reachable)
- Generator → Verification → Release (always)
- Writes an append-only run artifact JSON to `praxis_runs/`

Run:

```bash
PYTHONPATH=src .venv/bin/python run.py
```

Artifacts written:
- `praxis_runs/run_<timestamp>_<gitrev>.json` (immutable per run)
- `praxis_runs/latest.json` (convenience pointer)

---

## Run the GUI (Agent orchestration)

The GUI provides:
- Left: a wireframe flow diagram (Env → Planner → Controller → Generator → Evals → Release)
- Right: terminal-style output for the workflow
- Multi-run mode: loops **Evals → Planner** for subsequent iterations

### Launch the GUI

```bash
PYTHONPATH=src .venv/bin/python -m streamlit run praxis_gui.py
```

Open the URL Streamlit prints (typically `http://localhost:8501`).

### GUI controls

- **Runs**: number of workflow iterations to execute
- **Claims per run**: number of claims the Generator emits per iteration
- **Run agents**: enables Planner/Controller calls (requires `OPENAI_API_KEY`)
- **Min attribution**: threshold passed into evidence/attribution verification
- **PRAXIS_DATASET_ROOT**: optional dataset root to drive dataset-grounded generation

### Output behavior

- **Runs = 1**:
  - terminal output includes verbose details including verification checks
- **Runs > 1**:
  - each run emits concise, run-prefixed step summaries (e.g., `run 2 - Generator: ...`)
  - a summary table is shown after completion
  - each run writes an append-only run artifact JSON

---

## Troubleshooting

### `ModuleNotFoundError: praxis_core`

Use `PYTHONPATH=src` (as shown in the run commands) and/or ensure the package is installed:

```bash
pip install -e .
```

### Planner/Controller agent failures

If agent calls fail:
- confirm `OPENAI_API_KEY` is correct and active
- confirm network connectivity
- run with agents disabled (GUI: uncheck **Run agents**) to validate the non-agent pipeline

