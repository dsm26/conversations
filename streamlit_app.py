import streamlit as st
import pandas as pd
import toml
import os
import urllib.parse

# ----------------------------------------------------
# 1. CONFIGURATION & TOML SETUP
# ----------------------------------------------------
st.set_page_config(page_title="Scenario Walkthrough", page_icon="🗣️", layout="centered")

CONFIG_FILE = "conversations.toml"

if os.path.exists(CONFIG_FILE):
    try:
        config_data = toml.load(CONFIG_FILE)
        CONVERSATIONS_LIST = config_data.get("conversations", [])
    except Exception as e:
        st.error(f"Error reading {CONFIG_FILE}: {e}")
        CONVERSATIONS_LIST = []
else:
    st.error(f"Configuration file '{CONFIG_FILE}' not found. Please create it in the root directory.")
    CONVERSATIONS_LIST = []

# ----------------------------------------------------
# 2. HELPER FUNCTIONS
# ----------------------------------------------------
def build_google_sheet_csv_url(spreadsheet_id, worksheet_name):
    """Constructs a direct CSV export URL using the Google Visualization API."""
    base_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
    encoded_worksheet = urllib.parse.quote(worksheet_name)
    return f"{base_url}?tqx=out:csv&sheet={encoded_worksheet}"

@st.cache_data(ttl=60)
def load_scenario_data(spreadsheet_id, worksheet_name):
    """Fetches, sanitizes, and types Google Sheet data blocks safely."""
    try:
        csv_url = build_google_sheet_csv_url(spreadsheet_id, worksheet_name)
        df = pd.read_csv(csv_url)
        
        df.columns = [c.strip().replace(' ', '_').lower() for c in df.columns]
        required = ['scenario_name', 'sequence', 'speaker_tag', 'is_user', 'italian', 'english']
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"⚠️ **Column Alignment Error in Tab '{worksheet_name}'**")
            return pd.DataFrame()
            
        # Secure Type Sanitization to eliminate Python structural rendering type exceptions
        df['sequence'] = pd.to_numeric(df['sequence']).fillna(0).astype(int)
        df['scenario_name'] = df['scenario_name'].fillna('').astype(str).str.strip()
        df['speaker_tag'] = df['speaker_tag'].fillna('').astype(str).str.strip()
        df['italian'] = df['italian'].fillna('').astype(str).str.strip()
        df['english'] = df['english'].fillna('').astype(str).str.strip()
        df['is_user'] = df['is_user'].fillna('FALSE').astype(str).str.strip().str.upper() == 'TRUE'
        
        return df.sort_values(by=['scenario_name', 'sequence']).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading worksheet '{worksheet_name}': {e}")
        return pd.DataFrame()

# ----------------------------------------------------
# 3. SIDEBAR AND APP STATE INIT
# ----------------------------------------------------
st.sidebar.title("🎛️ App Settings")

if CONVERSATIONS_LIST:
    display_names = [item["display_name"] for item in CONVERSATIONS_LIST]
    selected_display = st.sidebar.selectbox("Select Scenario Pack", display_names)
    
    selected_config = next(item for item in CONVERSATIONS_LIST if item["display_name"] == selected_display)
    df_all = load_scenario_data(selected_config["spreadsheet_id"], selected_config["worksheet_name"])
    selected_id = selected_config["id"]
else:
    df_all = pd.DataFrame()
    selected_id = None

# Condense the option labels to "English first" and "Italian First"
display_mode = st.sidebar.radio(
    "Prompt Language:",
    ["Italian First", "English first"]
)
target_first = "Italian" in display_mode

if not df_all.empty:
    scenarios = df_all['scenario_name'].unique().tolist()
    
    if 'current_scenario_idx' not in st.session_state or st.session_state.get('last_deck_id') != selected_id:
        st.session_state.current_scenario_idx = 0
        st.session_state.current_line_sequence = 1
        st.session_state.show_translation = False
        st.session_state.last_deck_id = selected_id

    current_scenario = scenarios[st.session_state.current_scenario_idx]
    df_scenario = df_all[df_all['scenario_name'] == current_scenario].sort_values('sequence').reset_index(drop=True)
    
    total_lines = len(df_scenario)
    current_row = df_scenario[df_scenario['sequence'] == st.session_state.current_line_sequence]
    
    if current_row.empty and total_lines > 0:
        st.session_state.current_line_sequence = int(df_scenario['sequence'].min())
        current_row = df_scenario[df_scenario['sequence'] == st.session_state.current_line_sequence]

    # ----------------------------------------------------
    # 4. MAIN INTERFACE RENDERING (CLEAN HEADER / NO SUBHEAD)
    # ----------------------------------------------------
    # Just the scenario name, no labels or extra header tags
    st.title(current_scenario)
    
    # Smaller status indicator sub-line
    current_num = st.session_state.current_scenario_idx + 1
    total_scenarios = len(scenarios)
    st.caption(f"Practicing scenario {current_num} of {total_scenarios}")

    # Dialogue Display Window
    if not current_row.empty:
        row = current_row.iloc[0]
        
        speaker_name = str(row['speaker_tag']).replace('"', '&quot;').replace("'", "&#39;")
        is_user = bool(row['is_user'])
        
        user_suffix = " (You)" if is_user else ""
        full_speaker_label = f"{speaker_name}{user_suffix}"
        
        prompt_text = str(row['italian']) if target_first else str(row['english'])
        translation_text = str(row['english']) if target_first else str(row['italian'])
        
        # Clean background bubble colors based on chat role alignment
        bg_color = "#e8f0fe" if is_user else "#f1f3f4"
        text_color = "#1a73e8" if is_user else "#3c4043"
        border_radius = "18px 18px 4px 18px" if is_user else "18px 18px 18px 4px"
        
        # Inject standard style structural wrappers safely to handle fluid viewport heights
        st.html(f"""
            <div style="margin-top: 15px; margin-bottom: 5px; font-family: -apple-system, sans-serif;">
                <span style="font-size: 0.85em; font-weight: 600; color: #5f6368; display: block; margin-bottom: 3px;">
                    {full_speaker_label}
                </span>
            </div>
        """)
        
        # Combined Box Content Model: Keeps prompt and answer in the exact same footprint
        with st.container(border=True):
            # Monospace text stack guarantees differentiation between letters like 'l' and 'I'
            st.markdown(
                f"##### <span style='font-family: \"Consolas\", \"Monaco\", monospace; color: {text_color}; font-weight: 500;'>{prompt_text}</span>", 
                unsafe_html=True
            )
            
            if st.session_state.show_translation:
                st.html("<div style='border-top: 1px dashed #ccc; margin: 12px 0;'></div>")
                st.markdown(
                    f"**Translation:**\n<span style='font-family: \"Consolas\", \"Monaco\", monospace; font-size: 1.15em; color: #555; font-style: italic;'>{translation_text}</span>", 
                    unsafe_html=True
                )

    # ----------------------------------------------------
    # 5. NAVIGATION CONTROLS & MOBILITY ERGONOMICS
    # ----------------------------------------------------
    min_seq = int(df_scenario['sequence'].min())
    max_seq = int(df_scenario['sequence'].max())
    
    is_first_line = (st.session_state.current_line_sequence == min_seq)
    is_last_line = (st.session_state.current_line_sequence == max_seq)

    st.write("") # Padding spacer
    
    # Mobile Action Row 1: The reveal button sits on its own line right over the directions
    if st.button("👁️ Show Answer / Translation", use_container_width=True):
        st.session_state.show_translation = not st.session_state.show_translation
        st.rerun()

    # Mobile Action Row 2: Navigation commands placed split side-by-side on one row
    nav_col_left, nav_col_right = st.columns(2)

    with nav_col_left:
        if st.button("⬅️ Previous Line", disabled=is_first_line, use_container_width=True):
            prev_seqs = df_scenario[df_scenario['sequence'] < st.session_state.current_line_sequence]['sequence']
            if not prev_seqs.empty:
                st.session_state.current_line_sequence = int(prev_seqs.max())
                st.session_state.show_translation = False
                st.rerun()

    with nav_col_right:
        if is_last_line:
            if st.session_state.current_scenario_idx < len(scenarios) - 1:
                if st.button("🎉 Next Scenario", type="primary", use_container_width=True):
                    st.session_state.current_scenario_idx += 1
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
            else:
                st.balloons()
                st.success("🏆 Completed all scenarios in this pack!")
                if st.button("🔄 Restart Pack", use_container_width=True):
                    st.session_state.current_scenario_idx = 0
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
        else:
            if st.button("Next Line ➡️", use_container_width=True):
                next_seqs = df_scenario[df_scenario['sequence'] > st.session_state.current_line_sequence]['sequence']
                if not next_seqs.empty:
                    st.session_state.current_line_sequence = int(next_seqs.min())
                    st.session_state.show_translation = False
                    st.rerun()
else:
    st.info("Verify your setup configurations inside conversations.toml to load your data sets.")
