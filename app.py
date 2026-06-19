"""Streamlit entry point — AI Usage Dashboard v1 Phase 1 UI."""

import math
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database.connection import get_connection
from src.database.schema import get_setting, init_db, save_setting
from src.ingestion.loader import ingest_all, ingest_provider
from src.metrics.heuristics import check_context_debt, detect_pleasantries
from src.providers.registry import get_all_providers

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Usage Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }

div[data-testid="stMetric"] {
    background: rgba(30,41,59,0.7);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 14px 18px;
}
.stTabs [data-baseweb="tab"] { font-size: 0.95rem; font-weight: 500; padding: 8px 14px; }

.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}
.metric-box  { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:16px; text-align:center; }
.metric-title{ color:#94a3b8; font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:.05em; margin-bottom:5px; }
.metric-val  { font-size:1.7rem; font-weight:700; color:#38bdf8; }
.metric-sub  { font-size:0.72rem; color:#64748b; margin-top:3px; }

.warning-card{ background:#272111; border-left:5px solid #eab308; padding:10px 14px; border-radius:6px; margin:7px 0; color:#ffedd5; font-size:.9rem; }
.info-card   { background:#0f1c2e; border-left:5px solid #38bdf8;  padding:10px 14px; border-radius:6px; margin:7px 0; color:#e0f2fe;  font-size:.9rem; }
.success-card{ background:#0d2216; border-left:5px solid #22c55e;  padding:10px 14px; border-radius:6px; margin:7px 0; color:#dcfce7;  font-size:.9rem; }
.tok-badge   { color:#a8a29e; background:#292524; padding:2px 7px; border-radius:4px; font-family:monospace; font-size:.82rem; }
</style>
""", unsafe_allow_html=True)

# ── Bootstrap ──────────────────────────────────────────────────────────────────
init_db()
_providers = get_all_providers()

if "initial_ingest_done" not in st.session_state:
    st.session_state["initial_ingest_done"] = True
    try:
        ingest_all()
    except Exception as exc:
        st.sidebar.warning(f"Auto-ingest: {exc}")


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    for p in _providers:
        st.subheader(p.display_name)

        dir_key = f"{p.provider_id}_log_directory"
        cur_dir = get_setting(dir_key, "")
        new_dir = st.text_input(
            "Log Directory", value=cur_dir,
            key=f"logdir_{p.provider_id}",
            placeholder="Full path to log folder",
        )
        if new_dir != cur_dir:
            if new_dir == "" or os.path.isdir(new_dir):
                save_setting(dir_key, new_dir)
                st.rerun()
            else:
                st.error("Directory not found")

        if p.provider_id == "gemini":
            cur_key = get_setting("gemini_api_key", "")
            new_key = st.text_input(
                "API Key (token counting)", value=cur_key,
                type="password", key="sidebar_gemini_api_key",
            )
            if new_key != cur_key:
                save_setting("gemini_api_key", new_key)
                st.rerun()

        if p.provider_id == "claude-code":
            cur_akey = get_setting("anthropic_api_key", "")
            new_akey = st.text_input(
                "Anthropic API Key (AI rewrite)", value=cur_akey,
                type="password", key="sidebar_anthropic_api_key",
                help="Used by Prompt Auditor's AI compression. Falls back to ANTHROPIC_API_KEY env var.",
            )
            if new_akey != cur_akey:
                save_setting("anthropic_api_key", new_akey)
                st.rerun()

        with st.expander("💰 Pricing ($/1M tokens)"):
            if p.provider_id == "gemini":
                fi  = st.number_input("Flash In",  value=float(get_setting("gemini_flash_input_rate",  "0.075")), format="%.4f", key="gfi")
                fo  = st.number_input("Flash Out", value=float(get_setting("gemini_flash_output_rate", "0.30")),  format="%.4f", key="gfo")
                pi_ = st.number_input("Pro In",    value=float(get_setting("gemini_pro_input_rate",    "1.25")),  format="%.4f", key="gpi")
                po  = st.number_input("Pro Out",   value=float(get_setting("gemini_pro_output_rate",   "5.00")),  format="%.4f", key="gpo")
                if st.button("Save Gemini Rates", use_container_width=True, key="save_grates"):
                    for k, v in [("gemini_flash_input_rate", fi), ("gemini_flash_output_rate", fo),
                                  ("gemini_pro_input_rate", pi_), ("gemini_pro_output_rate", po)]:
                        save_setting(k, str(v))
                    st.success("Saved!")
            elif p.provider_id == "claude-code":
                hi = st.number_input("Haiku In",   value=float(get_setting("claude_haiku_input_rate",   "0.80")),  format="%.2f", key="chi")
                ho = st.number_input("Haiku Out",  value=float(get_setting("claude_haiku_output_rate",  "4.00")),  format="%.2f", key="cho")
                si = st.number_input("Sonnet In",  value=float(get_setting("claude_sonnet_input_rate",  "3.00")),  format="%.2f", key="csi")
                so = st.number_input("Sonnet Out", value=float(get_setting("claude_sonnet_output_rate", "15.00")), format="%.2f", key="cso")
                oi = st.number_input("Opus In",    value=float(get_setting("claude_opus_input_rate",    "15.00")), format="%.2f", key="coi")
                oo = st.number_input("Opus Out",   value=float(get_setting("claude_opus_output_rate",   "75.00")), format="%.2f", key="coo")
                if st.button("Save Claude Rates", use_container_width=True, key="save_crates"):
                    for k, v in [("claude_haiku_input_rate", hi), ("claude_haiku_output_rate", ho),
                                  ("claude_sonnet_input_rate", si), ("claude_sonnet_output_rate", so),
                                  ("claude_opus_input_rate", oi), ("claude_opus_output_rate", oo)]:
                        save_setting(k, str(v))
                    st.success("Saved!")
            elif p.provider_id == "codex":
                st.caption("Enter rates when OpenAI publishes Codex pricing.")
                dxi = st.number_input("GPT-5.5 In",      value=float(get_setting("codex_input_rate",      "0.0")), format="%.4f", key="dxi")
                dxo = st.number_input("GPT-5.5 Out",     value=float(get_setting("codex_output_rate",     "0.0")), format="%.4f", key="dxo")
                dmi = st.number_input("GPT-5.4-mini In",  value=float(get_setting("codex_mini_input_rate",  "0.0")), format="%.4f", key="dmi")
                dmo = st.number_input("GPT-5.4-mini Out", value=float(get_setting("codex_mini_output_rate", "0.0")), format="%.4f", key="dmo")
                if st.button("Save Codex Rates", use_container_width=True, key="save_dxrates"):
                    for k, v in [("codex_input_rate", dxi), ("codex_output_rate", dxo),
                                  ("codex_mini_input_rate", dmi), ("codex_mini_output_rate", dmo)]:
                        save_setting(k, str(v))
                    st.success("Saved!")
            elif p.provider_id == "devin":
                st.caption("Devin pricing is task-based; token rates TBD once log format is known.")
                dvi = st.number_input("In",  value=float(get_setting("devin_input_rate",  "0.0")), format="%.4f", key="dvi")
                dvo = st.number_input("Out", value=float(get_setting("devin_output_rate", "0.0")), format="%.4f", key="dvo")
                if st.button("Save Devin Rates", use_container_width=True, key="save_dvrates"):
                    for k, v in [("devin_input_rate", dvi), ("devin_output_rate", dvo)]:
                        save_setting(k, str(v))
                    st.success("Saved!")

        if st.button(f"🔄 Rescan {p.display_name}",
                     key=f"rescan_{p.provider_id}", use_container_width=True):
            with st.spinner(f"Scanning {p.display_name}…"):
                s, t = ingest_provider(p.provider_id)
            st.success(f"Done — {s} sessions, {t} turns")
            st.rerun()

        st.divider()

    if st.button("🔄 Rescan All", use_container_width=True,
                 type="primary", key="rescan_all"):
        with st.spinner("Scanning all providers…"):
            s, t = ingest_all()
        st.success(f"Done — {s} sessions, {t} turns total")
        st.rerun()


# ── Query helpers ──────────────────────────────────────────────────────────────
def _safe_int(val) -> int:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _q_totals(pid: str) -> dict:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS session_count,
                   COALESCE(SUM(turn_count), 0)          AS total_turns,
                   COALESCE(SUM(total_input_tokens), 0)  AS total_input,
                   COALESCE(SUM(total_output_tokens), 0) AS total_output,
                   COALESCE(SUM(total_cost), 0.0)        AS total_cost
            FROM sessions WHERE provider = ?
        """, (pid,)).fetchone()
    return dict(row)


def _q_daily_trends(pid: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("""
            SELECT date(created_at) AS date,
                   SUM(total_cost) AS daily_cost,
                   SUM(total_input_tokens + total_output_tokens) AS daily_tokens,
                   COUNT(*) AS daily_sessions
            FROM sessions
            WHERE provider = ? AND created_at != ''
            GROUP BY date ORDER BY date
        """, conn, params=(pid,))


def _q_sessions(pid: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("""
            SELECT session_id, title, model, turn_count,
                   total_input_tokens, total_output_tokens,
                   total_cost, efficiency_score, created_at
            FROM sessions WHERE provider = ?
            ORDER BY CASE WHEN created_at = '' THEN 1 ELSE 0 END, created_at DESC
        """, conn, params=(pid,))


def _q_session_detail(sid: str) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (sid,)).fetchone()
    return dict(row) if row else {}


def _q_turns(sid: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("""
            SELECT turn_id, sequence_index, role, raw_type, content, model,
                   input_tokens, output_tokens,
                   cache_creation_tokens, cache_read_tokens,
                   cost, created_at, is_dismissed
            FROM turns WHERE session_id = ?
            ORDER BY sequence_index ASC
        """, conn, params=(sid,))


def _has_data(pid: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE provider = ?", (pid,)
        ).fetchone()[0] > 0


# ── Sub-tab renderers ──────────────────────────────────────────────────────────

def _render_overview(pid: str):
    tot = _q_totals(pid)
    if tot["session_count"] == 0:
        st.markdown(
            '<div class="info-card">💡 No sessions yet. '
            'Set a log directory in the sidebar and click Rescan.</div>',
            unsafe_allow_html=True,
        )
        return

    total_tok = tot["total_input"] + tot["total_output"]
    st.markdown(f"""
    <div class="metric-grid">
      <div class="metric-box">
        <div class="metric-title">Sessions</div>
        <div class="metric-val">{tot['session_count']:,}</div>
        <div class="metric-sub">discovered</div>
      </div>
      <div class="metric-box">
        <div class="metric-title">Total Cost</div>
        <div class="metric-val">${tot['total_cost']:.4f}</div>
        <div class="metric-sub">USD aggregate</div>
      </div>
      <div class="metric-box">
        <div class="metric-title">Total Tokens</div>
        <div class="metric-val">{total_tok:,}</div>
        <div class="metric-sub">{tot['total_input']:,} in / {tot['total_output']:,} out</div>
      </div>
      <div class="metric-box">
        <div class="metric-title">Total Turns</div>
        <div class="metric-val">{tot['total_turns']:,}</div>
        <div class="metric-sub">conversation steps</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    df_t = _q_daily_trends(pid)
    if not df_t.empty:
        st.subheader("📅 Daily Activity")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_t["date"], y=df_t["daily_cost"],
            name="Daily Cost ($)", marker_color="#38bdf8", yaxis="y",
        ))
        fig.add_trace(go.Scatter(
            x=df_t["date"], y=df_t["daily_tokens"],
            name="Daily Tokens", line=dict(color="#f43f5e", width=2), yaxis="y2",
        ))
        for _, row in df_t.iterrows():
            fig.add_annotation(
                x=row["date"], y=row["daily_cost"],
                text=str(int(row["daily_sessions"])),
                showarrow=False, yshift=12,
                font=dict(size=10, color="#94a3b8"),
                yref="y",
            )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Date"),
            yaxis=dict(title="Cost (USD)", titlefont=dict(color="#38bdf8"),
                       tickfont=dict(color="#38bdf8")),
            yaxis2=dict(title="Tokens", titlefont=dict(color="#f43f5e"),
                        tickfont=dict(color="#f43f5e"), overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99),
            margin=dict(l=40, r=40, t=20, b=40), height=280,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📂 Sessions")
    df_s = _q_sessions(pid)
    if not df_s.empty:
        disp = df_s[["title", "model", "turn_count", "total_cost",
                      "total_input_tokens", "total_output_tokens",
                      "efficiency_score", "created_at"]].copy()
        disp.columns = ["Title", "Model", "Turns", "Cost ($)",
                         "Input Tok", "Output Tok", "Efficiency %", "Created"]
        disp["Cost ($)"]     = disp["Cost ($)"].map(lambda v: f"${v:.4f}")
        disp["Efficiency %"] = disp["Efficiency %"].map(lambda v: f"{v:.1f}%")
        disp["Input Tok"]    = disp["Input Tok"].map(lambda v: f"{int(v):,}")
        disp["Output Tok"]   = disp["Output Tok"].map(lambda v: f"{int(v):,}")
        st.dataframe(disp, use_container_width=True, hide_index=True)


def _render_explorer(pid: str, capabilities: set):
    df_s = _q_sessions(pid)
    if df_s.empty:
        st.info("No sessions found. Configure and rescan in the sidebar.")
        return

    options = {
        f"{r['title']} ({r['session_id'][:8]}…)": r["session_id"]
        for _, r in df_s.iterrows()
    }
    sel = st.selectbox("Session", list(options.keys()), key=f"exp_sel_{pid}")
    sid = options[sel]

    detail  = _q_session_detail(sid)
    df_turns = _q_turns(sid)

    if df_turns.empty:
        st.warning("No turns found for this session.")
        return

    # Metrics row
    c1, c2, c3, c4 = st.columns(4)
    tot_in   = _safe_int(detail.get("total_input_tokens"))
    tot_out  = _safe_int(detail.get("total_output_tokens"))
    tot_cost = float(detail.get("total_cost") or 0.0)
    score    = float(detail.get("efficiency_score") or 0.0)

    c1.metric("Cost", f"${tot_cost:.5f}")
    c2.metric("Tokens", f"{tot_in + tot_out:,}",
              f"{tot_in:,} in / {tot_out:,} out", delta_color="off")
    c3.metric("Turns", _safe_int(detail.get("turn_count")) or len(df_turns))
    score_label = (
        f"🟢 {score:.1f}% High"     if score >= 15.0 else
        f"🟡 {score:.1f}% Moderate" if score >= 5.0  else
        f"🔴 {score:.1f}% Low"
    )
    c4.metric("Efficiency", score_label)

    # Context accumulation chart
    df_asst = df_turns[df_turns["role"] == "assistant"].copy()
    if not df_asst.empty and df_asst["input_tokens"].fillna(0).sum() > 0:
        st.subheader("📈 Context Growth")
        fig_ctx = go.Figure()
        fig_ctx.add_trace(go.Scatter(
            x=df_asst["sequence_index"],
            y=df_asst["input_tokens"].fillna(0),
            mode="lines+markers",
            name="Input tokens (context window)",
            line=dict(color="#38bdf8", width=2), marker=dict(size=5),
        ))
        if "cache_tokens" in capabilities:
            cr = df_asst["cache_read_tokens"].fillna(0)
            if cr.sum() > 0:
                fig_ctx.add_trace(go.Scatter(
                    x=df_asst["sequence_index"], y=cr,
                    mode="lines", name="Cache read tokens",
                    line=dict(color="#22c55e", width=1, dash="dot"),
                ))
        fig_ctx.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Turn index"),
            yaxis=dict(title="Tokens"),
            margin=dict(l=40, r=40, t=20, b=40), height=240,
        )
        st.plotly_chart(fig_ctx, use_container_width=True)

    # Transcript
    st.subheader("💬 Transcript")
    for _, turn in df_turns.iterrows():
        role     = turn["role"] or "user"
        content  = turn["content"] or ""
        in_tok   = _safe_int(turn["input_tokens"])
        out_tok  = _safe_int(turn["output_tokens"])
        cost_val = float(turn["cost"] or 0.0)
        model    = turn["model"] or ""
        idx      = _safe_int(turn["sequence_index"])
        ts       = turn["created_at"] or ""
        cc_val   = _safe_int(turn["cache_creation_tokens"])
        cr_val   = _safe_int(turn["cache_read_tokens"])

        if role == "assistant":
            msg_role = "assistant"
            label = "🤖 Assistant" + (f" · {model}" if model else "")
        elif role == "system":
            msg_role = "assistant"
            label = "⚙️ System"
        else:
            msg_role = "user"
            label = "👤 User"

        with st.chat_message(msg_role):
            header = f"**{label}** &nbsp;·&nbsp; Turn {idx}"
            if ts:
                header += f" &nbsp;·&nbsp; {ts}"
            st.markdown(header)
            st.text(content)

            if in_tok > 0 or out_tok > 0:
                cache_part = ""
                if cc_val > 0:
                    cache_part += f" │ cache_write: {cc_val:,}"
                if cr_val > 0:
                    cache_part += f" │ cache_read: {cr_val:,}"
                st.markdown(
                    f"<span class='tok-badge'>"
                    f"in: {in_tok:,} │ out: {out_tok:,}{cache_part} │ ${cost_val:.5f}"
                    f"</span>",
                    unsafe_allow_html=True,
                )

            if content and role == "user":
                p_hits = detect_pleasantries(content)
                if p_hits:
                    st.markdown(
                        f'<div class="warning-card">⚠️ <b>Pleasantry match:</b> '
                        f'{", ".join(repr(ph) for ph in p_hits)}</div>',
                        unsafe_allow_html=True,
                    )

            if role == "assistant" and in_tok > 0:
                debt = check_context_debt(in_tok, out_tok)
                if debt["debt_heavy"]:
                    st.markdown(
                        f'<div class="warning-card">💡 <b>Context debt:</b> {debt["message"]}</div>',
                        unsafe_allow_html=True,
                    )


_HIGH_COST_THRESHOLD = 0.05  # USD; turns above this are flagged as high-cost


def _render_advice(pid: str):
    with get_connection() as conn:
        user_rows = conn.execute("""
            SELECT t.turn_id, t.session_id, t.sequence_index,
                   t.content, t.cost, t.created_at, s.title
            FROM turns t JOIN sessions s ON t.session_id = s.session_id
            WHERE t.provider = ? AND t.role = 'user' AND t.is_dismissed = 0
            ORDER BY t.created_at DESC
        """, (pid,)).fetchall()

        debt_rows = conn.execute("""
            SELECT t.turn_id, t.session_id, t.sequence_index,
                   t.content, t.input_tokens, t.output_tokens, t.cost,
                   t.created_at, s.title
            FROM turns t JOIN sessions s ON t.session_id = s.session_id
            WHERE t.provider = ? AND t.role = 'assistant' AND t.is_dismissed = 0
              AND (t.input_tokens > 40000
                   OR (t.input_tokens > 8000
                       AND CAST(t.input_tokens AS REAL) / MAX(1, t.output_tokens) > 15.0))
            ORDER BY t.input_tokens DESC
        """, (pid,)).fetchall()

        cost_rows = conn.execute("""
            SELECT t.turn_id, t.session_id, t.sequence_index,
                   t.content, t.input_tokens, t.output_tokens, t.cost,
                   t.model, t.created_at, s.title
            FROM turns t JOIN sessions s ON t.session_id = s.session_id
            WHERE t.provider = ? AND t.is_dismissed = 0
              AND t.cost > ?
            ORDER BY t.cost DESC
            LIMIT 20
        """, (pid, _HIGH_COST_THRESHOLD)).fetchall()

    items = []
    for row in user_rows:
        hits = detect_pleasantries(row["content"])
        if hits:
            items.append({**dict(row), "type": "pleasantry", "pleasantries": hits})

    for row in debt_rows:
        debt = check_context_debt(row["input_tokens"], row["output_tokens"])
        if debt["debt_heavy"]:
            items.append({**dict(row), "type": "context_debt", "debt": debt})

    seen_ids = {item["turn_id"] for item in items}
    for row in cost_rows:
        if row["turn_id"] not in seen_ids:
            items.append({**dict(row), "type": "high_cost"})
            seen_ids.add(row["turn_id"])

    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Summary header
    n_plea  = sum(1 for i in items if i["type"] == "pleasantry")
    n_debt  = sum(1 for i in items if i["type"] == "context_debt")
    n_cost  = sum(1 for i in items if i["type"] == "high_cost")
    pot_cost = sum(i.get("cost", 0.0) for i in items if i["type"] == "high_cost")

    if not items:
        st.markdown(
            '<div class="success-card">✅ <b>All clear.</b> '
            'No pleasantry matches, context debt, or high-cost turns found.</div>',
            unsafe_allow_html=True,
        )
        return

    summary_parts = []
    if n_plea: summary_parts.append(f"⚠️ {n_plea} pleasantry")
    if n_debt: summary_parts.append(f"🚨 {n_debt} context-debt")
    if n_cost: summary_parts.append(f"💸 {n_cost} high-cost (${pot_cost:.2f} total)")
    st.markdown(
        f'<div class="warning-card"><b>{len(items)} optimization opportunities</b> &nbsp;·&nbsp; '
        f'{" &nbsp;·&nbsp; ".join(summary_parts)}</div>',
        unsafe_allow_html=True,
    )

    for item in items:
        st.divider()
        col_h, col_btn = st.columns([5, 1])

        with col_h:
            st.markdown(f"**{item['title']}** &nbsp;·&nbsp; Turn {item['sequence_index']}")

            if item["type"] == "pleasantry":
                phrases = ", ".join(f'"{p}"' for p in item["pleasantries"])
                st.markdown(
                    f'<span style="background:#272111;color:#f59e0b;padding:2px 8px;'
                    f'border-radius:4px;font-size:.8rem;font-weight:600;">⚠️ PLEASANTRY</span>'
                    f'&nbsp; {phrases}',
                    unsafe_allow_html=True,
                )
            elif item["type"] == "context_debt":
                in_t  = item["input_tokens"]
                out_t = item["output_tokens"]
                ratio = in_t / max(1, out_t)
                st.markdown(
                    f'<span style="background:#2e100a;color:#f43f5e;padding:2px 8px;'
                    f'border-radius:4px;font-size:.8rem;font-weight:600;">'
                    f'🚨 CONTEXT DEBT {ratio:.1f}x</span>'
                    f'&nbsp; {in_t:,} in → {out_t:,} out &nbsp; ${item["cost"]:.5f}',
                    unsafe_allow_html=True,
                )
            else:
                in_t  = item.get("input_tokens", 0) or 0
                out_t = item.get("output_tokens", 0) or 0
                model = item.get("model", "") or ""
                st.markdown(
                    f'<span style="background:#1a0a2e;color:#c084fc;padding:2px 8px;'
                    f'border-radius:4px;font-size:.8rem;font-weight:600;">'
                    f'💸 HIGH COST ${item["cost"]:.4f}</span>'
                    f'&nbsp; {in_t:,} in · {out_t:,} out'
                    + (f' &nbsp;·&nbsp; {model}' if model else ''),
                    unsafe_allow_html=True,
                )

            snippet = item["content"][:400] + ("…" if len(item["content"]) > 400 else "")
            st.code(snippet, wrap_lines=True)

        with col_btn:
            if st.button("Dismiss", key=f"dismiss_{item['turn_id']}", use_container_width=True):
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE turns SET is_dismissed = 1 WHERE turn_id = ?",
                        (item["turn_id"],),
                    )
                st.rerun()


def _compress_with_llm(provider, prompt: str) -> tuple[str, int]:
    """Calls the provider's LLM to compress a prompt. Returns (rewritten, token_count)."""
    instruction = (
        "Compress the following prompt to reduce its token count while fully preserving "
        "all intent, requirements, and context. Return ONLY the rewritten prompt — "
        "no explanations or commentary."
    )
    full_input = f"{instruction}\n\n{prompt}"

    if provider.provider_id in ("claude-code", "codex"):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        api_key = get_setting("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "No Anthropic API key found. Add it in the sidebar under Claude Code "
                "settings, or set the ANTHROPIC_API_KEY environment variable."
            )
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": full_input}],
        )
        rewritten = msg.content[0].text.strip()

    elif provider.provider_id == "gemini":
        import google.generativeai as genai
        api_key = get_setting("gemini_api_key", "")
        if not api_key:
            raise RuntimeError("No Gemini API key found. Add it in the sidebar.")
        genai.configure(api_key=api_key)
        model_obj = genai.GenerativeModel("gemini-1.5-flash")
        response = model_obj.generate_content(full_input)
        rewritten = response.text.strip()

    else:
        raise ValueError(f"LLM compression not available for {provider.display_name}")

    return rewritten, provider.count_tokens(rewritten)


def _render_auditor(provider):
    st.markdown(
        "Paste any prompt to estimate its token cost and check for low-value phrases."
    )
    prompt = st.text_area(
        "Prompt", height=160,
        placeholder="Type or paste your prompt here…",
        key=f"auditor_{provider.provider_id}",
    )
    if not prompt:
        return

    token_count  = provider.count_tokens(prompt)
    pleasantries = detect_pleasantries(prompt)

    c1, c2 = st.columns(2)
    c1.metric("Estimated Tokens", f"{token_count:,}")

    if pleasantries:
        c2.error(f"⚠️ {len(pleasantries)} pleasantry phrase(s) found")
        st.markdown(f"**Matched:** {', '.join(pleasantries)}")
    else:
        c2.success("✅ No pleasantries detected")

    rate     = provider.get_pricing("")
    in_cost  = token_count * rate.input_rate  / 1_000_000
    out_cost = token_count * rate.output_rate / 1_000_000
    st.caption(
        f"At {provider.display_name} default rate — "
        f"as input: **${in_cost:.5f}** · as output: **${out_cost:.5f}**"
    )

    st.divider()
    col_btn, col_cap = st.columns([1, 4])
    with col_btn:
        rewrite_clicked = st.button(
            "✨ Compress with AI",
            key=f"rewrite_btn_{provider.provider_id}",
            use_container_width=True,
        )
    with col_cap:
        lbl = "claude-haiku-4-5-20251001" if provider.provider_id == "claude-code" else "gemini-1.5-flash"
        st.caption(f"Rewrites your prompt using **{lbl}** to minimize tokens while preserving intent.")

    rw_key = f"rewrite_{provider.provider_id}"
    if rewrite_clicked:
        with st.spinner("Compressing prompt…"):
            try:
                rewritten, new_count = _compress_with_llm(provider, prompt)
                st.session_state[rw_key] = {
                    "rewritten": rewritten,
                    "orig_count": token_count,
                    "new_count": new_count,
                    "source_prompt": prompt,
                }
            except Exception as exc:
                st.error(str(exc))

    rw = st.session_state.get(rw_key)
    if rw and rw.get("source_prompt") == prompt:
        orig  = rw["orig_count"]
        new_c = rw["new_count"]
        saved = orig - new_c
        pct   = saved / max(1, orig) * 100
        st.subheader("✅ Compressed Prompt")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Original Tokens", f"{orig:,}")
        cc2.metric("Compressed Tokens", f"{new_c:,}",
                   delta=f"-{saved:,}" if saved >= 0 else f"+{-saved:,}",
                   delta_color="inverse")
        cc3.metric("Token Savings", f"{pct:.1f}%")
        st.text_area(
            "Rewritten prompt:",
            value=rw["rewritten"],
            height=200,
            key=f"rewrite_result_{provider.provider_id}",
        )


# ── Compare tab ───────────────────────────────────────────────────────────────

_PROVIDER_COLORS = ["#38bdf8", "#f43f5e", "#a3e635", "#fb923c"]


def _render_compare(providers: list):
    """Cross-provider comparison — metrics only, no session content."""

    totals  = {p.provider_id: _q_totals(p.provider_id) for p in providers}
    labels  = [p.display_name for p in providers]
    colors  = _PROVIDER_COLORS[:len(providers)]

    # ── Summary table ──────────────────────────────────────────────────────────
    st.subheader("📊 At a Glance")
    rows = []
    for p in providers:
        t = totals[p.provider_id]
        tok = t["total_input"] + t["total_output"]
        rows.append({
            "Provider":          p.display_name,
            "Sessions":          f"{t['session_count']:,}",
            "Total Cost":        f"${t['total_cost']:.2f}",
            "Total Tokens":      f"{tok:,}",
            "Turns":             f"{t['total_turns']:,}",
            "Avg Cost / Session":f"${t['total_cost'] / max(1, t['session_count']):.2f}",
            "Output Ratio":      f"{t['total_output'] / max(1, t['total_input']) * 100:.1f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Cost vs Token Volume ───────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("💰 Total Spend")
        fig_cost = go.Figure(go.Bar(
            x=labels,
            y=[totals[p.provider_id]["total_cost"] for p in providers],
            marker_color=colors,
            text=[f"${totals[p.provider_id]['total_cost']:.2f}" for p in providers],
            textposition="outside",
        ))
        fig_cost.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="USD"),
            showlegend=False,
            margin=dict(l=40, r=40, t=10, b=40), height=280,
        )
        st.plotly_chart(fig_cost, use_container_width=True)

    with col_b:
        st.subheader("🔢 Token Volume")
        fig_tok = go.Figure()
        for p, color in zip(providers, colors):
            t = totals[p.provider_id]
            fig_tok.add_trace(go.Bar(
                name=p.display_name,
                x=["Input", "Output"],
                y=[t["total_input"], t["total_output"]],
                marker_color=color,
            ))
        fig_tok.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            barmode="group",
            yaxis=dict(title="Tokens"),
            legend=dict(x=0.01, y=0.99),
            margin=dict(l=40, r=40, t=10, b=40), height=280,
        )
        st.plotly_chart(fig_tok, use_container_width=True)

    # ── Daily Cost Overlay ─────────────────────────────────────────────────────
    st.subheader("📅 Daily Cost Trends")
    fig_trend = go.Figure()
    any_trend = False
    for p, color in zip(providers, colors):
        df_t = _q_daily_trends(p.provider_id)
        if not df_t.empty:
            any_trend = True
            fig_trend.add_trace(go.Scatter(
                x=df_t["date"], y=df_t["daily_cost"],
                name=p.display_name,
                mode="lines+markers",
                line=dict(color=color, width=2),
                marker=dict(size=5),
            ))
    if any_trend:
        fig_trend.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Date"),
            yaxis=dict(title="Daily Cost (USD)"),
            legend=dict(x=0.01, y=0.99),
            margin=dict(l=40, r=40, t=10, b=40), height=300,
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No daily trend data available.")

    # ── Efficiency Leaderboard ─────────────────────────────────────────────────
    st.subheader("🏆 Efficiency Leaderboard")
    eff_rows = []
    for p in providers:
        t = totals[p.provider_id]
        out_ratio  = t["total_output"] / max(1, t["total_input"]) * 100
        cost_per_k = t["total_cost"] / max(1, t["total_output"]) * 1_000
        cost_p_ses = t["total_cost"] / max(1, t["session_count"])
        cost_p_trn = t["total_cost"] / max(1, t["total_turns"])
        eff_rows.append({
            "Provider":              p.display_name,
            "Output/Input %":        f"{out_ratio:.2f}%",
            "Cost / 1K Out Tokens":  f"${cost_per_k:.4f}",
            "Avg Cost / Session":    f"${cost_p_ses:.2f}",
            "Avg Cost / Turn":       f"${cost_p_trn:.5f}",
        })
    st.dataframe(pd.DataFrame(eff_rows), use_container_width=True, hide_index=True)

    # Cost per 1K output tokens — bar chart
    fig_eff = go.Figure(go.Bar(
        x=labels,
        y=[totals[p.provider_id]["total_cost"] / max(1, totals[p.provider_id]["total_output"]) * 1_000
           for p in providers],
        marker_color=colors,
        text=[f"${totals[p.provider_id]['total_cost'] / max(1, totals[p.provider_id]['total_output']) * 1_000:.4f}"
              for p in providers],
        textposition="outside",
    ))
    fig_eff.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="USD per 1K output tokens"),
        showlegend=False,
        margin=dict(l=40, r=40, t=10, b=40), height=240,
        annotations=[dict(
            text="Lower = more cost-efficient",
            x=0.5, y=1.05, xref="paper", yref="paper",
            showarrow=False, font=dict(size=11, color="#94a3b8"),
        )],
    )
    st.plotly_chart(fig_eff, use_container_width=True)

    # ── Spend & Session Distribution ───────────────────────────────────────────
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.subheader("🗂 Sessions by Provider")
        fig_s_pie = go.Figure(go.Pie(
            labels=labels,
            values=[totals[p.provider_id]["session_count"] for p in providers],
            marker=dict(colors=colors),
            hole=0.45,
            textinfo="label+percent",
        ))
        fig_s_pie.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10), height=260,
        )
        st.plotly_chart(fig_s_pie, use_container_width=True)

    with col_p2:
        st.subheader("💸 Spend by Provider")
        fig_c_pie = go.Figure(go.Pie(
            labels=labels,
            values=[totals[p.provider_id]["total_cost"] for p in providers],
            marker=dict(colors=colors),
            hole=0.45,
            textinfo="label+percent",
        ))
        fig_c_pie.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10), height=260,
        )
        st.plotly_chart(fig_c_pie, use_container_width=True)


# ── Main layout ────────────────────────────────────────────────────────────────
st.title("📊 AI Usage Dashboard")
st.caption("Multi-provider AI log analysis — token usage, cost, and prompt efficiency.")

_visible = [
    p for p in _providers
    if get_setting(f"{p.provider_id}_log_directory", "") or _has_data(p.provider_id)
]

if not _visible:
    st.markdown(
        '<div class="info-card">👈 No providers configured yet. '
        'Set a log directory for each provider in the sidebar to get started.</div>',
        unsafe_allow_html=True,
    )
else:
    _with_data   = [p for p in _visible if _has_data(p.provider_id)]
    _has_compare = len(_with_data) >= 2
    _tab_labels  = [p.display_name for p in _visible] + (["⚖️ Compare"] if _has_compare else [])
    root_tabs    = st.tabs(_tab_labels)

    for tab, provider in zip(root_tabs, _visible):
        with tab:
            ov, ex, adv, aud = st.tabs([
                "📈 Overview",
                "💬 Session Explorer",
                "💡 Advice",
                "🔍 Prompt Auditor",
            ])
            with ov:
                _render_overview(provider.provider_id)
            with ex:
                _render_explorer(provider.provider_id, provider.capabilities)
            with adv:
                _render_advice(provider.provider_id)
            with aud:
                _render_auditor(provider)

    if _has_compare:
        with root_tabs[-1]:
            _render_compare(_with_data)
