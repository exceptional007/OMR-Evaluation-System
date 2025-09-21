import streamlit as st
from PIL import Image
import numpy as np
from io import BytesIO
import pandas as pd
import os
import json

# This assumes you have an 'app' directory with the necessary modules.
# If you don't, you'll need to create dummy functions for these imports.
from app.core.config import settings
from app.services.omr import compute_scores_from_answers, format_answers_as_columns
from app.services.key import parse_key_excel
from app.services.preprocess import detect_orientation, rectify_perspective
from app.services.detect import evaluate_by_questions
from app.services.grid import estimate_grid_rois
from app.services.omr_template import draw_overlay


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# -------------- UI helpers --------------

@st.cache_data
def cached_parse_key_excel(file_bytes, sheet_name):
    """Caches the result of parsing the Excel key file to improve performance."""
    return parse_key_excel(file_bytes, sheet_name)

def _inject_css(theme: str = "Cyberpunk"):
    theme = (theme or "Cyberpunk").lower()
    
    if theme == "nord":
        css_vars = """
        :root {
          --brand-primary: #88C0D0;      /* Nord 8 - Icy Blue */
          --brand-accent: #5E81AC;       /* Nord 10 - Deeper Blue */
          --brand-primary-rgb: 136, 192, 208;
          --brand-accent-rgb: 94, 129, 172;

          --bg-main: #2E3440;           /* Nord 0 */
          --bg-sidebar: #3B4252;        /* Nord 1 */
          --card-bg: #3B4252;
          --card-border: #4C566A;        /* Nord 3 */
          --muted: #D8DEE9;             /* Nord 4 */
          --text: #ECEFF4;              /* Nord 6 */
          --radius: 8px;
        }
        """
    elif theme == "synthwave":
        css_vars = """
        :root {
          --brand-primary: #F000FF;      /* Magenta */
          --brand-accent: #00E5FF;       /* Electric Cyan */
          --brand-primary-rgb: 240, 0, 255;
          --brand-accent-rgb: 0, 229, 255;

          --bg-main: #0D021F;
          --bg-sidebar: #1A052A;
          --card-bg: rgba(26, 5, 42, 0.7);
          --card-border: rgba(var(--brand-primary-rgb), 0.3);
          --muted: #A482C4;
          --text: #F5E6FF;
          --radius: 10px;
        }
        """
    else: # Cyberpunk (default)
        css_vars = """
        :root {
          --brand-primary: #00FF41;      /* Electric Green */
          --brand-accent: #00BFFF;       /* Deep Sky Blue */
          --brand-primary-rgb: 0, 255, 65;
          --brand-accent-rgb: 0, 191, 255;

          --bg-main: #000000;
          --bg-sidebar: #0D1117;
          --card-bg: rgba(20, 20, 20, 0.6);
          --card-border: rgba(var(--brand-primary-rgb), 0.2);
          --muted: #888888;
          --text: #EAEAEA;
          --radius: 8px;
        }
        """

    css_rest = f"""
        /* App background */
        .main > div {{
          background: var(--bg-main);
          color: var(--text);
          padding-bottom: 2rem;
        }}
        /* Global Font Style */
        body {{
            font-family: "JetBrains Mono", monospace;
        }}
        /* Sidebar */
        [data-testid="stSidebar"] {{ 
            background: var(--bg-sidebar);
            border-right: 1px solid var(--card-border);
        }}        
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] label {{ color: var(--muted); }}

        [data-testid="stInfo"] {{
            background-color: rgba(var(--brand-accent-rgb), 0.1);
            color: var(--text);
            border: 1px solid rgba(var(--brand-accent-rgb), 0.2);
            border-radius: var(--radius);
        }}

        /* Hero */
        .hero {{
          background: radial-gradient(80% 80% at 20% 10%, rgba(var(--brand-primary-rgb), 0.1) 0%, rgba(var(--brand-primary-rgb), 0.0) 100%), var(--card-bg);
          border: 1px solid var(--card-border);
          border-radius: 14px; padding: 26px 30px; margin: 12px 0 10px 0;
          box-shadow: 0 4px 12px rgba(0,0,0, 0.4);
        }}
        .hero h1 {{
            margin: 0 0 8px 0; font-size: 30px; color: var(--brand-primary);
            text-shadow: 0 0 8px rgba(var(--brand-primary-rgb), 0.5);
        }}
        .hero p {{ margin: 0; color: var(--muted); }}
        
        /* Theme-Adaptive Button Styles */
        .stButton>button {{
          background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
          color: #2E3440; /* Dark text for contrast */
          border: 0; padding: 0.65rem 1.05rem; border-radius: var(--radius); font-weight: bold;
          box-shadow: 0 10px 20px rgba(var(--brand-primary-rgb), 0.2);
          transition: transform .06s ease, box-shadow .2s ease;
        }}
        .stButton>button:hover {{ 
            box-shadow: 0 12px 24px rgba(var(--brand-primary-rgb), 0.3);
            color: #000000;
        }}        
        .stButton>button:active {{ transform: translateY(1px); }}
        .stButton>button:disabled {{
            background: rgba(128, 128, 128, 0.2);
            color: rgba(255, 255, 255, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: none;
            cursor: not-allowed;
        }}
        
        /* Other elements */
        [data-testid="stFileUploaderDropzone"] {{
          background: var(--card-bg);
          border: 1px dashed var(--brand-primary);
        }}
        [data-baseweb="tab-list"], [data-testid="stMetric"], .stDataFrame, .streamlit-expanderHeader {{
          background: var(--card-bg);
          border: 1px solid var(--card-border);
          border-radius: var(--radius);
        }}
        .stDataFrame {{ padding: 0.5rem; }}
        [data-testid="stMetric"] {{ padding: 12px 14px; }}
        .streamlit-expanderHeader {{ 
            padding: 0.75rem;
            color: var(--brand-accent);
            font-weight: 600;
        }}

        /* --- RESPONSIVENESS IMPROVEMENT --- */
        @media (max-width: 600px) {{
            .hero h1 {{
                font-size: 24px; /* Smaller font for mobile */
            }}
            .stButton>button {{
                padding: 0.6rem 0.9rem; /* Slightly smaller button padding */
            }}
        }}
    """

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
        {css_vars}
        {css_rest}
        </style>
    """, unsafe_allow_html=True)


def _status_metrics(container, uploaded_files, key_map, tpl_file):
    files_count = len(uploaded_files) if uploaded_files else 0
    key_status = "Loaded" if key_map else "Not loaded"
    tpl_status = "Loaded" if tpl_file else "Not loaded"
    
    with container:
        c1, c2, c3 = st.columns(3)
        c1.metric("Images Queued", files_count)
        c2.metric("Answer Key", key_status)
        c3.metric("Template", tpl_status)


# --- Page Configuration ---
st.set_page_config(page_title="OMR Neural Grid", page_icon="💠", layout="wide")

# --- Sidebar ---
with st.sidebar:
    st.header("Global Settings")
    theme_choice = st.selectbox("Theme", ["Cyberpunk", "Synthwave", "Nord"], index=0)
    sheet_version = st.selectbox("Sheet Version", settings.sheet_versions, index=0)
    st.markdown("---")
    st.info("Max per-subject: **{}**\n\nTotal: **{}**".format(settings.per_subject_max, settings.total_max))

_inject_css(theme_choice)

# --- Main App ---
st.markdown("""
<div class="hero">
  <h1>💠 OMR Neural Grid</h1>
  <p>A high-throughput optical mark recognition (OMR) evaluation tool with a modern interface.</p>
</div>
""", unsafe_allow_html=True)

# --- Two-Column Layout ---
col1, col2 = st.columns([1, 2], gap="large")

# --- Column 1: Control Panel ---
with col1:
    st.subheader("1. Configure Evaluation")
    
    key_file = st.file_uploader("Upload Answer Key (.xlsx)", type=["xlsx"])
    key_sheet = None
    key_map = None

    if key_file:
        try:
            key_bytes = key_file.getvalue()
            xls = pd.ExcelFile(BytesIO(key_bytes))
            key_sheet = st.selectbox("Select Key Sheet (Set)", options=xls.sheet_names, index=0, key="key_sheet_selector")
            key_map = cached_parse_key_excel(key_bytes, key_sheet) # Using cached function
            st.success(f"Key loaded from sheet: '{key_sheet}'")
        except Exception as e:
            st.error(f"Failed to parse key: {e}")

    with st.expander("Template & Alignment (Optional)"):
        tpl_file = st.file_uploader("Upload Template JSON", type=["json"])
        fill_threshold = st.slider("Fill threshold", 0.1, 0.9, 0.45, 0.01)
        min_margin = st.slider("Min margin between top 2", 0.0, 0.5, 0.12, 0.01)
        st.caption("Alignment fine-tuning:")
        scale_x = st.slider("Scale X", 0.9, 1.1, 1.0, 0.005, key="scale_x")
        scale_y = st.slider("Scale Y", 0.9, 1.1, 1.0, 0.005, key="scale_y")
        offset_x = st.slider("Offset X", -0.05, 0.05, 0.0, 0.001, key="offset_x")
        offset_y = st.slider("Offset Y", -0.05, 0.05, 0.0, 0.001, key="offset_y")
        show_overlay = st.checkbox("Show debug overlay", value=False)

    st.subheader("2. Upload OMR Sheets")
    uploaded_files = st.file_uploader(
        "Select up to 500 images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )
    
    st.subheader("3. Set Options & Run")
    large_batch = st.checkbox(
        "Large batch mode",
        value=False,
        help="Recommended for 200+ images. Skips per-image sheets for faster export.",
    )
    save_to_db = st.checkbox("Save results to database", value=False)
    student_id_hint = st.text_input("Student ID pattern", value="filename_without_extension")

    st.markdown("---")
    evaluate_button = st.button(f"Evaluate {len(uploaded_files)} image(s)", use_container_width=True, disabled=not uploaded_files)

# --- Column 2: Results Display ---
with col2:
    st.subheader("Status & Results")
    status_container = st.container()
    results_container = st.container()
    
    # User guidance messages
    with results_container:
        if not uploaded_files:
            st.info("Please upload OMR sheets in the left panel to begin.")
        elif not key_map:
            st.warning("Answer key not loaded. Scores will not be calculated.")
        else:
            st.success("Ready to evaluate. Click the 'Evaluate' button to start.")

    if uploaded_files:
        _status_metrics(status_container, uploaded_files, key_map, tpl_file)

    if evaluate_button:
        # Clear guidance messages before showing results
        results_container.empty()

        if key_map is None:
            st.warning("No answer key loaded. Scores cannot be computed.")

        if len(uploaded_files) > 500:
            st.warning("Processing only the first 500 files.")
            uploaded_files = uploaded_files[:500]

        results = []
        detailed_sheets = []
        progress_bar = st.progress(0, text="Starting Evaluation...")

        for i, uf in enumerate(uploaded_files, 1):
            try:
                progress_bar.progress(i / len(uploaded_files), text=f"Processing: {uf.name}")
                
                image = Image.open(uf).convert("RGB")
                np_img = np.array(image)

                np_img, _ = detect_orientation(np_img)
                np_img = rectify_perspective(np_img)

                if tpl_file is not None:
                    tpl = json.loads(tpl_file.getvalue().decode("utf-8"))
                    questions = sorted(tpl.get("questions", []), key=lambda q: q.get("index", 0))
                    answers = evaluate_by_questions(
                        np_img,
                        questions,
                        scale_x=scale_x, scale_y=scale_y,
                        offset_x=offset_x, offset_y=offset_y,
                    )
                else:
                    h, w = np_img.shape[:2]
                    questions = estimate_grid_rois(w, h)
                    answers = evaluate_by_questions(np_img, questions)
                
                per_subj_scores, total_score = {}, None
                if key_map:
                    per_subj_scores, total_score = compute_scores_from_answers(answers, key_map)

                row = {"filename": uf.name, "Set": key_sheet or sheet_version}
                for s in settings.subjects:
                    if per_subj_scores.get(s) is not None:
                        row[s] = per_subj_scores[s]
                if total_score is not None:
                    row["total"] = total_score
                results.append(row)

                if not large_batch:
                    cols = format_answers_as_columns(answers)
                    detailed_sheets.append((uf.name, pd.DataFrame(cols)))

            except Exception as e:
                results.append({"filename": uf.name, "error": str(e)})

        st.success("Evaluation complete!")
        
        # Improved error reporting
        error_files = [r['filename'] for r in results if 'error' in r and pd.notna(r['error'])]
        if error_files:
            st.error(f"Processing failed for {len(error_files)} image(s):\n" + "\n".join(f"- {f}" for f in error_files))

        if results:
            df = pd.DataFrame(results)
            tab_sum, tab_charts, tab_dl = st.tabs(["📄 Summary", "📈 Charts", "💾 Downloads"])

            with tab_sum:
                st.dataframe(df, use_container_width=True)
                
            with tab_charts:
                chart_df = df.dropna(subset=[s for s in settings.subjects if s in df.columns])
                c1, c2 = st.columns(2)
                if "total" in chart_df.columns and not chart_df["total"].empty:
                    c1.subheader("Total Score Distribution")
                    c1.bar_chart(chart_df["total"])
                
                by_subject = {s: chart_df[s].mean() for s in settings.subjects if s in chart_df.columns and not chart_df[s].empty}
                if by_subject:
                    c2.subheader("Per-Subject Average")
                    c2.bar_chart(by_subject)

            with tab_dl:
                subject_cols = list(settings.subjects)
                ordered_cols = [c for c in ["filename", "Set", *subject_cols, "total"] if c in df.columns]
                df_for_export = df[ordered_cols] if ordered_cols else df

                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    df_for_export.to_excel(writer, index=False, sheet_name="Summary")
                    if not large_batch:
                        for name, dfi in detailed_sheets:
                            safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '.', '_')]).rstrip()[:28]
                            dfi.to_excel(writer, index=False, sheet_name=f"Answers_{safe_name}")
                st.download_button(
                    label="Download Excel Results",
                    data=buffer.getvalue(),
                    file_name="omr_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                csv = df_for_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download CSV Summary", 
                    data=csv, 
                    file_name="omr_summary.csv", 
                    mime="text/csv",
                    use_container_width=True
                )