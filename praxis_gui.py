from __future__ import annotations

import os
import sys
import time
import json
import hashlib
import subprocess
from pathlib import Path
from typing import Set, Tuple, Optional, Dict, Any, List

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from praxis_core.generator_stub import generate_sample_claims
from praxis_core.verification import verify_evidence_presence
from praxis_core.release import decide_release
from praxis_core.run_artifacts import build_run_artifact, write_run_artifact

# Agent runtime is optional (requires OPENAI_API_KEY + network)
from agents import Runner
from praxis_agents.planner import planner_agent
from praxis_agents.controller import controller_agent


# Flow nodes (wireframe/flowchart shapes)
# kinds: terminator (pill), process (rect)
NODES = [
    ("env", "Env/.env", "terminator"),
    ("planner", "Planner", "process"),
    ("controller", "Controller", "process"),
    ("generator", "Generator", "process"),
    ("evals", "Evals Harness", "process"),
    ("release", "Release", "terminator"),
]

EDGES_FWD = [
    ("env", "planner"),
    ("planner", "controller"),
    ("controller", "generator"),
    ("generator", "evals"),
    ("evals", "release"),
]

EDGE_LOOP = ("evals", "planner")

PRECEDES: Dict[str, Tuple[str, str]] = {
    "planner": ("env", "planner"),
    "controller": ("planner", "controller"),
    "generator": ("controller", "generator"),
    "evals": ("generator", "evals"),
    "release": ("evals", "release"),
}


def _git_rev() -> str:
    try:
        r = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return r or "unknown"
    except Exception:
        return "unknown"


def read_plan_text() -> str:
    plan_path = Path(__file__).parent / "docs" / "praxis_plan.md"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing {plan_path}.")
    return plan_path.read_text(encoding="utf-8")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:10]


def _parse_coverage(summary: str) -> Optional[float]:
    # Expected: "evidence_coverage=0.500 (1/2), threshold=1.0"
    try:
        key = "evidence_coverage="
        i = summary.find(key)
        if i == -1:
            return None
        j = summary.find(" ", i)
        if j == -1:
            j = len(summary)
        return float(summary[i + len(key) : j].strip())
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _extract_eval_metrics(payload: Any) -> Dict[str, Any]:
    """
    Best-effort extraction. We don't assume your eval JSON schema.
    We'll search common keys at top-level or under 'metrics'.
    """
    out = {
        "numeric_agreement": None,
        "unsupported_claims": None,
        "factscore": None,
        "ragas": None,
    }

    if not isinstance(payload, dict):
        return out


def _summarize_claims(claims: List[Any], max_items: int = 4) -> str:
    items: List[str] = []
    for c in claims[:max_items]:
        cid = getattr(c, "id", None) or getattr(c, "claim_id", None) or getattr(c, "name", None) or "claim"
        txt = (
            getattr(c, "text", None)
            or getattr(c, "statement", None)
            or getattr(c, "claim", None)
            or getattr(c, "description", None)
            or ""
        )
        if not isinstance(txt, str):
            txt = str(txt)
        txt = " ".join(txt.strip().split())
        if len(txt) > 70:
            txt = txt[:67] + "..."
        items.append(f"{cid}: {txt}" if txt else str(cid))
    more = max(0, len(claims) - len(items))
    suffix = f"; +{more} more" if more else ""
    return ", ".join(items) + suffix

    candidates: List[dict] = []
    candidates.append(payload)
    if isinstance(payload.get("metrics"), dict):
        candidates.append(payload["metrics"])

    # Some harnesses store results under nested 'results' or 'summary'
    for k in ("results", "summary", "eval", "evaluation"):
        v = payload.get(k)
        if isinstance(v, dict):
            candidates.append(v)
            if isinstance(v.get("metrics"), dict):
                candidates.append(v["metrics"])

    def get_any(keys: List[str]) -> Any:
        for d in candidates:
            for kk in keys:
                if kk in d:
                    return d[kk]
        return None

    out["numeric_agreement"] = _safe_float(get_any(["numeric_agreement", "numericAgreement", "num_agreement"]))
    out["unsupported_claims"] = get_any(["unsupported_claims", "unsupportedClaims", "unsupported", "unsupported_count"])
    if isinstance(out["unsupported_claims"], (int, float, str)):
        try:
            out["unsupported_claims"] = int(out["unsupported_claims"])
        except Exception:
            pass

    out["factscore"] = _safe_float(get_any(["FaCTScore", "factscore", "fact_score"]))
    out["ragas"] = _safe_float(get_any(["RAGAS", "ragas", "ragas_score"]))

    return out


def wireframe_svg(
    active_nodes: Set[str],
    neon_edges: Set[Tuple[str, str]],
    white_edge: Optional[Tuple[str, str]],
    run_counter: str,
    nonce: int,
) -> str:
    """
    - Single wireframe diagram updated in-place (same placeholder).
    - Connectors are 50% smaller (stroke + arrowheads).
    - When an agent is working: the connector that precedes it pulses white (CSS/SVG animate).
    - Handoffs: we still drive a 3x pulse from Python using neon_edges toggling.
    - Run counter sits UNDER the Evals Harness node.
    - Loop edge: OUT of TOP of Evals, INTO TOP of Planner (arc above).
    """
    # Layout (leave space for loop arc)
    x0 = 55
    y = 310
    gap = 200
    W, H = 150, 64

    svg_w = x0 + gap * (len(NODES) - 1) + W + 70
    svg_h = 540

    pos = {nid: (x0 + idx * gap, y) for idx, (nid, _, _) in enumerate(NODES)}

    def left(nid: str) -> float:
        return pos[nid][0]

    def right(nid: str) -> float:
        return pos[nid][0] + W

    def top(nid: str) -> float:
        return pos[nid][1]

    def cy(nid: str) -> float:
        return pos[nid][1] + H / 2

    def cx(nid: str) -> float:
        return pos[nid][0] + W / 2

    # Node style
    base_stroke = "#6b7280"
    node_base_w = 7
    node_neon_w = 11

    # Connector style (50% smaller than before)
    edge_base_w = 3.5
    edge_neon_w = 6.0

    font = "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"
    label_fill = "#e9ecf1"
    dim_op = 0.42
    active_any = bool(active_nodes or neon_edges or white_edge)

    def node_rx(kind: str) -> int:
        return 32 if kind == "terminator" else 10

    def edge_path(a: str, b: str) -> str:
        x1, y1 = right(a), cy(a)
        x2, y2 = left(b), cy(b)
        mid = (x1 + x2) / 2
        return f"M {x1} {y1} C {mid} {y1}, {mid} {y2}, {x2} {y2}"

    def loop_path() -> str:
        # OUT of TOP of Evals -> INTO TOP of Planner
        a, b = EDGE_LOOP
        x1, y1 = cx(a), top(a)
        x2, y2 = cx(b), top(b)
        lift = 175
        c1x, c1y = x1, y1 - lift
        c2x, c2y = x2, y2 - lift
        return f"M {x1} {y1} C {c1x} {c1y}, {c2x} {c2y}, {x2} {y2}"

    # Edge render helpers
    def base_edge(d: str, is_on: bool) -> str:
        op = 1.0 if (not active_any or is_on) else dim_op
        return (
            f'<path d="{d}" fill="none" stroke="{base_stroke}" stroke-width="{edge_base_w}" '
            f'stroke-linecap="round" marker-end="url(#arrow)" opacity="{op}"/>'
        )

    def neon_edge(d: str, is_on: bool) -> str:
        op = "1" if is_on else "0"
        return (
            f'<path d="{d}" fill="none" stroke="url(#aiGrad)" stroke-width="{edge_neon_w}" '
            f'stroke-linecap="round" marker-end="url(#arrowNeon)" filter="url(#glow)" opacity="{op}"/>'
        )

    def white_pulse_edge(d: str, is_on: bool) -> str:
        # White pulse overlay that runs continuously in the browser while node is active.
        if not is_on:
            return ""
        return (
            f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="{edge_neon_w}" stroke-linecap="round" '
            f'marker-end="url(#arrowWhite)" opacity="0.2">'
            f'  <animate attributeName="opacity" values="0.15;1;0.15" dur="0.85s" repeatCount="indefinite" />'
            f"</path>"
        )

    # Node render helpers
    def base_rect(xx: float, yy: float, rx: int, is_on: bool) -> str:
        op = 1.0 if (not active_any or is_on) else dim_op
        return (
            f'<rect x="{xx}" y="{yy}" width="{W}" height="{H}" rx="{rx}" ry="{rx}" '
            f'fill="none" stroke="{base_stroke}" stroke-width="{node_base_w}" opacity="{op}"/>'
        )

    def active_glow(xx: float, yy: float, is_on: bool) -> str:
        op = "0.75" if is_on else "0"
        ex = xx + W / 2
        ey = yy + H / 2
        return (
            f'<ellipse cx="{ex}" cy="{ey}" rx="{W*0.62}" ry="{H*0.95}" '
            f'fill="url(#aiRadial)" filter="url(#blur)" opacity="{op}"/>'
        )

    def active_fillwash(xx: float, yy: float, rx: int, is_on: bool) -> str:
        op = "0.16" if is_on else "0"
        return (
            f'<rect x="{xx+3}" y="{yy+3}" width="{W-6}" height="{H-6}" rx="{max(rx-3, 6)}" ry="{max(rx-3, 6)}" '
            f'fill="url(#aiFill)" opacity="{op}"/>'
        )

    def active_rect(xx: float, yy: float, rx: int, is_on: bool) -> str:
        op = "1" if is_on else "0"
        return (
            f'<rect x="{xx}" y="{yy}" width="{W}" height="{H}" rx="{rx}" ry="{rx}" '
            f'fill="none" stroke="url(#aiGrad)" stroke-width="{node_neon_w}" stroke-linecap="round" '
            f'filter="url(#glow)" opacity="{op}"/>'
        )

    # Build edges
    edge_elems: List[str] = []
    edge_paths: Dict[Tuple[str, str], str] = {}

    for a, b in EDGES_FWD:
        d = edge_path(a, b)
        edge_paths[(a, b)] = d
        on_neon = (a, b) in neon_edges
        on_white = (white_edge == (a, b))
        edge_elems.append(base_edge(d, is_on=on_neon or on_white))
        edge_elems.append(neon_edge(d, is_on=on_neon))
        edge_elems.append(white_pulse_edge(d, is_on=on_white))

    # Loop
    dloop = loop_path()
    on_neon_loop = EDGE_LOOP in neon_edges
    on_white_loop = (white_edge == EDGE_LOOP)
    edge_elems.append(base_edge(dloop, is_on=on_neon_loop or on_white_loop))
    edge_elems.append(neon_edge(dloop, is_on=on_neon_loop))
    edge_elems.append(white_pulse_edge(dloop, is_on=on_white_loop))

    # Build nodes (+ eval counter under evals)
    node_elems: List[str] = []
    for nid, label, kind in NODES:
        xx, yy = pos[nid]
        rx = node_rx(kind)
        is_on = nid in active_nodes

        node_elems.append(active_glow(xx, yy, is_on))
        node_elems.append(active_fillwash(xx, yy, rx, is_on))
        node_elems.append(base_rect(xx, yy, rx, is_on))
        node_elems.append(active_rect(xx, yy, rx, is_on))

        node_elems.append(
            f'<text x="{xx + W/2}" y="{yy + H/2 + 6}" text-anchor="middle" '
            f'fill="{label_fill}" font-family="{font}" font-size="13" font-weight="700">{label}</text>'
        )

        if nid == "evals" and run_counter:
            bw, bh = 60, 20
            bx = xx + W / 2 - bw / 2
            by = yy + H + 10
            node_elems.append(
                f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="10" ry="10" '
                f'fill="#0f172a" stroke="#6b7280" stroke-width="2" opacity="0.95"/>'
            )
            node_elems.append(
                f'<text x="{bx + bw/2}" y="{by + 14}" text-anchor="middle" '
                f'fill="#e9ecf1" font-family="{font}" font-size="12" font-weight="800">{run_counter}</text>'
            )

    return f"""
<div style="background:#0b0d12;border-radius:18px;overflow:hidden;height:78vh;">
  <svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="Autonomous CFO flow diagram" preserveAspectRatio="xMidYMid meet"
       style="width:100%;height:100%;display:block" data-nonce="{nonce}">
    <!-- nonce:{nonce} -->
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
              markerUnits="strokeWidth" markerWidth="4" markerHeight="4" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="{base_stroke}"></path>
      </marker>

      <marker id="arrowNeon" viewBox="0 0 10 10" refX="9" refY="5"
              markerUnits="strokeWidth" markerWidth="4" markerHeight="4" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#a855f7"></path>
      </marker>

      <marker id="arrowWhite" viewBox="0 0 10 10" refX="9" refY="5"
              markerUnits="strokeWidth" markerWidth="4" markerHeight="4" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#ffffff"></path>
      </marker>

      <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
        <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#ff2d55" flood-opacity="0.65"/>
        <feDropShadow dx="0" dy="0" stdDeviation="7" flood-color="#a855f7" flood-opacity="0.35"/>
        <feDropShadow dx="0" dy="0" stdDeviation="10" flood-color="#3b82f6" flood-opacity="0.25"/>
      </filter>

      <filter id="blur" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="10"/>
      </filter>

      <linearGradient id="aiGrad" x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
        <stop offset="0%"  stop-color="#ff2d55"/>
        <stop offset="50%" stop-color="#a855f7"/>
        <stop offset="100%" stop-color="#3b82f6"/>
        <animateTransform attributeName="gradientTransform"
                          type="rotate"
                          from="0 0.5 0.5"
                          to="360 0.5 0.5"
                          dur="1.05s"
                          repeatCount="indefinite"/>
      </linearGradient>

      <radialGradient id="aiRadial" cx="50%" cy="50%" r="55%">
        <stop offset="0%" stop-color="#a855f7" stop-opacity="0.55"/>
        <stop offset="55%" stop-color="#3b82f6" stop-opacity="0.25"/>
        <stop offset="100%" stop-color="#0b0d12" stop-opacity="0"/>
      </radialGradient>

      <linearGradient id="aiFill" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#ff2d55" stop-opacity="0.45"/>
        <stop offset="50%" stop-color="#a855f7" stop-opacity="0.22"/>
        <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.35"/>
      </linearGradient>
    </defs>

    {''.join(edge_elems)}
    {''.join(node_elems)}
  </svg>
</div>
""".strip()


def main() -> None:
    st.set_page_config(page_title="Autonomous CFO", layout="wide")

    # Load .env once at app start
    env_path = Path(__file__).with_name(".env")
    env_present = env_path.exists()
    load_dotenv(dotenv_path=env_path)

    col_left, col_right = st.columns([2, 1], gap="large")

    # Right: terminal + summary table
    with col_right:
        st.title("Terminal output")
        log_slot = st.empty()
        table_slot = st.empty()

    # Left: title + controls + diagram
    with col_left:
        rev = _git_rev()
        st.title(f"Autonomous CFO (rev {rev})")

        c1, c2, c3, c4, c5 = st.columns([1.15, 0.9, 1.0, 1.2, 2.2], vertical_alignment="bottom")
        with c1:
            run_btn = st.button("Run flow", type="primary", use_container_width=True)
        with c2:
            runs = st.number_input("Runs", min_value=1, max_value=50, value=1, step=1)
            n_claims = st.number_input(
                "Claims per run",
                min_value=1,
                max_value=50,
                value=6,
                step=1,
                help="How many claims to generate per run (used by the Generator step).",
                key="n_claims",
            )

        with c3:
            run_agents = st.checkbox("Run agents", value=True, help="Enable Planner/Controller calls (requires OPENAI_API_KEY).")
        with c4:
            min_cov = st.slider("Min attribution", 0.0, 1.0, 1.0, 0.05)
        with c5:
            dataset_root = st.text_input("PRAXIS_DATASET_ROOT (optional)", value=os.environ.get("PRAXIS_DATASET_ROOT", ""))

        graph_slot = st.empty()

    # Terminal state (Streamlit code block; keep default wrapping behavior)
    logs = "Ready."
    def term_render() -> None:
        log_slot.code(logs, language="text")

    def term_append(line: str) -> None:
        nonlocal logs
        logs = (logs + ("\n" if logs else "") + line).rstrip("\n")
        term_render()

    term_render()

    # Graph state
    active_nodes: Set[str] = set()
    neon_edges: Set[Tuple[str, str]] = set()
    white_edge: Optional[Tuple[str, str]] = None
    eval_completed = 0
    run_counter = f"{eval_completed}/{int(runs)}" if int(runs) > 1 else ""
    nonce = 0

    def graph_render() -> None:
        nonlocal nonce
        nonce += 1
        html_svg = wireframe_svg(active_nodes, neon_edges, white_edge, run_counter, nonce)
        graph_slot.empty()
        with graph_slot.container():
            components.html(html_svg, height=720, scrolling=False)

    def set_active_node(node_id: Optional[str]) -> None:
        nonlocal active_nodes, neon_edges, white_edge
        active_nodes = {node_id} if node_id else set()
        neon_edges = set()
        # While Planner runs, also pulse the loop edge (Evals -> Planner) in white.
        if node_id == 'planner':
            white_edge = EDGE_LOOP
        else:
            white_edge = PRECEDES.get(node_id) if node_id in PRECEDES else None
        graph_render()
        time.sleep(0.02)

    def pulse_edge(edge: Tuple[str, str], cycles: int = 3) -> None:
        """
        Handoff pulse: flash the connector 3x before moving to the next agent.
        Uses NEON edge flashes (distinct from the continuous WHITE pulse that precedes an active node).
        """
        nonlocal neon_edges
        for _ in range(cycles):
            neon_edges = {edge}
            graph_render()
            time.sleep(0.10)
            neon_edges = set()
            graph_render()
            time.sleep(0.07)

    # Always show diagram before runs
    graph_render()

    if not run_btn:
        return

    # Reset output on click
    logs = ""
    term_render()

    # Execution summary (requested)
    api_key_present = bool(os.environ.get("OPENAI_API_KEY"))
    root = (dataset_root or os.environ.get("PRAXIS_DATASET_ROOT") or "").strip() or None
    multi = int(runs) > 1

    term_append("Execution summary:")
    term_append(f"- runs={int(runs)}")
    term_append(f"- run_agents={bool(run_agents)}")
    term_append(f"- OPENAI_API_KEY={'SET' if api_key_present else 'MISSING'}")
    term_append(f"- .env={'present' if env_present else 'missing'} ({env_path})")
    term_append(f"- PRAXIS_DATASET_ROOT={root if root else '(none)'}")
    term_append(f"- min_attribution_coverage={float(min_cov):.2f}")
    term_append("")

    plan_text = read_plan_text()

    # Results table
    results: List[Dict[str, Any]] = []
    prev: Optional[Dict[str, Any]] = None

    for i in range(int(runs)):
        run_idx = i + 1
        run_start = time.time()
        graph_render()

        # ENV
        set_active_node("env")
        term_append(f"run {run_idx} - Env: loaded environment (.env {('present' if env_present else 'missing')})")
        pulse_edge(("env", "planner"), cycles=3)

        # PLANNER
        set_active_node("planner")
        planner_out = ""
        planner_hash = ""
        agents_ran = False
        agent_error = ""

        if run_agents and api_key_present:
            try:
                agents_ran = True
                planner_input = (
                    "Using the following Praxis plan context, produce the roadmap.\n\n"
                    "=== PRAXIS PLAN CONTEXT ===\n"
                    f"{plan_text}\n"
                    "=== END CONTEXT ===\n"
                )
                roadmap = Runner.run_sync(planner_agent, input=planner_input)
                planner_out = getattr(roadmap, "final_output", getattr(roadmap, "output", str(roadmap)))
                planner_hash = _sha(planner_out)
                term_append(f"run {run_idx} - Planner: roadmap generated (hash={planner_hash})")
            except Exception as e:
                agent_error = str(e)
                term_append(f"run {run_idx} - Planner: ERROR ({agent_error})")
        else:
            term_append(f"run {run_idx} - Planner: skipped (Run agents disabled or OPENAI_API_KEY missing)")

        pulse_edge(("planner", "controller"), cycles=3)

        # CONTROLLER
        set_active_node("controller")
        controller_out = ""
        controller_hash = ""
        if run_agents and api_key_present and not agent_error:
            try:
                controller_input = (
                    "You are given a roadmap produced by PraxisPlanner.\n"
                    "Select the single next best small, reversible step to implement in this repo.\n"
                    "Constraints:\n"
                    "- Do NOT create a new top-level claims.py.\n"
                    "- The canonical Claim/Evidence dataclasses already live in src/praxis_core/claims.py.\n"
                    "- Propose changes only within the existing src/praxis_core/* modules unless explicitly instructed.\n\n"
                    "=== ROADMAP ===\n"
                    f"{planner_out}\n"
                    "=== END ROADMAP ===\n"
                )
                decision = Runner.run_sync(controller_agent, input=controller_input)
                controller_out = getattr(decision, "final_output", getattr(decision, "output", str(decision)))
                controller_hash = _sha(controller_out)
                term_append(f"run {run_idx} - Controller: next-step selected (hash={controller_hash})")
            except Exception as e:
                agent_error = str(e)
                term_append(f"run {run_idx} - Controller: ERROR ({agent_error})")
        else:
            term_append(f"run {run_idx} - Controller: skipped")

        pulse_edge(("controller", "generator"), cycles=3)

        # GENERATOR
        set_active_node("generator")
        claims = generate_sample_claims(root, run_idx=run_idx, n_claims=int(n_claims), seed=run_idx)
        term_append(f"run {run_idx} - Generator: generated {len(claims)} claims ({_summarize_claims(claims)})")
        pulse_edge(("generator", "evals"), cycles=3)

        # EVALS HARNESS
        set_active_node("evals")
        report = verify_evidence_presence(claims, min_attribution_coverage=float(min_cov))
        v_status = report.status.value if hasattr(report.status, "value") else str(report.status)
        coverage = _parse_coverage(getattr(report, "summary", ""))

        # Run the harness and attempt to extract richer metrics if present
        eval_smoke_ok = None
        eval_metrics = {"numeric_agreement": None, "unsupported_claims": None, "factscore": None, "ragas": None}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "praxis_evals.run_local", "--case", "praxis_evals/cases/smoke.yaml"],
                capture_output=True,
                text=True,
                check=False,
                timeout=90,
            )
            eval_smoke_ok = (proc.returncode == 0)

            latest_path = Path("praxis_evals/out/latest.json")
            if latest_path.exists():
                payload = json.loads(latest_path.read_text(encoding="utf-8"))
                m = _extract_eval_metrics(payload)
                if isinstance(m, dict):
                    eval_metrics.update(m)

        except Exception:
            pass

        cov_txt = f"{coverage:.3f}" if isinstance(coverage, float) else "n/a"
        na_txt = "n/a"
        
        # Robust formatting (eval_metrics can be None / missing keys)
        if not isinstance(eval_metrics, dict):
            eval_metrics = {"numeric_agreement": None, "unsupported_claims": None, "factscore": None, "ragas": None}
        
        na_v = eval_metrics.get("numeric_agreement")
        uc_v = eval_metrics.get("unsupported_claims")
        fs_v = eval_metrics.get("factscore")
        rg_v = eval_metrics.get("ragas")
        
        na_s = f"{na_v:.3f}" if isinstance(na_v, float) else na_txt
        fs_s = f"{fs_v:.3f}" if isinstance(fs_v, float) else na_txt
        rg_s = f"{rg_v:.3f}" if isinstance(rg_v, float) else na_txt
        uc_s = str(uc_v) if uc_v is not None else na_txt
        ok_s = "true" if eval_smoke_ok is True else ("false" if eval_smoke_ok is False else na_txt)
        
        term_append(
            f"run {run_idx} - Evals: verification={v_status}, coverage={cov_txt}, "
            f"numeric_agreement={na_s}, unsupported_claims={uc_s}, FaCTScore={fs_s}, RAGAS={rg_s}, smoke_ok={ok_s}"
        )
        
        # Evals completed -> advance counter (0/x before first eval, then 1/x, ... x/x)
        eval_completed += 1
        if int(runs) > 1:
            run_counter = f"{eval_completed}/{int(runs)}"
            graph_render()


        pulse_edge(("evals", "release"), cycles=3)

        # RELEASE
        set_active_node("release")
        outcome = decide_release(report)
        r_decision = outcome.decision.value if hasattr(outcome.decision, "value") else str(outcome.decision)
        r_reason = getattr(outcome, "reason", "")
        term_append(f"run {run_idx} - Release: decision={r_decision} ({r_reason})")

        dur_s = round(time.time() - run_start, 2)

        # Persist immutable run artifact (does not affect gating)
        try:
            artifact = build_run_artifact(
                run_source="praxis_gui.py",
                dataset_root=str(dataset_root) if dataset_root else None,
                min_attribution_coverage=float(min_cov),
                planner_output=(planner_out if "planner_out" in locals() else None),
                controller_output=(controller_out if "controller_out" in locals() else None),
                claims=claims,
                verification_report=report,
                release_outcome=outcome,
                extra={
                    "run_idx": int(run_idx),
                    "runs": int(runs),
                    "run_agents": bool(run_agents),
                    "eval_metrics": eval_metrics,
                    "eval_smoke_ok": eval_smoke_ok,
                    "agent_error": agent_error,
                },
            )
            out_path = write_run_artifact(artifact)
            # Keep terminal noise low for multi-run; show path only on single-run
            if int(runs) == 1:
                term_append(f"run {run_idx} - Artifact: {out_path}")
        except Exception as _artifact_err:
            if int(runs) == 1:
                term_append(f"[non-fatal] artifact write failed: {_artifact_err}")

        row = {
            "run": run_idx,
            "agents": "ran" if (agents_ran and not agent_error) else ("error" if agent_error else "skipped"),
            "planner_hash": planner_hash,
            "controller_hash": controller_hash,
            "verification_status": v_status,
            "evidence_coverage": coverage if coverage is not None else None,
            "numeric_agreement": eval_metrics.get("numeric_agreement"),
            "unsupported_claims": eval_metrics.get("unsupported_claims"),
            "factscore": eval_metrics.get("factscore"),
            "ragas": eval_metrics.get("ragas"),
            "eval_smoke_ok": eval_smoke_ok,
            "release": r_decision,
            "duration_s": dur_s,
        }

        # Improvement deltas vs previous run
        if prev is None:
            row["Δ_evidence_coverage"] = None
            row["Δ_numeric_agreement"] = None
            row["Δ_factscore"] = None
            row["Δ_ragas"] = None
        else:
            def delta(cur, prv):
                if isinstance(cur, float) and isinstance(prv, float):
                    return cur - prv
                return None

            row["Δ_evidence_coverage"] = delta(row["evidence_coverage"], prev.get("evidence_coverage"))
            row["Δ_numeric_agreement"] = delta(row["numeric_agreement"], prev.get("numeric_agreement"))
            row["Δ_factscore"] = delta(row["factscore"], prev.get("factscore"))
            row["Δ_ragas"] = delta(row["ragas"], prev.get("ragas"))

        results.append(row)
        prev = row

        # Single-run: keep existing detailed output as well
        if not multi:
            term_append("")
            term_append("===== Detailed (single-run) output =====")
            if run_agents and api_key_present and not agent_error:
                term_append("=== PraxisPlanner output ===")
                term_append(planner_out)
                term_append("=== PraxisController output ===")
                term_append(controller_out)
            term_append("=== Verification checks ===")
            term_append(f"Summary: {report.summary}")
            for c in report.checks:
                term_append(f"- {c.claim_id}: {c.status.value} ({c.reason})")
            term_append("")

        # Between runs: loop back Evals -> Planner (neon pulse)
        if run_idx < int(runs):
            set_active_node("evals")
            pulse_edge(EDGE_LOOP, cycles=3)
            set_active_node("planner")

        # Clear active state between runs
        set_active_node(None)

    # Table after completion (requested)
    if multi:
        table_slot.dataframe(results, use_container_width=True)

    term_append("")
    term_append("Done.")
    set_active_node(None)


if __name__ == "__main__":
    main()
