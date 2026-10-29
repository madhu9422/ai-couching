"""Visual theme: CSS plus small HTML helpers for a professional dashboard look."""
import html

import streamlit as st

CREATOR = "Madhu"  # shown in the footer; change the name here

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', 'Segoe UI', sans-serif; }

/* ---------- background ---------- */
.stApp {
  background:
    radial-gradient(1100px 560px at 8% -8%, rgba(99,102,241,.28), transparent 60%),
    radial-gradient(900px 520px at 100% 0%, rgba(14,165,233,.20), transparent 55%),
    radial-gradient(800px 500px at 50% 110%, rgba(168,85,247,.14), transparent 60%),
    linear-gradient(180deg, #0B1020 0%, #0D1430 100%);
  background-attachment: fixed;
}
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1200px; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #111A3A 0%, #0B1020 100%);
  border-right: 1px solid rgba(255,255,255,.07);
}
.brand { display:flex; gap:12px; align-items:center; padding:6px 4px 18px; }
.brand .logo { width:42px; height:42px; border-radius:12px; display:grid; place-items:center; font-size:22px;
  background: linear-gradient(135deg,#6C8CFF,#A855F7); box-shadow: 0 6px 18px rgba(108,140,255,.45); }
.brand b { display:block; font-size:1.05rem; letter-spacing:.2px; }
.brand small { color:#8F9BC4; font-size:.75rem; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  padding: 9px 12px; border-radius: 10px; transition: background .15s ease; width: 100%;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(255,255,255,.06); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(108,140,255,.30), rgba(108,140,255,.08));
  box-shadow: inset 3px 0 0 #6C8CFF;
}

/* ---------- hero & headers ---------- */
.hero { padding: 38px 40px; border-radius: 22px; margin-bottom: 22px; position: relative; overflow: hidden;
  background: linear-gradient(135deg, rgba(108,140,255,.28), rgba(168,85,247,.20) 55%, rgba(14,165,233,.18));
  border: 1px solid rgba(255,255,255,.12); box-shadow: 0 20px 50px rgba(0,0,0,.35); }
.hero::after { content:""; position:absolute; right:-60px; top:-60px; width:260px; height:260px; border-radius:50%;
  background: radial-gradient(circle, rgba(255,255,255,.14), transparent 70%); }
.hero .badge { display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:1.4px; padding:5px 12px;
  border-radius:999px; background: rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18); margin-bottom:14px; }
.hero h1 { font-size: 2.3rem; line-height:1.15; margin:0 0 10px; font-weight:800; letter-spacing:-.5px; }
.hero p { color:#C9D2F0; font-size:1.05rem; max-width: 720px; margin:0; }

.page-head { margin-bottom: 18px; }
.page-head h2 { margin:0; font-size:1.75rem; font-weight:800; letter-spacing:-.3px; }
.page-head p { margin:4px 0 0; color:#9AA6CF; }

/* ---------- cards ---------- */
.card { background: rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.09); border-radius:18px;
  padding:20px 22px; box-shadow: 0 10px 30px rgba(0,0,0,.28); backdrop-filter: blur(8px); margin-bottom: 14px; }
.card h4 { margin:0 0 6px; font-size:.78rem; text-transform:uppercase; letter-spacing:1.2px; color:#8F9BC4; font-weight:700; }
.card .step { width:34px; height:34px; border-radius:10px; display:grid; place-items:center; font-weight:800;
  background: linear-gradient(135deg,#6C8CFF,#A855F7); margin-bottom:12px; }
.card .title { font-weight:700; font-size:1.05rem; margin-bottom:4px; }
.card .muted { color:#9AA6CF; font-size:.92rem; }

.kpi { display:flex; gap:14px; align-items:center; background: rgba(255,255,255,.045);
  border:1px solid rgba(255,255,255,.09); border-radius:18px; padding:18px 20px;
  box-shadow: 0 10px 30px rgba(0,0,0,.28); }
.kpi .icon { width:46px; height:46px; border-radius:14px; display:grid; place-items:center; font-size:22px;
  background: color-mix(in srgb, var(--accent) 22%, transparent); border:1px solid color-mix(in srgb, var(--accent) 45%, transparent); }
.kpi .label { color:#8F9BC4; font-size:.78rem; text-transform:uppercase; letter-spacing:1px; font-weight:600; }
.kpi .value { font-size:1.7rem; font-weight:800; line-height:1.15; }

.ring-wrap { display:flex; align-items:center; gap:22px; min-height:150px; }
.ring { --p:0; position:relative; width:128px; height:128px; border-radius:50%; flex:none; display:grid; place-items:center;
  background: conic-gradient(#6C8CFF calc(var(--p) * 1%), #A855F7 calc(var(--p) * 1%) 0, rgba(255,255,255,.09) 0); }
.ring::after { content:""; position:absolute; inset:11px; border-radius:50%; background:#10173A; }
.ring span { position:relative; z-index:1; font-size:1.6rem; font-weight:800; }

.next-card { border-left: 4px solid var(--accent, #6C8CFF); min-height:150px; display:flex; flex-direction:column; justify-content:center; }
.next-card .msg { font-size:1.15rem; font-weight:600; line-height:1.4; }

/* ---------- chips ---------- */
.chip { display:inline-block; padding:3px 11px; border-radius:999px; font-size:.75rem; font-weight:600; border:1px solid transparent; }
.chip.pending { color:#B6BFDD; background:rgba(182,191,221,.12); border-color:rgba(182,191,221,.25); }
.chip.in_progress { color:#FBBF24; background:rgba(251,191,36,.12); border-color:rgba(251,191,36,.30); }
.chip.completed { color:#34D399; background:rgba(52,211,153,.12); border-color:rgba(52,211,153,.30); }
.chip.needs_revision { color:#F87171; background:rgba(248,113,113,.12); border-color:rgba(248,113,113,.30); }
.chip.info { color:#9DB4FF; background:rgba(108,140,255,.14); border-color:rgba(108,140,255,.32); margin-right:6px; }

/* ---------- roadmap rows ---------- */
.row { display:flex; align-items:center; gap:16px; padding:14px 18px; border-radius:14px; margin-bottom:10px;
  background: rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); }
.row .day { width:46px; height:46px; border-radius:12px; flex:none; display:grid; place-items:center; font-weight:800;
  background: rgba(108,140,255,.16); border:1px solid rgba(108,140,255,.35); color:#BFD0FF; font-size:.85rem; }
.row .info { flex:1; min-width:0; }
.row .name { font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.row .meta { color:#8F9BC4; font-size:.8rem; margin-top:2px; }
.row .score { width:150px; flex:none; text-align:right; }
.row .score b { font-size:.95rem; }
.bar { height:7px; border-radius:99px; background:rgba(255,255,255,.09); margin-top:6px; overflow:hidden; }
.bar > div { height:100%; border-radius:99px; background: linear-gradient(90deg,#6C8CFF,#A855F7); }

/* ---------- native widgets ---------- */
.stButton > button, .stFormSubmitButton > button { border-radius: 12px; font-weight:600; padding:.55rem 1.1rem;
  border:1px solid rgba(255,255,255,.14); transition: transform .12s ease, box-shadow .12s ease; }
.stButton > button:hover, .stFormSubmitButton > button:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(108,140,255,.28); }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(135deg,#6C8CFF,#8B5CF6); border:none; color:#fff; }
[data-testid="stForm"] { background: rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.09);
  border-radius:18px; padding:22px; }
[data-testid="stExpander"] { background: rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.09) !important;
  border-radius:14px; }
[data-testid="stAlert"] { border-radius:14px; }
[data-testid="stDataFrame"] { border-radius:14px; overflow:hidden; border:1px solid rgba(255,255,255,.09); }
input, textarea, [data-baseweb="select"] > div { border-radius:10px !important; }
h3 { font-weight:700; letter-spacing:-.2px; }

/* ---------- footer / credit ---------- */
.app-footer { margin-top: 56px; padding: 18px 0 6px; text-align:center; color:#8F9BC4; font-size:.85rem;
  border-top: 1px solid rgba(255,255,255,.08); }
.app-footer b { background: linear-gradient(90deg,#6C8CFF,#A855F7); -webkit-background-clip:text;
  background-clip:text; color:transparent; font-weight:800; }
.sidebar-credit { margin-top: 28px; padding: 12px 14px; border-radius: 12px; font-size:.8rem; color:#8F9BC4;
  background: rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); text-align:center; }
.sidebar-credit b { color:#E8ECF8; }
[class*="st-key-codebox"] textarea { font-family: 'JetBrains Mono','Cascadia Code',Consolas,monospace !important;
  font-size:.9rem; line-height:1.55; background:#0A0F24 !important; border:1px solid rgba(108,140,255,.35) !important; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


def _html(s: str) -> str:
    # Markdown ends an HTML block at a blank line and treats 4-space indents as code, so flatten.
    return "".join(line.strip() for line in s.splitlines())


def render(s: str):
    st.markdown(_html(s), unsafe_allow_html=True)


def brand():
    render('<div class="brand"><div class="logo">🎓</div><div><b>Learning Coach</b>'
           '<small>AI personalised study</small></div></div>')


def hero(badge, title, text):
    render(f'<div class="hero"><span class="badge">{esc(badge)}</span><h1>{esc(title)}</h1><p>{esc(text)}</p></div>')


def page_header(title, subtitle=""):
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    render(f'<div class="page-head"><h2>{esc(title)}</h2>{sub}</div>')


def info_card(step, title, text):
    render(f'<div class="card"><div class="step">{esc(step)}</div><div class="title">{esc(title)}</div>'
           f'<div class="muted">{esc(text)}</div></div>')


def kpi(icon, label, value, accent="#6C8CFF") -> str:
    return _html(f'<div class="kpi" style="--accent:{accent}"><div class="icon">{icon}</div>'
                 f'<div><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div></div></div>')


def chips(items):
    render("".join(f'<span class="chip info">{esc(i)}</span>' for i in items) + "<br><br>")


def ring_card(percent, caption):
    p = max(0, min(100, round(percent)))
    return _html(f'<div class="card"><h4>Overall progress</h4><div class="ring-wrap">'
                 f'<div class="ring" style="--p:{p}"><span>{p}%</span></div>'
                 f'<div><div class="title">{esc(caption)}</div>'
                 f'<div class="muted">Topics reach "completed" when a quiz score is 80% or higher.</div></div>'
                 f'</div></div>')


ACCENT = {"revise": "#F87171", "continue": "#6C8CFF", "done": "#34D399", "none": "#6C8CFF"}


def next_card(kind, message):
    return _html(f'<div class="card next-card" style="--accent:{ACCENT.get(kind, "#6C8CFF")}">'
                 f'<h4>Recommended next step</h4><div class="msg">{esc(message)}</div></div>')


def status_chip(status, label):
    return f'<span class="chip {esc(status)}">{esc(label)}</span>'


def topic_row(t, label):
    last = t["last_score"]
    pct = f"{last:.0f}%" if last is not None else "No quiz yet"
    width = f"{last:.0f}" if last is not None else "0"
    return (f'<div class="row"><div class="day">D{esc(t["day"])}</div>'
            f'<div class="info"><div class="name">{esc(t["title"])}</div>'
            f'<div class="meta">{esc(t["estimated_minutes"])} min · {esc(t["attempts"])} attempt(s)</div></div>'
            f'{status_chip(t["status"], label)}'
            f'<div class="score"><b>{pct}</b><div class="bar"><div style="width:{width}%"></div></div></div></div>')


def footer():
    render(f'<div class="app-footer">AI Personalized Learning Coach &nbsp;·&nbsp; Created by <b>{esc(CREATOR)}</b> 🎓</div>')


def sidebar_credit():
    render(f'<div class="sidebar-credit">Created by <b>{esc(CREATOR)}</b></div>')
