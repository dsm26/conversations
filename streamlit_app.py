import streamlit as st
import streamlit.components.v1 as components
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
    """
    Constructs a direct CSV export URL using the Google Visualization API.
    This query structure properly honors text-based worksheet tab names (like 'Conversations').
    """
    base_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
    encoded_worksheet = urllib.parse.quote(worksheet_name)
    return f"{base_url}?tqx=out:csv&sheet={encoded_worksheet}"

@st.cache_data(ttl=60)  # Low cache limit (1 min) to easily track structural changes
def load_scenario_data(spreadsheet_id, worksheet_name):
    """Fetches data from a specific Google Sheet tab, normalizes headers, and validates row contents."""
    try:
        csv_url = build_google_sheet_csv_url(spreadsheet_id, worksheet_name)
        df = pd.read_csv(csv_url)
        
        # Normalize column names: strip spaces, replace inner spaces with underscores, force lowercase
        df.columns = [c.strip().replace(' ', '_').lower() for c in df.columns]
        
        # Code validation checks for normalized names
        required = ['scenario_name', 'sequence', 'speaker_tag', 'is_user', 'italian', 'english']
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"⚠️ **Column Alignment Error in Tab '{worksheet_name}'**")
            st.info(f"**Expected Columns:** {required}\n\n**Actual Columns Found (Cleaned):** {list(df.columns)}")
            return pd.DataFrame()
            
        # 🔍 STRICT LINE-BY-LINE DATA CLEANING & VALIDATION
        for idx, row in df.iterrows():
            sheet_row_num = idx + 2  
            try:
                # 1. Sequence Verification
                if pd.isna(row['sequence']):
                    raise ValueError("The 'Sequence' column value is empty or missing.")
                try:
                    float(row['sequence'])
                except ValueError:
                    raise ValueError(f"The 'Sequence' value '{row['sequence']}' is text. It must be an integer.")
                
                # 2. Text Integrity Check
                for field in ['scenario_name', 'speaker_tag', 'italian', 'english']:
                    if pd.isna(row[field]) or str(row[field]).strip() == "":
                        raise ValueError(f"The '{field.replace('_', ' ').title()}' column value is unreadable or blank.")
                
                # 3. Boolean Role Guard
                if pd.isna(row['is_user']) or str(row['is_user']).strip() == "":
                    raise ValueError("The 'Is User' column value is blank. It must be TRUE or FALSE.")

            except Exception as row_error:
                st.error(f"❌ **Spreadsheet Data Error on Row {sheet_row_num}**")
                st.warning(f"**Underlying Parser Error:** {row_error}")
                st.info("Please verify this row in your Google Sheet. The app will refresh automatically when updated.")
                return pd.DataFrame()

        # Secure Type Sanitization
        df['sequence'] = pd.to_numeric(df['sequence']).astype(int)
        df['scenario_name'] = df['scenario_name'].astype(str).str.strip()
        df['speaker_tag'] = df['speaker_tag'].astype(str).str.strip()
        df['italian'] = df['italian'].astype(str).str.strip()
        df['english'] = df['english'].astype(str).str.strip()
        
        # Enforce clean boolean matching down the dataframe
        df['is_user'] = df['is_user'].astype(str).str.strip().str.upper() == 'TRUE'
        
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
        
        speaker_name = str(row['speaker_tag']).replace('"', '&quot;').replace("'", "&#39;")
        is_user = bool(row['is_user'])
        
        user_suffix = " (You)" if is_user else ""
        full_speaker_label = f"{speaker_name}{user_suffix}"
        
        raw_prompt = str(row['italian']) if target_first else str(row['english'])
        raw_translation = str(row['english']) if target_first else str(row['italian'])
        
        prompt_text = raw_prompt.replace('"', '&quot;').replace("'", "&#39;")
        translation_text = raw_translation.replace('"', '&quot;').replace("'", "&#39;")
        
        alignment = "right" if is_user else "left"
        bg_color = "#e8f0fe" if is_user else "#f1f3f4"
        text_color = "#1a73e8" if is_user else "#3c4043"
        
        # Calculate dynamic rendering height based on text footprint to prevent native iframe scrollbars
        estimated_height = max(110, 85 + (len(prompt_text) // 50) * 25)
        
        chat_html = f"""
        <div style="text-align: {alignment}; margin-bottom: 10px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; direction: ltr;">
            <span style="font-size: 13px; font-weight: bold; color: #5f6368; display: block; margin-bottom: 5px; padding-left: 5px; padding-right: 5px;">
                {full_speaker_label}
            </span>
            <div style="display: inline-block; padding: 14px 20px; background-color: {bg_color}; 
                        border-radius: 15px; max-width: 80%; text-align: left; 
                        box-shadow: 0 1px 2px rgba(0,0,0,0.1); border: 1px solid rgba(0,0,0,0.05);">
                <p style="font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 20px; margin: 0; color: {text_color}; font-weight: 500; letter-spacing: 0.5px; line-height: 1.4; white-space: pre-wrap; word-break: break-word;">
                    {prompt_text}
                </p>
            </div>
        </div>
        """
        
        # Render bubble securely using native HTML components
        components.html(chat_html, height=estimated_height, scrolling=False)

        # Translation/Reveal Panel Card
        col_space, col_btn_reveal, col_cb = st.columns([1, 2, 2])
        with col_btn_reveal:
            if st.button("👁️ Show Answer / Translation", use_container_width=True):
                st.session_state.show_translation = not st.session_state.show_translation
        
        if st.session_state.show_translation:
            est_trans_height = max(90, 65 + (len(translation_text) // 60) * 25)
            translation_html = f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-left: 5px solid #34a853; 
                        border-radius: 4px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; direction: ltr;">
                <strong style="color: #202124; font-size: 14px;">Translation:</strong>
                <p style="font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 18px; margin: 5px 0 0 0; color: #3c4043; font-style: italic; white-space: pre-wrap; word-break: break-word;">
                    {translation_text}
                </p>
            </div>
            """
            components.html(translation_html, height=est_trans_height, scrolling=False)

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
