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
    """Constructs a direct CSV export URL using the spreadsheet ID and worksheet tab name."""
    base_export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
    # URL-encode the worksheet name to safely handle spaces, numbers, and accents
    encoded_worksheet = urllib.parse.quote(worksheet_name)
    return f"{base_export_url}&sheet={encoded_worksheet}"

@st.cache_data(ttl=300)  # Caches data for 5 minutes
def load_scenario_data(spreadsheet_id, worksheet_name):
    """Fetches data from a specific Google Sheet tab, normalizes headers, and sorts by sequence."""
    try:
        csv_url = build_google_sheet_csv_url(spreadsheet_id, worksheet_name)
        df = pd.read_csv(csv_url)
        
        # Normalize column names: strip spaces, replace inner spaces with underscores, force lowercase
        # This allows human-friendly names like "Scenario Name" in Google Sheets to match "scenario_name" in code
        df.columns = [c.strip().replace(' ', '_').lower() for c in df.columns]
        
        # Code validation checks for normalized names
        required = ['scenario_name', 'sequence', 'speaker_tag', 'is_user', 'italian', 'english']
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"Missing required columns in tab '{worksheet_name}': {missing}")
            return pd.DataFrame()
            
        df['sequence'] = pd.to_numeric(df['sequence']).astype(int)
        return df.sort_values(by=['scenario_name', 'sequence']).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading worksheet '{worksheet_name}': {e}")
        return pd.DataFrame()

# ----------------------------------------------------
# 3. SIDEBAR AND APP STATE INIT
# ----------------------------------------------------
st.sidebar.title("🎛️ App Settings")

if CONVERSATIONS_LIST:
    # Build a selection mapping using the display_name from TOML
    display_names = [item["display_name"] for item in CONVERSATIONS_LIST]
    selected_display = st.sidebar.selectbox("Select Scenario Pack", display_names)
    
    # Extract the matching configuration dictionary block
    selected_config = next(item for item in CONVERSATIONS_LIST if item["display_name"] == selected_display)
    
    # Load from the targeted sheet using spreadsheet_id and worksheet_name
    df_all = load_scenario_data(selected_config["spreadsheet_id"], selected_config["worksheet_name"])
    selected_id = selected_config["id"]
else:
    df_all = pd.DataFrame()
    selected_id = None

# Language Toggle Mode
display_mode = st.sidebar.radio(
    "Prompt Language:",
    ["Target Language First (Italian ➡️ English)", "Native Language First (English ➡️ Italian)"]
)
target_first = "Italian" in display_mode

if not df_all.empty:
    scenarios = df_all['scenario_name'].unique().tolist()
    
    # Initialize or reset session tracking states when shifting packs
    if 'current_scenario_idx' not in st.session_state or st.session_state.get('last_deck_id') != selected_id:
        st.session_state.current_scenario_idx = 0
        st.session_state.current_line_sequence = 1
        st.session_state.show_translation = False
        st.session_state.last_deck_id = selected_id

    # Filter data down to the actively selected scenario block
    current_scenario = scenarios[st.session_state.current_scenario_idx]
    df_scenario = df_all[df_all['scenario_name'] == current_scenario].sort_values('sequence').reset_index(drop=True)
    
    total_lines = len(df_scenario)
    current_row = df_scenario[df_scenario['sequence'] == st.session_state.current_line_sequence]
    
    if current_row.empty and total_lines > 0:
        st.session_state.current_line_sequence = int(df_scenario['sequence'].min())
        current_row = df_scenario[df_scenario['sequence'] == st.session_state.current_line_sequence]

    # ----------------------------------------------------
    # 4. MAIN INTERFACE RENDERING
    # ----------------------------------------------------
    st.title("🗣️ Scenario Walkthrough")
    st.caption(f"Currently practicing Pack ID: `{selected_id}`")
    
    # Scenario Progress Header Card
    with st.container(border=True):
        col_scen_left, col_scen_right = st.columns([3, 1])
        with col_scen_left:
            st.subheader(f"🎬 Scenario: {current_scenario}")
            if 'setting' in df_scenario.columns:
                st.caption(f"📍 **Setting:** {df_scenario['setting'].iloc[0]}")
        with col_scen_right:
            st.metric("Scenario Progress", f"{st.session_state.current_scenario_idx + 1} / {len(scenarios)}")

    st.write("---")

    # Dialogue Display Window
    if not current_row.empty:
        row = current_row.iloc[0]
        speaker = row['speaker_tag']
        is_user = str(row['is_user']).upper() == 'TRUE'
        
        prompt_text = row['italian'] if target_first else row['english']
        translation_text = row['english'] if target_first else row['italian']
        
        # Establish ergonomic chat bubble styling positions based on role
        alignment = "right" if is_user else "left"
        bg_color = "#e8f0fe" if is_user else "#f1f3f4"
        text_color = "#1a73e8" if is_user else "#3c4043"
        
        st.markdown(
            f"""
            <div style="text-align: {alignment}; margin-bottom: 20px;">
                <span style="font-size: 0.85em; font-weight: bold; color: #5f6368; display: block; margin-bottom: 4px;">
                    {speaker} {'(You)' if is_user else ''}
                </span>
                <div style="display: inline-block; padding: 14px 20px; background-color: {bg_color}; 
                            border-radius: 15px; max-width: 75%; text-align: left; 
                            box-shadow: 0 1px 2px rgba(0,0,0,0.1); border: 1px solid rgba(0,0,0,0.05);">
                    <p style="font-size: 1.25em; margin: 0; color: {text_color}; font-weight: 500;">{prompt_text}</p>
                </div>
            </div>
            """, 
            unsafe_html=True
        )

        # Translation/Reveal Panel Card
        col_space, col_btn_reveal, col_cb = st.columns([1, 2, 2])
        with col_btn_reveal:
            if st.button("👁️ Show Answer / Translation", use_container_width=True):
                st.session_state.show_translation = not st.session_state.show_translation
        
        if st.session_state.show_translation:
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 5px solid #34a853; 
                            border-radius: 4px; margin: 15px 0; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);">
                    <strong style="color: #202124;">Translation:</strong>
                    <p style="font-size: 1.15em; margin-top: 5px; color: #3c4043; font-style: italic;">{translation_text}</p>
                </div>
                """, 
                unsafe_html=True
            )

    st.write("---")

    # ----------------------------------------------------
    # 5. NAVIGATION CONTROLS & LOGIC BOUNDARIES
    # ----------------------------------------------------
    min_seq = int(df_scenario['sequence'].min())
    max_seq = int(df_scenario['sequence'].max())
    
    is_first_line = (st.session_state.current_line_sequence == min_seq)
    is_last_line = (st.session_state.current_line_sequence == max_seq)

    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])

    with nav_col1:
        if st.button("⬅️ Previous Line", disabled=is_first_line, use_container_width=True):
            prev_seqs = df_scenario[df_scenario['sequence'] < st.session_state.current_line_sequence]['sequence']
            if not prev_seqs.empty:
                st.session_state.current_line_sequence = int(prev_seqs.max())
                st.session_state.show_translation = False
                st.rerun()

    with nav_col2:
        if st.button("Next Line ➡️", disabled=is_last_line, use_container_width=True):
            next_seqs = df_scenario[df_scenario['sequence'] > st.session_state.current_line_sequence]['sequence']
            if not next_seqs.empty:
                st.session_state.current_line_sequence = int(next_seqs.min())
                st.session_state.show_translation = False
                st.rerun()

    with nav_col3:
        if is_last_line:
            if st.session_state.current_scenario_idx < len(scenarios) - 1:
                if st.button("🎉 Next Scenario", type="primary", use_container_width=True):
                    st.session_state.current_scenario_idx += 1
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
            else:
                st.balloons()
                st.success("🏆 Excellent work! You completed all the available scenarios in this pack!")
                if st.button("🔄 Restart Pack", use_container_width=True):
                    st.session_state.current_scenario_idx = 0
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
        else:
            st.button("Scenario Locked 🔒", disabled=True, use_container_width=True, 
                      help="Step through to the end of the current conversation line-by-line to unlock the next scenario block.")
else:
    st.info("Verify your setup configurations inside conversations.toml to load your data sets.")
