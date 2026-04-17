#!/usr/bin/env python3
"""
Rose Mapper  —  Aeronautical Wind Analytics
WEB by ABDUL ALEEM | Run: python windrose_redesign.py
"""
import sys, subprocess, io, time

def _in_streamlit():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False

if __name__ == "__main__" and not _in_streamlit():
    DEPS = [("streamlit","streamlit"),("matplotlib","matplotlib"),
            ("numpy","numpy"),("pandas","pandas"),
            ("reportlab","reportlab"),("openpyxl","openpyxl"),("Pillow","PIL")]
    print("\n  Rose Mapper  —  Wind Rose Generator\n  " + "─"*40)
    for pkg, mod in DEPS:
        try: __import__(mod)
        except ImportError:
            print(f"  Installing {pkg}...")
            subprocess.check_call(
                [sys.executable,"-m","pip","install",pkg,"-q","--disable-pip-version-check"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  Launching ->  http://localhost:8501\n")
    subprocess.run([sys.executable,"-m","streamlit","run",__file__,
        "--server.port=8501","--server.headless=false",
        "--browser.gatherUsageStats=false"])
    sys.exit(0)

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as RC
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Image as RLImage, PageBreak, HRFlowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

st.set_page_config(page_title="Rose Mapper | Analytics", page_icon="🧭",
                   layout="wide", initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════
#  CONSTANTS & THEME DICTIONARY
# ══════════════════════════════════════════════════════════════════════
DIRS_16    = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
              "S","SSW","SW","WSW","W","WNW","NW","NNW"]
C2D        = {d: i*22.5 for i,d in enumerate(DIRS_16)}
SPD_BINS   = [-0.001, 0.97, 4.08, 7.00, 11.08, 17.11, 21.58, 9999]
SPD_LABELS = ["<0.97","0.97-4.08","4.08-7.00","7.00-11.08","11.08-17.11","17.11-21.58",">=21.58"]
TBL_COLS   = ["0.97-4.08","4.08-7.00","7.00-11.08","11.08-17.11","17.11-21.58",">=21.58"]
TBL_IDX    = [1,2,3,4,5,6]

T2_COLORS  = ["#e2e8f0","#bbf7d0","#fef08a","#f87171","#60a5fa","#22c55e","#06b6d4"]
T2_NAMES   = ["< 0.97 (Calms)","0.97-4.08","4.08-7.00","7.00-11.08","11.08-17.11","17.11-21.58",">= 21.58"]

TH = {
    "dark": {
        "bg":"#0f172a", "card":"rgba(30,41,59,0.75)", "brd":"rgba(148,163,184,0.15)", "brd2":"rgba(255,255,255,0.05)",
        "txt":"#f8fafc", "mut":"#94a3b8", "acc":"#3b82f6", "acc2":"#06b6d4",
        "suc":"#10b981", "dng":"#f43f5e", "gold":"#f59e0b",
        "ibg":"rgba(15,23,42,1)", "itxt":"#f8fafc",
        "pbg":"#1e293b", "ptxt":"#f8fafc", "phov":"#334155", "psel":"rgba(59,130,246,0.2)",
        "shd":"0 8px 32px rgba(0,0,0,0.4)", "blur":"blur(16px)",
        "m_bg":"#0f172a", "m_card":"#1e293b", "m_grid":"#334155", "m_tick":"#94a3b8",
        "m_title":"#06b6d4", "m_poly":"#06b6d4", "m_pfill":"#3b82f6", "m_txt":"#f8fafc"
    },
    "light": {
        "bg":"#f8fafc", "card":"rgba(255,255,255,0.9)", "brd":"rgba(148,163,184,0.3)", "brd2":"rgba(15,23,42,0.05)",
        "txt":"#0f172a", "mut":"#64748b", "acc":"#2563eb", "acc2":"#0284c7",
        "suc":"#059669", "dng":"#e11d48", "gold":"#d97706",
        "ibg":"#ffffff", "itxt":"#0f172a",
        "pbg":"#ffffff", "ptxt":"#0f172a", "phov":"#f1f5f9", "psel":"rgba(37,99,235,0.1)",
        "shd":"0 4px 20px rgba(0,0,0,0.06)", "blur":"blur(12px)",
        "m_bg":"#ffffff", "m_card":"#f8fafc", "m_grid":"#e2e8f0", "m_tick":"#64748b",
        "m_title":"#2563eb", "m_poly":"#0284c7", "m_pfill":"#2563eb", "m_txt":"#0f172a"
    }
}

_SS = dict(theme="dark",diagrams={},freq=None,rwy1=None,rwy2=None,
           stats=None,cxlim=19.4,ready=False,show_table=False,
           _file_bytes=None,_file_name=None,_cols=None,
           _file_rows=0,_file_loaded=False,
           _processing=False)
for k,v in _SS.items():
    if k not in st.session_state: st.session_state[k]=v

# ══════════════════════════════════════════════════════════════════════
#  CSS INJECTION (DYNAMIC THEME + ANIMATIONS)
# ══════════════════════════════════════════════════════════════════════
def inject_css():
    T=TH[st.session_state.theme]; dk=st.session_state.theme=="dark"
    g=f"linear-gradient(135deg, {T['acc']}, {T['acc2']})"

    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;700;800&family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@300;400;500;600&display=swap');

:root {{
  --bg: {T['bg']}; --txt: {T['txt']}; --mut: {T['mut']}; --acc: {T['acc']}; --acc2: {T['acc2']};
  --ibg: {T['ibg']}; --brd: {T['brd']}; --brd2: {T['brd2']}; --card: {T['card']};
  --g: {g};
}}

html,body,.stApp,[data-testid="stApp"],[data-testid="stAppViewContainer"]{{
  font-family:'Inter',sans-serif!important;color:var(--txt)!important;
}}
[data-testid="stAppViewContainer"]{{background:var(--bg);background-attachment:fixed; transition: background 0.4s ease;}}
[data-testid="stAppViewContainer"]::before{{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(var(--brd) 1px,transparent 1px),linear-gradient(90deg,var(--brd) 1px,transparent 1px);
  background-size:40px 40px; mask-image: radial-gradient(circle at center, black 40%, transparent 100%);
  -webkit-mask-image: radial-gradient(circle at center, black 40%, transparent 100%);
}}

/* Universal Entrance Animations */
@keyframes zl-fade-in-up {{
  0% {{ opacity: 0; transform: translateY(30px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.block-container {{ position:relative;z-index:1;max-width:1000px!important; margin:0 auto!important;padding:1.5rem 2rem 5rem!important; }}
.zl-hero {{ animation: zl-fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) both; }}
.zl-animate-1 {{ animation: zl-fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both; }}
.zl-animate-2 {{ animation: zl-fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both; }}
.zl-animate-3 {{ animation: zl-fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both; }}

[data-testid="stSidebar"],section[data-testid="stSidebar"],[data-testid="collapsedControl"],[data-testid="stSidebarNav"]{{display:none!important;}}
#MainMenu,header,footer{{visibility:hidden!important;}}
*,*::before,*::after{{color:var(--txt)!important;-webkit-text-fill-color:var(--txt)!important;}}
.stButton>button,.stDownloadButton>button,button[data-testid],.zl-step-num{{ color:#ffffff!important;-webkit-text-fill-color:#ffffff!important; }}

/* ── FORM INPUTS DYNAMIC COLORING (FIXED FOR LIGHT MODE) ── */
.stTextInput>div>div>input {{
  background-color:var(--ibg)!important; border:1px solid var(--brd)!important; border-radius:8px!important;
  font-family:'JetBrains Mono',monospace!important;font-size:.9rem!important;padding:.7rem 1rem!important;
  color:var(--txt)!important; -webkit-text-fill-color:var(--txt)!important; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}
/* Fix for Number Input Container */
[data-testid="stNumberInputContainer"] {{
  background-color:var(--ibg)!important; border:1px solid var(--brd)!important; border-radius:8px!important;
  transition: all 0.3s ease;
}}
[data-testid="stNumberInputContainer"] input {{
  color:var(--txt)!important; -webkit-text-fill-color:var(--txt)!important; background:transparent!important;
  font-family:'JetBrains Mono',monospace!important;font-size:.9rem!important;
}}
/* Fix for Number Input +/- Buttons */
[data-testid="stNumberInputContainer"] button {{
  background:transparent!important; color:var(--txt)!important; border:none!important;
}}
[data-testid="stNumberInputContainer"] button * {{ fill:var(--txt)!important; }}

.stTextInput>div>div>input:hover, [data-testid="stNumberInputContainer"]:hover {{ border-color:rgba(148,163,184,0.4)!important; }}
.stTextInput>div>div>input:focus, [data-testid="stNumberInputContainer"]:focus-within {{ 
  border-color:var(--acc)!important; 
  box-shadow:0 0 0 4px {'rgba(59,130,246,0.15)' if dk else 'rgba(37,99,235,0.15)'}!important; 
  outline:none!important; transform: translateY(-1px);
}}

/* Selectbox Dynamic Coloring */
.stSelectbox>div>div {{ background-color:var(--ibg)!important; border:1px solid var(--brd)!important;border-radius:8px!important; transition: all 0.3s ease; padding: 0.1rem 0.2rem!important; }}
.stSelectbox>div>div:hover {{ border-color:rgba(148,163,184,0.4)!important; }}
.stSelectbox [data-baseweb="select"] span,.stSelectbox [data-baseweb="select"] div {{ font-family:'JetBrains Mono',monospace!important; background:transparent!important; color:var(--txt)!important; -webkit-text-fill-color:var(--txt)!important; }}
[data-baseweb="popover"],[data-baseweb="popover"]>div,ul[data-baseweb="menu"] {{ background-color:{T['pbg']}!important;border:1px solid var(--brd)!important; border-radius:8px!important; box-shadow:{T['shd']}!important; }}
[data-baseweb="popover"] li,[data-baseweb="popover"] [role="option"] {{ background:{T['pbg']}!important; font-family:'JetBrains Mono',monospace!important;font-size:.85rem!important; color:{T['ptxt']}!important; -webkit-text-fill-color:{T['ptxt']}!important; }}
[data-baseweb="popover"] li:hover {{ background:{T['phov']}!important; }}
[data-baseweb="popover"] [aria-selected="true"] {{ background:{T['psel']}!important;color:var(--acc)!important; -webkit-text-fill-color:var(--acc)!important;font-weight:600!important; }}

/* Labels */
label, div[data-testid="stCheckbox"] p {{ font-family:'Inter',sans-serif!important;font-size:.85rem!important; color:var(--mut)!important; font-weight:500!important; }}
.stTextInput label,.stSelectbox label,.stNumberInput label,.stFileUploader label {{ font-family:'JetBrains Mono',monospace!important;font-size:.7rem!important; letter-spacing:.05em!important;text-transform:uppercase!important; margin-bottom:0.4rem!important; }}

/* ── FILE UPLOADER FIX FOR LIGHT/DARK MODE ── */
[data-testid="stFileUploader"] section {{ background-color:var(--ibg)!important; border:1.5px dashed var(--acc)!important;border-radius:12px!important; transition: all 0.3s ease; padding: 2rem!important; }}
[data-testid="stFileUploader"] section:hover {{ background-color:{T['psel']}!important; border-color:var(--acc2)!important; transform: scale(1.01); }}
[data-testid="stFileUploader"] section * {{ color:var(--mut)!important; fill:var(--mut)!important; }}
/* Uploaded File Item Box */
[data-testid="stUploadedFile"] {{ background-color:var(--ibg)!important; border:1px solid var(--brd)!important; border-radius:8px!important; }}
[data-testid="stUploadedFile"] * {{ color:var(--txt)!important; fill:var(--txt)!important; }}
[data-testid="stUploadedFile"] button {{ background:transparent!important; }}

/* Primary Buttons */
.stButton>button, .stDownloadButton>button {{
  background:var(--g)!important; border:none!important;border-radius:8px!important; font-family:'JetBrains Mono',monospace!important;
  font-weight:600!important;font-size:.85rem!important;letter-spacing:.05em!important; text-transform:uppercase!important;
  padding:.7rem 1.4rem!important; transition:all .3s cubic-bezier(0.4,0,0.2,1)!important; color: white!important; -webkit-text-fill-color: white!important;
}}
.stButton>button:hover, .stDownloadButton>button:hover {{ transform:translateY(-3px)!important; box-shadow:0 8px 20px {'rgba(59,130,246,0.3)' if dk else 'rgba(37,99,235,0.25)'}!important; }}

/* Theme Toggle Pill Button */
.zl-theme-wrap .stButton>button {{
  background:transparent!important; color:var(--mut)!important; -webkit-text-fill-color:var(--mut)!important;
  border:1px solid var(--brd)!important; padding:0.4rem 1rem!important; font-size:0.75rem!important; width:auto!important;
  box-shadow:none!important; text-transform:none!important; letter-spacing:0!important; border-radius: 99px!important;
}}
.zl-theme-wrap .stButton>button:hover {{ border-color:var(--acc)!important; color:var(--acc)!important; -webkit-text-fill-color:var(--acc)!important; transform:translateY(-2px)!important; box-shadow:0 4px 10px rgba(0,0,0,0.05)!important; }}

/* Layout Elements */
.zl-hero {{ text-align:center;padding:2rem 1rem 3rem;position:relative; }}
.zl-hero-glow {{ position:absolute;top:-50px;left:50%;transform:translateX(-50%);width:500px;height:500px; background:{'radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 60%)' if dk else 'radial-gradient(circle, rgba(37,99,235,0.08) 0%, transparent 60%)'}; pointer-events:none; }}
.zl-tag {{ display:inline-flex;align-items:center;gap:.5rem;font-family:'JetBrains Mono',monospace;font-size:.7rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--acc2)!important; background:{'rgba(6,182,212,0.1)' if dk else 'rgba(2,132,199,0.08)'}; border:1px solid {'rgba(6,182,212,0.2)' if dk else 'rgba(2,132,199,0.2)'};padding:.3rem 1rem;border-radius:99px;margin-bottom:1.5rem; }}
.zl-dot {{ width:6px;height:6px;border-radius:50%;background:var(--acc2);animation:zl-pulse 2s ease-in-out infinite; }}
@keyframes zl-pulse {{ 0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.5;transform:scale(.75);}} }}
.zl-title {{ font-family:'Outfit',sans-serif;font-size:clamp(3rem,6vw,4.8rem);font-weight:800;line-height:1;letter-spacing:-.02em;margin:.3rem 0 .5rem; color:var(--txt)!important; }}
.zl-tagline {{ font-family:'Inter',sans-serif;font-size:1.15rem;color:var(--mut)!important; margin:0 auto 2rem; }}

/* Animated Hover Chips */
.zl-chips {{ display:flex;flex-wrap:wrap;justify-content:center;gap:.75rem;margin-bottom:2rem; }}
.zl-chip {{ 
  font-family:'JetBrains Mono',monospace;font-size:.65rem;font-weight:600;text-transform:uppercase;
  background:{'rgba(255,255,255,0.03)' if dk else '#ffffff'};border:1px solid var(--brd);padding:.4rem 1rem;border-radius:8px;
  color:var(--txt)!important; box-shadow:{'0 4px 12px rgba(0,0,0,0.2)' if dk else '0 2px 8px rgba(0,0,0,0.04)'};
  transition:all .3s cubic-bezier(.4,0,.2,1); cursor:default;
}}
.zl-chip:hover {{
  transform:translateY(-4px); border-color:var(--acc);
  box-shadow:0 8px 16px {'rgba(59,130,246,0.3)' if dk else 'rgba(37,99,235,0.2)'};
  color:var(--acc)!important;-webkit-text-fill-color:var(--acc)!important;
}}

.zl-hr {{ height:1px; background:linear-gradient(90deg,transparent,var(--brd),transparent); border:none;margin:2rem 0; }}

/* New Section Header Styling */
.zl-section-wrapper {{ display:flex; align-items:center; gap:12px; margin: 3rem 0 1.5rem; }}
.zl-section-num {{ background:var(--g); color:white!important; -webkit-text-fill-color:white!important; font-family:'JetBrains Mono',monospace; font-size:0.75rem; font-weight:800; padding:4px 8px; border-radius:6px; box-shadow: 0 2px 8px {'rgba(59,130,246,0.4)' if dk else 'rgba(37,99,235,0.3)'}; }}
.zl-section-lbl {{ font-family:'Outfit',sans-serif; font-size:1.25rem; font-weight:700; color:var(--txt)!important; text-transform:uppercase; letter-spacing:0.05em; }}
.zl-section-line {{ flex-grow:1; height:1px; background:linear-gradient(90deg, var(--brd) 0%, transparent 100%); }}

.zl-card {{ background:var(--card);border:1px solid var(--brd);border-radius:12px;padding:1.5rem;backdrop-filter:{T['blur']};box-shadow:{T['shd']};margin-bottom:1rem; transition: transform 0.3s, border-color 0.3s; }}

/* Steps */
.zl-step {{ display:flex;align-items:flex-start;gap:1rem;padding:1rem 0;border-bottom:1px solid var(--brd2); transition: transform 0.3s ease; }}
.zl-step:hover {{ transform: translateX(8px); }}
.zl-step:last-child {{ border-bottom:none; }}
.zl-step-num {{ width:34px;height:34px;border-radius:8px;background:var(--g);font-family:'Outfit',sans-serif;font-size:1rem;font-weight:800;display:flex;align-items:center;justify-content:center; box-shadow: 0 4px 10px {'rgba(59,130,246,0.3)' if dk else 'rgba(37,99,235,0.2)'}; color:white!important; -webkit-text-fill-color:white!important; }}
.zl-step-title {{ font-family:'Outfit',sans-serif;font-size:1.05rem;font-weight:600;margin-bottom:.2rem; color:var(--txt)!important; }}
.zl-step-desc {{ font-size:.85rem;color:var(--mut)!important;line-height:1.5; }}

/* Type Cards w/ Hover Physics */
.zl-type-grid {{ display:grid;grid-template-columns:repeat(4,1fr);gap:1.2rem;margin:.5rem 0 1rem; }}
.zl-type-card {{ background:{'rgba(15,23,42,0.6)' if dk else '#ffffff'};border:1px solid var(--brd);border-radius:12px;padding:1.5rem 1.2rem;transition:all .3s cubic-bezier(0.34, 1.56, 0.64, 1); box-shadow:{'none' if dk else '0 2px 8px rgba(0,0,0,0.03)'}; cursor:default; }}
.zl-type-card:hover {{ transform:translateY(-8px) scale(1.02); border-color:var(--acc); box-shadow:0 16px 32px {'rgba(59,130,246,0.15)' if dk else 'rgba(37,99,235,0.12)'}; }}
.zl-type-code {{ font-family:'Outfit',sans-serif;font-size:2.2rem;font-weight:800;background:var(--g);-webkit-background-clip:text;-webkit-text-fill-color:transparent!important;margin-bottom:.4rem; }}
.zl-type-name {{ font-family:'JetBrains Mono',monospace;font-size:.7rem;font-weight:600;text-transform:uppercase;color:var(--mut)!important;margin-bottom:.6rem; letter-spacing:0.05em; }}
.zl-type-desc {{ font-size:.85rem;line-height:1.5; color:var(--txt)!important; opacity:0.9; }}

/* Stats & Banners */
.zl-file-banner {{ background:{'rgba(16,185,129,0.1)' if dk else 'rgba(5,150,105,0.05)'};border:1px solid {T['suc']};border-radius:8px;padding:.8rem 1.2rem;font-family:'JetBrains Mono',monospace;font-size:.85rem;display:flex;align-items:center;gap:.8rem;margin-bottom:1rem; color:var(--txt)!important; animation: zl-fade-in-up 0.5s ease-out; }}
.zl-file-banner b {{ color:{T['suc']}!important; }}
.zl-stats {{ display:grid;grid-template-columns:repeat(6,1fr);gap:1rem;margin:1rem 0; }}
.zl-stat {{ background:{'rgba(15,23,42,0.6)' if dk else '#ffffff'};border:1px solid var(--brd);border-radius:10px;padding:1.2rem .5rem;text-align:center; box-shadow:{'none' if dk else '0 2px 6px rgba(0,0,0,0.03)'}; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }}
.zl-stat:hover {{ transform: translateY(-6px) scale(1.03); box-shadow: {T['shd']}; border-color: var(--acc); }}
.zl-sv {{ font-family:'Outfit',sans-serif;font-size:1.6rem;font-weight:800;background:var(--g);-webkit-background-clip:text;-webkit-text-fill-color:transparent!important; }}
.zl-sl {{ font-family:'JetBrains Mono',monospace;font-size:.65rem;font-weight:600;text-transform:uppercase;color:var(--mut)!important;margin-top:.5rem; letter-spacing:0.05em; }}
.zl-cov {{ background:{'rgba(59,130,246,0.1)' if dk else 'rgba(37,99,235,0.05)'};border:1px solid {'rgba(59,130,246,0.3)' if dk else 'rgba(37,99,235,0.2)'};border-radius:10px;padding:1.2rem;font-family:'JetBrains Mono',monospace;font-size:.85rem;display:flex;flex-wrap:wrap;gap:1.5rem;align-items:center;margin:1.5rem 0; color:var(--txt)!important; }}
.zl-cov b {{ color:var(--acc2)!important; font-size: 0.95rem; }}
.zl-pass {{ background:{'rgba(16,185,129,0.2)' if dk else 'rgba(5,150,105,0.1)'};border:1px solid {T['suc']};color:{T['suc']}!important;padding:4px 12px;border-radius:99px;font-weight:700; font-size:0.75rem; }}
.zl-fail {{ background:{'rgba(244,63,94,0.2)' if dk else 'rgba(225,29,72,0.1)'};border:1px solid {T['dng']};color:{T['dng']}!important;padding:4px 12px;border-radius:99px;font-weight:700; font-size:0.75rem; }}

/* Generate Button Emphasis */
.zl-gen-wrap .stButton>button {{ padding:1.2rem!important;font-size:1.15rem!important;border-radius:12px!important;box-shadow:{'0 8px 30px rgba(59,130,246,0.4)' if dk else '0 6px 20px rgba(37,99,235,0.3)'}!important;animation:zl-genpulse 3s cubic-bezier(0.4, 0, 0.2, 1) infinite; }}
@keyframes zl-genpulse {{ 0%,100%{{box-shadow:0 4px 20px {'rgba(59,130,246,0.3)' if dk else 'rgba(37,99,235,0.2)'}; transform: scale(1);}} 50%{{box-shadow:0 12px 40px {'rgba(59,130,246,0.6)' if dk else 'rgba(37,99,235,0.4)'}; transform: scale(1.01);}} }}

/* Upgraded Loading Screen */
.zl-loading-screen {{ display:flex;flex-direction:column;align-items:center;justify-content:center;padding:5rem 2rem;background:var(--ibg);border:1px solid var(--brd);border-radius:16px;margin:2rem 0; box-shadow:{T['shd']}; animation: zl-fade-in-up 0.4s ease-out; }}
.zl-loader-orbit {{ position:relative;width:90px;height:90px;margin-bottom:2.5rem; }}
.zl-loader-core {{ position:absolute;inset:50%;width:14px;height:14px;transform:translate(-50%,-50%);border-radius:50%;background:var(--acc);box-shadow:0 0 25px var(--acc);animation:zl-corepulse 1.5s ease-in-out infinite; }}
@keyframes zl-corepulse {{ 0%,100%{{transform:translate(-50%,-50%) scale(1); box-shadow:0 0 20px var(--acc); }} 50%{{transform:translate(-50%,-50%) scale(1.8); box-shadow:0 0 50px var(--acc2); }} }}
.zl-orbit-ring {{ position:absolute;inset:0;border-radius:50%;border:2px solid transparent;animation:zl-orbit linear infinite; }}
.zl-orbit-ring:nth-child(2) {{ border-top-color:var(--acc);border-right-color:{'rgba(59,130,246,0.3)' if dk else 'rgba(37,99,235,0.2)'};animation-duration:1.2s; }}
.zl-orbit-ring:nth-child(3) {{ inset:12px;border-bottom-color:var(--acc2);border-left-color:{'rgba(6,182,212,0.3)' if dk else 'rgba(2,132,199,0.2)'};animation-duration:0.9s;animation-direction:reverse; }}
.zl-load-stage {{ font-family:'Outfit',sans-serif;font-size:1.3rem;font-weight:700;margin-bottom:.5rem; color:var(--txt)!important; animation: zl-text-pulse 2s infinite; }}
@keyframes zl-text-pulse {{ 0%,100%{{opacity:0.8;}} 50%{{opacity:1;}} }}
.zl-load-pct {{ font-family:'JetBrains Mono',monospace;font-size:.85rem;font-weight:600; color:var(--acc2)!important;letter-spacing:.15em;margin-bottom:2rem; }}
.zl-load-bar-outer {{ width:320px;height:6px;background:{'rgba(255,255,255,0.1)' if dk else 'rgba(15,23,42,0.1)'};border-radius:99px;overflow:hidden; }}
.zl-load-bar-fill {{ height:100%;background:var(--g);border-radius:99px;transition:width .4s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 0 12px var(--acc); }}
@keyframes zl-orbit {{ from{{transform:rotate(0deg);}}to{{transform:rotate(360deg);}} }}

/* Table */
.zl-freq-box {{ background:{'rgba(15,23,42,0.6)' if dk else '#ffffff'};border:1px solid var(--brd);border-radius:12px;padding:1.5rem;margin:1rem 0; box-shadow:{'none' if dk else '0 2px 8px rgba(0,0,0,0.03)'}; }}
.zl-freq-hdr {{ font-family:'Outfit',sans-serif;font-size:1.2rem;font-weight:700;margin-bottom:.5rem; color:var(--txt)!important; }}
.zl-tbl {{ width:100%;border-collapse:collapse;font-family:'JetBrains Mono',monospace;font-size:.75rem; }}
.zl-tbl th {{ background:{'#1e293b' if dk else '#f8fafc'}!important;color:var(--txt)!important;padding:12px 10px;text-align:center;border-bottom:2px solid {'rgba(59,130,246,0.5)' if dk else 'rgba(37,99,235,0.3)'}; }}
.zl-tbl td {{ padding:10px 8px;border-bottom:1px solid var(--brd2);text-align:center;color:var(--txt)!important; opacity:0.9; }}
.zl-tbl td.dc {{ text-align:left;color:var(--acc2)!important;font-weight:600;background:{'rgba(255,255,255,0.02)' if dk else 'rgba(15,23,42,0.02)'}!important; opacity:1; }}
.zl-tbl tr:hover td {{ background: {'rgba(255,255,255,0.03)' if dk else 'rgba(15,23,42,0.02)'}!important; }}

/* Footer */
.zl-footer {{ text-align:center;padding:4rem 0 2rem;margin-top:5rem;border-top:1px solid var(--brd); animation: zl-fade-in-up 1s ease both; }}
.zl-footer-brand {{ font-family:'Outfit',sans-serif;font-size:1.6rem;font-weight:800;background:var(--g);-webkit-background-clip:text;-webkit-text-fill-color:transparent!important;margin-bottom:.5rem; letter-spacing:0.05em; }}
.zl-footer-line {{ font-family:'Inter',sans-serif;font-size:.85rem;color:var(--mut)!important;margin:.4rem 0; font-weight:500; }}
.zl-footer-divider {{ width:50px;height:4px;background:var(--g);border-radius:2px;margin:1.5rem auto; }}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════
def section(num, label):
    return (f'<div class="zl-section-wrapper">'
            f'<div class="zl-section-num">{num}</div>'
            f'<div class="zl-section-lbl">{label}</div>'
            f'<div class="zl-section-line"></div></div>')

def sc(v,l):
    return f'<div class="zl-stat"><div class="zl-sv">{v}</div><div class="zl-sl">{l}</div></div>'

def zl_loading(pct, stage):
    return (f'<div class="zl-loading-screen">'
            f'<div class="zl-loader-orbit">'
            f'<div class="zl-orbit-ring"></div>'
            f'<div class="zl-orbit-ring"></div>'
            f'<div class="zl-loader-core"></div></div>'
            f'<div class="zl-load-stage">{stage}</div>'
            f'<div class="zl-load-pct">{pct:.0f}% EXECUTING</div>'
            f'<div class="zl-load-bar-outer">'
            f'<div class="zl-load-bar-fill" style="width:{pct:.0f}%;"></div></div></div>')

# ══════════════════════════════════════════════════════════════════════
#  DATA PROCESSING
# ══════════════════════════════════════════════════════════════════════
def load_file(f):
    name=f.name.lower(); raw=f.read(); f.seek(0)
    if name.endswith((".xlsx",".xls")):
        try: return pd.read_excel(io.BytesIO(raw),engine="openpyxl"), None
        except Exception as e: return None, str(e)
    for enc in ("utf-8","utf-8-sig","latin-1","cp1252"):
        try: return pd.read_csv(io.BytesIO(raw),encoding=enc,low_memory=False), None
        except Exception: pass
    return None, "Cannot decode file."

@st.cache_data(show_spinner=False)
def process_data(fb, fname, dc, sc_col, dfmt, su):
    name=fname.lower()
    if name.endswith((".xlsx",".xls")): df=pd.read_excel(io.BytesIO(fb),engine="openpyxl")
    else:
        df=None
        for enc in ("utf-8","utf-8-sig","latin-1","cp1252"):
            try: df=pd.read_csv(io.BytesIO(fb),encoding=enc,low_memory=False); break
            except Exception: pass
        if df is None: raise ValueError("Cannot decode file.")
    df.columns=df.columns.str.strip()
    for col in (dc,sc_col):
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found. Available: {list(df.columns)}")
    w=df[[dc,sc_col]].copy(); w.columns=["dir","spd"]
    if dfmt=="Compass (N, NNE ...)":
        w["dg"]=w["dir"].astype(str).str.strip().str.upper().map(C2D)
    else:
        w["dg"]=pd.to_numeric(w["dir"],errors="coerce")%360
    w["kmh"]=pd.to_numeric(w["spd"],errors="coerce")
    if su=="knots": w["kmh"]*=1.852
    elif su=="m/s":  w["kmh"]*=3.6
    w=w.dropna(subset=["dg","kmh"])
    if len(w)==0: raise ValueError("No valid rows after processing.")
    w["sec"]=(((w["dg"]+11.25)%360)//22.5).astype(int).clip(0,15)
    w["sc"]=pd.cut(w["kmh"],bins=SPD_BINS,labels=list(range(7))).astype(float).astype("Int64")
    total=len(w); freq=np.zeros((16,7))
    for s in range(16):
        for c in range(7):
            freq[s,c]=((w.sec==s)&(w.sc==c)).sum()/total*100
    op=freq[:,1:7].sum(axis=1)
    return freq,{"total":total,"calm":round(freq[:,0].sum(),1),
                 "op":round(op.sum(),1),"avg":round(w.kmh.mean(),1),
                 "max":round(w.kmh.max(),1),"dom":DIRS_16[int(op.argmax())]}

# ══════════════════════════════════════════════════════════════════════
#  RUNWAY ANALYSIS
# ══════════════════════════════════════════════════════════════════════
def ha(cx): return np.degrees(np.arcsin(min(cx/24.1,1.)))
def rwy_cov(freq,hdg,cx):
    h=ha(cx); t=0.
    for i in range(16):
        d=abs(((i*22.5-hdg+180)%360)-180)
        if d<=h or d>=180-h: t+=freq[i,1:7].sum()
    return min(t,100.)
def best_rwy(freq,cx,excl=None):
    bh,bc=0.,0.
    for hdg in np.arange(0,180,5):
        if excl is not None and abs(((hdg-excl+90)%180)-90)<20: continue
        c=rwy_cov(freq,hdg,cx)
        if c>bc: bc,bh=c,hdg
    return float(bh)
def comb_cov(freq,r1,r2,cx):
    h=ha(cx); t=0.
    for i in range(16):
        a=i*22.5; d1=abs(((a-r1+180)%360)-180); d2=abs(((a-r2+180)%360)-180)
        if d1<=h or d1>=180-h or d2<=h or d2>=180-h: t+=freq[i,1:7].sum()
    return min(t,100.)
def rwy_lbl(hdg):
    e1=int(round(hdg/10))%36 or 36; e2=int(round((hdg+180)/10))%36 or 36
    return f"Runway {e1:02d}/{e2:02d}"

# ══════════════════════════════════════════════════════════════════════
#  FREQUENCY TABLE
# ══════════════════════════════════════════════════════════════════════
def freq_table_html(freq):
    th_cols="".join([f"<th>{c}</th>" for c in TBL_COLS])
    hdr=(f'<tr><th class="dh" rowspan="2">Direction</th>'
         f'<th colspan="{len(TBL_COLS)}">Duration of Wind (%)</th>'
         f'<th rowspan="2">Total % above 0.97 Knots</th></tr>'
         f'<tr>{th_cols}</tr>')
    rows=""
    for i,d in enumerate(DIRS_16):
        td_cells="".join([f"<td>{freq[i,j]:.1f}</td>" for j in TBL_IDX])
        tot=sum(freq[i,j] for j in TBL_IDX)
        rows+=(f'<tr><td class="dc">{d}</td>{td_cells}<td>{tot:.1f}</td></tr>')
    t_cells="".join([f"<td>{freq[:,j].sum():.1f}</td>" for j in TBL_IDX])
    tt=sum(freq[:,j].sum() for j in TBL_IDX)
    rows+=(f'<tr class="trow"><td class="dc">TOTAL</td>{t_cells}<td>{tt:.1f}</td></tr>')
    return (f'<div class="zl-freq-box"><div class="zl-freq-hdr">Statistical Frequency Matrix</div>'
            f'<table class="zl-tbl">{hdr}{rows}</table></div>')

def freq_to_csv(freq):
    rows=[]
    for i,d in enumerate(DIRS_16):
        r={"Direction":d}
        for j,lbl in enumerate(TBL_COLS): r[lbl]=round(freq[i,TBL_IDX[j]],4)
        r["Total % (>0.97 Knots)"]=round(sum(freq[i,j] for j in TBL_IDX),4)
        rows.append(r)
    t={"Direction":"TOTAL"}
    for j,lbl in enumerate(TBL_COLS): t[lbl]=round(freq[:,TBL_IDX[j]].sum(),4)
    t["Total % (>0.97 Knots)"]=round(sum(freq[:,j].sum() for j in TBL_IDX),4)
    rows.append(t)
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")

# ══════════════════════════════════════════════════════════════════════
#  DIAGRAM RENDERERS (DYNAMIC THEME LINKED)
# ══════════════════════════════════════════════════════════════════════
def _polar(title, theme):
    T = TH[theme]
    fig,ax=plt.subplots(figsize=(7.5,7.5),subplot_kw=dict(polar=True),facecolor=T["m_bg"])
    ax.set_facecolor(T["m_card"]); ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    ax.grid(color=T["m_grid"],linestyle="--",lw=0.6,alpha=0.8)
    ax.spines["polar"].set_color(T["m_grid"])
    ax.set_xticks(np.linspace(0,2*np.pi,16,endpoint=False))
    ax.set_xticklabels(DIRS_16,fontsize=9,fontweight="bold",color=T["m_txt"],fontfamily="monospace")
    ax.tick_params(axis="y",labelsize=7.5,labelcolor=T["m_tick"])
    ax.set_title(title,fontsize=12,fontweight="bold",pad=26,color=T["m_title"],wrap=True,fontfamily="sans-serif")
    return fig,ax

def _leg(ax, handles, theme):
    T = TH[theme]
    ax.legend(handles=handles,loc="lower left",bbox_to_anchor=(-0.22,-0.28),
              fontsize=8.5,framealpha=0.9,facecolor=T["m_card"],
              edgecolor=T["m_grid"],labelcolor=T["m_txt"])

def _png(fig, theme):
    T = TH[theme]
    buf=io.BytesIO()
    fig.savefig(buf,format="png",dpi=180,bbox_inches="tight",facecolor=T["m_bg"])
    plt.close(fig); buf.seek(0); return buf.getvalue()

def _refcircles(ax, mv, theme):
    T = TH[theme]
    for frac in [.25,.5,.75,1.]:
        rv=mv*frac
        ax.plot(np.linspace(0,2*np.pi,200),[rv]*200,color=T["m_tick"],lw=0.6,alpha=0.6,zorder=1)
        ax.text(np.radians(10),rv,f"{rv:.1f}%",fontsize=7.5,color=T["m_tick"],ha="left",va="bottom")

def render_t1s(freq, theme):
    T = TH[theme]
    dp=freq[:,1:7].sum(axis=1); N=16
    th=np.linspace(0,2*np.pi,N,endpoint=False); mv=max(dp.max(),1.)
    fig,ax=_polar("TYPE I  —  SINGLE RUNWAY\n", theme)
    _refcircles(ax,mv, theme)
    ax.fill(th,dp,color=T["m_pfill"],alpha=0.25,zorder=2)
    ax.plot(np.append(th,th[0]),np.append(dp,dp[0]),color=T["m_poly"],lw=2.5,zorder=3)
    sz=[110 if dp[i]>=mv*.90 else 65 if dp[i]>=mv*.60 else 35 for i in range(N)]
    ax.scatter(th,dp,s=sz,color=T["m_poly"],zorder=4,edgecolors=T["m_card"],linewidths=1.5)
    dom=int(np.argmax(dp))
    ax.text(th[dom],dp[dom]*1.16,f"{dp[dom]:.1f}%",fontsize=9,color=T["m_poly"],ha="center",va="bottom",fontweight="bold")
    ax.set_ylim(0,mv*1.30)
    _leg(ax,[mpatches.Patch(color=T["m_pfill"],alpha=0.4,label="Wind Polygon"), plt.Line2D([0],[0],color=T["m_poly"],lw=2,label="Outline")], theme)
    plt.tight_layout(rect=[0,.07,1,.97]); return _png(fig, theme)

def render_t1m(freq, theme):
    T = TH[theme]
    dp=freq[:,1:7].sum(axis=1); N=16
    th=np.linspace(0,2*np.pi,N,endpoint=False); mv=max(dp.max(),1.)
    fig,ax=_polar("TYPE I  —  MULTI RUNWAY\n", theme)
    _refcircles(ax,mv, theme)
    ax.fill(th,dp,color=T["m_pfill"],alpha=0.25,zorder=2)
    ax.plot(np.append(th,th[0]),np.append(dp,dp[0]),color=T["m_poly"],lw=2.5,zorder=3)
    ax.scatter(th,dp,s=35,color=T["m_poly"],zorder=4,edgecolors=T["m_card"],linewidths=1.5)
    dom=int(np.argmax(dp))
    ax.text(th[dom],dp[dom]*1.16,f"{dp[dom]:.1f}%",fontsize=8.5,color=T["m_poly"],ha="center",va="bottom",fontweight="bold")
    ax.set_ylim(0,mv*1.32)
    _leg(ax,[mpatches.Patch(color=T["m_pfill"],alpha=0.4,label="Wind Polygon")], theme)
    plt.tight_layout(rect=[0,.07,1,.97]); return _png(fig, theme)

def render_t2s(freq, theme):
    T = TH[theme]
    N=16; th=np.linspace(0,2*np.pi,N,endpoint=False); w=2*np.pi/N*.80
    fig,ax=_polar("TYPE II  —  SINGLE RUNWAY\n", theme)
    bot=np.zeros(N)
    for s in range(7):
        ax.bar(th,freq[:,s],width=w,bottom=bot,color=T2_COLORS[s],edgecolor=T["m_card"],lw=0.8,alpha=0.95,label=T2_NAMES[s],zorder=3)
        bot+=freq[:,s]
    dom=int(bot.argmax())
    ax.text(th[dom],bot[dom]*1.10,f"{bot[dom]:.1f}%",fontsize=8.5,color=T["m_txt"],ha="center",va="bottom",fontweight="bold")
    ax.set_ylim(0,bot.max()*1.22 or 1)
    _leg(ax,[mpatches.Patch(color=T2_COLORS[i],label=T2_NAMES[i],edgecolor=T["m_card"],lw=0.5) for i in range(7)], theme)
    plt.tight_layout(rect=[0,.09,1,.97]); return _png(fig, theme)

def render_t2m(freq, theme):
    T = TH[theme]
    N=16; th=np.linspace(0,2*np.pi,N,endpoint=False); w=2*np.pi/N*.80
    fig,ax=_polar("TYPE II  —  MULTI RUNWAY\n", theme)
    bot=np.zeros(N)
    for s in range(7):
        ax.bar(th,freq[:,s],width=w,bottom=bot,color=T2_COLORS[s],edgecolor=T["m_card"],lw=0.8,alpha=0.95,label=T2_NAMES[s],zorder=3)
        bot+=freq[:,s]
    dom=int(bot.argmax())
    ax.text(th[dom],bot[dom]*1.10,f"{bot[dom]:.1f}%",fontsize=8.5,color=T["m_txt"],ha="center",va="bottom",fontweight="bold")
    ax.set_ylim(0,bot.max()*1.22 or 1)
    _leg(ax,[mpatches.Patch(color=T2_COLORS[i],label=T2_NAMES[i],edgecolor=T["m_card"],lw=0.5) for i in range(7)], theme)
    plt.tight_layout(rect=[0,.10,1,.97]); return _png(fig, theme)

# ══════════════════════════════════════════════════════════════════════
#  PDF BUILDER (FOOTER METADATA REDESIGN)
# ══════════════════════════════════════════════════════════════════════
def build_pdf(diagrams, sname, roll, batch, section_val, inst, site, date_val, logo_b=None):
    buf=io.BytesIO(); PW,PH=A4; MG=1.8*cm; lr=None
    if logo_b:
        try: lr=ImageReader(io.BytesIO(logo_b))
        except Exception: pass
    
    def pg(cvs,doc):
        cvs.saveState()
        
        # --- HEADER ---
        cvs.setFont("Helvetica-Bold",12); cvs.setFillColor(RC.black)
        cvs.drawCentredString(PW/2,PH-1.0*cm,"WIND ROSE DIAGRAM REPORT")
        cvs.setLineWidth(1.2); cvs.setStrokeColor(RC.black)
        cvs.line(MG,PH-1.4*cm,PW-MG,PH-1.4*cm)
        if lr:
            ls=1.5*cm
            try: cvs.drawImage(lr,PW-MG-ls,PH-1.35*cm,width=ls,height=ls,preserveAspectRatio=True,mask="auto")
            except Exception: pass
            
        # --- FOOTER ---
        cvs.line(MG,2.2*cm,PW-MG,2.2*cm)
        cvs.setFont("Helvetica",9.5); cvs.setFillColor(RC.black)
        
        parts1 = []
        if sname: parts1.append(sname.strip())
        if roll:  parts1.append(f"Roll No: {roll.strip()}")
        if batch: parts1.append(f"Batch: {batch.strip()}")
        if section_val: parts1.append(f"Sec: {section_val.strip()}")
        if parts1: cvs.drawString(MG, 1.6*cm, "  |  ".join(parts1))

        parts2 = []
        if inst: parts2.append(f"Instructor: {inst.strip()}")
        if site: parts2.append(f"Site: {site.strip()}")
        if date_val: parts2.append(f"Date: {date_val.strip()}")
        if parts2: cvs.drawString(MG, 1.1*cm, "  |  ".join(parts2))

        cvs.drawRightString(PW-MG,1.1*cm,f"Page {doc.page}")
        cvs.restoreState()
        
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=MG,rightMargin=MG,topMargin=2.0*cm,bottomMargin=2.5*cm)
    sty_t=ParagraphStyle("t",fontName="Helvetica-Bold",fontSize=15,textColor=RC.black,alignment=TA_CENTER,spaceAfter=4)
    sty_c=ParagraphStyle("c",fontName="Helvetica-Oblique",fontSize=9.5,textColor=RC.HexColor("#444"),alignment=TA_CENTER,spaceAfter=4)
    ORD=["t1s","t1m","t2s","t2m"]
    LBL={"t1s":"Type I - Single Runway  (Polygon)","t1m":"Type I - Multi Runway  (Polygon)",
         "t2s":"Type II - Single Runway  (Speed Bars)","t2m":"Type II - Multi Runway  (Speed Bars)"}
    story=[]; first=True
    for key in ORD:
        if key not in diagrams: continue
        if not first: story.append(PageBreak())
        first=False
        story.append(Paragraph(f"Wind Rose Diagram - {LBL[key]}",sty_t))
        story.append(HRFlowable(width="100%",thickness=1.2,color=RC.black,spaceAfter=12))
        story.append(Spacer(1,0.4*cm))
        story.append(RLImage(io.BytesIO(diagrams[key]),width=15.5*cm,height=15.5*cm,kind="proportional"))
        story.append(Spacer(1,0.25*cm))
        story.append(Paragraph(f"Figure: {LBL[key]}",sty_c))
    if not story: story.append(Paragraph("No diagrams selected.",sty_t))
    doc.build(story,onFirstPage=pg,onLaterPages=pg)
    buf.seek(0); return buf.getvalue()

# ══════════════════════════════════════════════════════════════════════
#  MAIN UI
# ══════════════════════════════════════════════════════════════════════
def main():
    inject_css()
    dk = st.session_state.theme == "dark"

    # ── THEME TOGGLE ──────────────────────────────────────────────
    st.markdown('<div style="display:flex; justify-content:flex-end; margin-bottom:-2rem; position:relative; z-index:10;">', unsafe_allow_html=True)
    st.markdown('<div class="zl-theme-wrap">',unsafe_allow_html=True)
    icon = "☀️ Enable Light Mode" if dk else "🌙 Enable Dark Mode"
    if st.button(icon, key="theme_btn"):
        st.session_state.theme = "light" if dk else "dark"; st.rerun()
    st.markdown('</div></div>',unsafe_allow_html=True)

    # ── HERO ───────────────────────────────────────────────────────
    st.markdown("""
    <div class="zl-hero">
      <div class="zl-hero-glow"></div>
      <div class="zl-tag"><span class="zl-dot"></span>Aeronautical Wind Analytics Engine</div>
      <div class="zl-title">Rose Mapper</div>
      <p class="zl-tagline">"Directional Data, Designed."</p>
      <div class="zl-chips">
        <span class="zl-chip">ICAO Standard</span>
        <span class="zl-chip">Automated WRD</span>
        <span class="zl-chip">Data Visualization</span>
        <span class="zl-chip">PDF Export</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── EXECUTION ARCHITECTURE ──────────────────────────────
    st.markdown('<div class="zl-animate-1">', unsafe_allow_html=True)
    st.markdown(section("01", "Execution Architecture"),unsafe_allow_html=True)
    hc1,hc2=st.columns(2,gap="large")
    steps=[("Data Input","Upload raw CSV or Excel wind datasets"),
           ("Vector Mapping","Assign direction and velocity columns"),
           ("Parameters","Define speed units and direction format"),
           ("Project Meta","Input credentials for generated PDF reports"),
           ("Computation","Execute runway coverage algorithms"),
           ("Export Results","Download statistical matrix and graphics")]
    with hc1:
        for i,(t,d) in enumerate(steps[:3],1):
            st.markdown(f'<div class="zl-step"><div class="zl-step-num">{i}</div>'
                        f'<div><div class="zl-step-title">{t}</div>'
                        f'<div class="zl-step-desc">{d}</div></div></div>',unsafe_allow_html=True)
    with hc2:
        for i,(t,d) in enumerate(steps[3:],4):
            st.markdown(f'<div class="zl-step"><div class="zl-step-num">{i}</div>'
                        f'<div><div class="zl-step-title">{t}</div>'
                        f'<div class="zl-step-desc">{d}</div></div></div>',unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── DIAGRAM METHODOLOGY ─────────────────────────────────────────────
    st.markdown('<div class="zl-animate-2">', unsafe_allow_html=True)
    st.markdown(section("02", "Diagram Methodology"),unsafe_allow_html=True)
    st.markdown("""<div class="zl-type-grid">
      <div class="zl-type-card">
        <div class="zl-type-code">I·S</div>
        <div class="zl-type-name">Type I — Single</div>
        <div class="zl-type-desc">Polygon geometry. Longest spoke marks optimum runway vector.</div>
      </div>
      <div class="zl-type-card">
        <div class="zl-type-code">I·M</div>
        <div class="zl-type-name">Type I — Multi</div>
        <div class="zl-type-desc">Polygon geometry applied to dual runway spatial planning.</div>
      </div>
      <div class="zl-type-card">
        <div class="zl-type-code">II·S</div>
        <div class="zl-type-name">Type II — Single</div>
        <div class="zl-type-desc">Color-coded speed magnitude bars classified by ICAO thresholds.</div>
      </div>
      <div class="zl-type-card">
        <div class="zl-type-code">II·M</div>
        <div class="zl-type-name">Type II — Multi</div>
        <div class="zl-type-desc">Speed magnitude classification for dual runway optimization.</div>
      </div>
    </div>""",unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── UPLOAD & CONFIG ───────────────────────────────────────────
    st.markdown('<div class="zl-animate-3">', unsafe_allow_html=True)
    st.markdown(section("03", "Data Ingestion Module"),unsafe_allow_html=True)

    uploaded=st.file_uploader("Upload wind data matrix (CSV/Excel)",type=["csv","xlsx","xls"],label_visibility="collapsed")

    if uploaded is not None:
        df_tmp,err=load_file(uploaded); uploaded.seek(0)
        if err or df_tmp is None:
            st.error(f"Failed to parse file structure: {err}"); st.session_state._file_loaded=False
        else:
            raw=uploaded.read(); uploaded.seek(0)
            st.session_state._file_bytes=raw; st.session_state._file_name=uploaded.name
            st.session_state._cols=list(df_tmp.columns)
            st.session_state._file_rows=len(df_tmp); st.session_state._file_loaded=True

    fl=st.session_state._file_loaded; cols=st.session_state._cols or []
    fn=st.session_state._file_name or ""; fr=st.session_state._file_rows or 0

    if fl:
        st.markdown(f'<div class="zl-file-banner"><b>[DATA LOADED]</b>&nbsp;&nbsp;'
                    f'{fn}&nbsp;&nbsp;&middot;&nbsp;&nbsp;{fr:,} Records parsed'
                    f'</div>',unsafe_allow_html=True)

    if fl and cols:
        st.markdown("<br>",unsafe_allow_html=True)
        def _g(opts,kws):
            for kw in kws:
                for i,c in enumerate(opts):
                    if kw in c.lower(): return i
            return 0
        di=_g(cols,["dir","wd","wind_d"]); si=_g(cols,["spee","ws","wind_s","vel"])
        if si==di: si=min(di+1,len(cols)-1)
        
        m1,m2,m3,m4=st.columns(4)
        with m1: dir_col=st.selectbox("Direction Vector Column",cols,index=di,key="dcol")
        with m2: spd_col=st.selectbox("Velocity Magnitude Column",cols,index=si,key="scol")
        with m3: dir_fmt=st.selectbox("Heading Format",["Degrees (0-360)","Compass (N, NNE ...)"],key="dfmt")
        with m4: spd_unit=st.selectbox("Input Velocity Unit",["km/h","knots","m/s"],key="sunit")

        st.markdown("<br>",unsafe_allow_html=True)
        rw1,rw2,rw3,rw4=st.columns(4)
        with rw1:
            cx_s=st.selectbox("Crosswind Tolerance Threshold",
                ["10.5 Knots (19.4 km/h) — Light Aircraft",
                 "13.0 Knots (24.1 km/h) — Medium Aircraft",
                 "20.0 Knots (37.0 km/h) — Heavy Aircraft"],key="cxs")
            cxlim=float(cx_s.split("(")[1].split()[0])
        with rw2: auto=st.checkbox("Algorithmic runway detection",value=True,key="auto")
        with rw3: r1_in=st.number_input("Runway 1 Vector (deg)",0,179,0,5,disabled=auto,key="r1i")
        with rw4: r2_in=st.number_input("Runway 2 Vector (deg)",0,179,45,5,disabled=auto,key="r2i")

        st.markdown("<br>",unsafe_allow_html=True)
        d1,d2,d3,d4=st.columns(4)
        with d1: s_t1s=st.checkbox("Compile Type I (Single)",value=True,key="ct1s")
        with d2: s_t1m=st.checkbox("Compile Type I (Multi)",value=True,key="ct1m")
        with d3: s_t2s=st.checkbox("Compile Type II (Single)",value=True,key="ct2s")
        with d4: s_t2m=st.checkbox("Compile Type II (Multi)",value=True,key="ct2m")
        sel={"t1s":s_t1s,"t1m":s_t1m,"t2s":s_t2s,"t2m":s_t2m}

    st.markdown('</div>',unsafe_allow_html=True)

    # ── DOCUMENT METADATA ─────────────────────────────────────────
    st.markdown(section("04", "Document Metadata"),unsafe_allow_html=True)
    
    ui1, ui2, ui3, ui4 = st.columns(4)
    with ui1: stu_name = st.text_input("Author Name", value="", key="sname")
    with ui2: roll_no = st.text_input("Roll No", value="", key="srollno")
    with ui3: batch_val = st.text_input("Batch", value="", key="sbatch")
    with ui4: section_val = st.text_input("Section", value="", key="ssection")

    st.markdown("<br>", unsafe_allow_html=True)

    ui5, ui6, ui7, ui8 = st.columns(4)
    with ui5: instructor = st.text_input("Course Instructor", value="", key="sinst")
    with ui6: stu_site = st.text_input("Project Site", value="", key="ssite")
    with ui7: date_val = st.text_input("Date", value="", key="sdate")
    with ui8: logo_file = st.file_uploader("Brand Logo (Opt)", type=["png","jpg","jpeg"], key="logo_up")

    # ── GENERATE BUTTON ───────────────────────────────────────────
    gen_btn=False
    if fl:
        st.markdown("<br><br>",unsafe_allow_html=True)
        _,gc,_=st.columns([1,2,1])
        with gc:
            st.markdown('<div class="zl-gen-wrap">',unsafe_allow_html=True)
            gen_btn=st.button("Initialize Compilation Engine",use_container_width=True)
            st.markdown('</div>',unsafe_allow_html=True)

    # ── GENERATE LOGIC ────────────────────────────────────────────
    if gen_btn:
        if not fl:
            st.warning("Awaiting wind data matrix upload.")
        elif not any(sel.values()):
            st.warning("Minimum one diagram type required for compilation.")
        else:
            if logo_file is not None:
                try: st.session_state['_pdf_logo']=logo_file.read(); logo_file.seek(0)
                except: st.session_state['_pdf_logo']=None
            else: st.session_state['_pdf_logo']=None

            ph=st.empty()
            ph.markdown(zl_loading(0,"Initializing Environment..."),unsafe_allow_html=True)
            
            try:
                freq,stats=process_data(st.session_state._file_bytes,st.session_state._file_name,
                                        dir_col,spd_col,dir_fmt,spd_unit)
                
                ph.markdown(zl_loading(35,"Calculating Runway Geometries..."),unsafe_allow_html=True)
                time.sleep(0.4) 
                
                if auto:
                    r1=best_rwy(freq,cxlim); r2=best_rwy(freq,cxlim,excl=r1)
                else:
                    r1,r2=float(r1_in),float(r2_in)

                ph.markdown(zl_loading(65,"Rendering Vector Graphics..."),unsafe_allow_html=True)

                tnow = st.session_state.theme
                diags={}
                rmap={"t1s":lambda:render_t1s(freq, tnow),"t1m":lambda:render_t1m(freq, tnow),
                      "t2s":lambda:render_t2s(freq, tnow),"t2m":lambda:render_t2m(freq, tnow)}
                for key,fn in rmap.items():
                    if not sel[key]: continue
                    try: diags[key]=fn()
                    except Exception as e: st.warning(f"Engine fault on {key}: {e}")

                ph.markdown(zl_loading(100,"Finalizing Output Sequence..."),unsafe_allow_html=True)
                time.sleep(0.6); ph.empty()

                st.session_state.diagrams=diags; st.session_state.freq=freq
                st.session_state.rwy1=r1; st.session_state.rwy2=r2
                st.session_state.stats=stats; st.session_state.cxlim=cxlim
                
                # Store PDF Meta
                st.session_state['_pdf_name']=stu_name
                st.session_state['_pdf_roll']=roll_no
                st.session_state['_pdf_batch']=batch_val
                st.session_state['_pdf_sec']=section_val
                st.session_state['_pdf_inst']=instructor
                st.session_state['_pdf_site']=stu_site
                st.session_state['_pdf_date']=date_val

                st.session_state.ready=True
            except ValueError as e:
                ph.empty(); st.error(f"Matrix integrity failure: {e}"); st.stop()
            except Exception as e:
                ph.empty(); st.error(f"System halt: {e}"); st.stop()

    # ── RESULTS ───────────────────────────────────────────────────
    if st.session_state.ready and st.session_state.diagrams:
        freq=st.session_state.freq; r1=st.session_state.rwy1
        r2=st.session_state.rwy2; stats=st.session_state.stats
        cx=st.session_state.cxlim; diags=st.session_state.diagrams
        c1=rwy_cov(freq,r1,cx); c2=rwy_cov(freq,r2,cx)
        cc=comb_cov(freq,r1,r2,cx); icao=cc>=95.

        st.markdown(section("05", "Analytic Telemetry"),unsafe_allow_html=True)

        st.markdown('<div class="zl-stats">'
                    +sc(f"{stats['total']:,}","Data Points")
                    +sc(f"{stats['calm']:.1f}%","Calm Freq")
                    +sc(f"{stats['op']:.1f}%","Operational")
                    +sc(f"{stats['avg']:.1f} kt","Mean Vel.")
                    +sc(stats['dom'],"Primary Vec.")
                    +sc(f"{cc:.1f}%","Net Coverage")
                    +'</div>',unsafe_allow_html=True)

        st.markdown(f"""<div class="zl-cov">
          &#9992; <b>{rwy_lbl(r1)}</b>: {c1:.1f}%
          &nbsp;&nbsp;&middot;&nbsp;&nbsp; &#9992; <b>{rwy_lbl(r2)}</b>: {c2:.1f}%
          &nbsp;&nbsp;&middot;&nbsp;&nbsp; Combined: <b>{cc:.1f}%</b>
          &nbsp;&nbsp;&middot;&nbsp;&nbsp; Limit: <b>{cx:.1f} kt</b>
          &nbsp;&nbsp;&middot;&nbsp;&nbsp; <span class="{'zl-pass' if icao else 'zl-fail'}">{'✓ ICAO &ge;95%' if icao else '✗ ICAO &lt;95%'}</span>
        </div>""",unsafe_allow_html=True)

        # ── FREQUENCY TABLE ──────────
        tog_lbl="Hide Frequency Matrix" if st.session_state.show_table else "Load Frequency Matrix"
        if st.button(tog_lbl,key="tog_tbl"):
            st.session_state.show_table=not st.session_state.show_table; st.rerun()

        if st.session_state.show_table:
            st.markdown(freq_table_html(freq),unsafe_allow_html=True)
            ec1,ec2=st.columns([2,3])
            with ec1:
                st.download_button(label="Export Data (CSV)",
                                   data=freq_to_csv(freq),
                                   file_name="rose_mapper_matrix.csv",
                                   mime="text/csv",key="csv_dl")

        # ── DIAGRAM PREVIEWS ──────────
        st.markdown("<br>",unsafe_allow_html=True)
        st.markdown(section("06", "Generated Visuals"),unsafe_allow_html=True)
        DLBL={"t1s":"Type I — Single Vector","t1m":"Type I — Multi Vector",
              "t2s":"Type II — Single Vector","t2m":"Type II — Multi Vector"}
        vis=[k for k in ["t1s","t1m","t2s","t2m"] if k in diags]
        for ri in range(0,len(vis),2):
            row_k=vis[ri:ri+2]; rcols=st.columns(len(row_k),gap="large")
            for ci,key in enumerate(row_k):
                with rcols[ci]:
                    st.markdown(f'<div class="zl-dlbl">{DLBL[key]}</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="zl-card" style="padding:10px; transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); cursor: crosshair;" onmouseover="this.style.transform=\'scale(1.03)\'" onmouseout="this.style.transform=\'scale(1)\'">',unsafe_allow_html=True)
                    st.image(diags[key],use_container_width=True)
                    st.markdown('</div>',unsafe_allow_html=True)

        # ── PDF DOWNLOAD ──────────────
        st.markdown("<br>",unsafe_allow_html=True)
        st.markdown(section("07", "Report Generation"),unsafe_allow_html=True)

        _pn = st.session_state.get('_pdf_name','')
        _pr = st.session_state.get('_pdf_roll','')
        _pb = st.session_state.get('_pdf_batch','')
        _psec = st.session_state.get('_pdf_sec','')
        _pinst = st.session_state.get('_pdf_inst','')
        _psite = st.session_state.get('_pdf_site','')
        _pdate = st.session_state.get('_pdf_date','')
        _pl = st.session_state.get('_pdf_logo',None)

        _,dc,_=st.columns([1,2,1])
        with dc:
            with st.spinner("Compiling structural PDF payload..."):
                pdf_b=build_pdf(diags, _pn, _pr, _pb, _psec, _pinst, _psite, _pdate, _pl)
            st.download_button("Download Compiled Report (PDF)",data=pdf_b,
                               file_name="RoseMapper_Report.pdf",
                               mime="application/pdf",use_container_width=True)

    # ── FOOTER ────────────────────────────────────────────────────
    st.markdown("""
    <div class="zl-footer">
      <div class="zl-footer-brand">ROSE MAPPER</div>
      <div class="zl-footer-divider"></div>
      <div class="zl-footer-line">Aeronautical Wind Analytics Platform</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:.7rem;font-weight:600;
           letter-spacing:.1em;color:inherit;margin:1rem 0 .3rem; opacity: 0.7;">
        ENGINEERED BY ABDUL ALEEM
      </div>
    </div>
    """,unsafe_allow_html=True)

main()
