import streamlit as st
import pandas as pd
import re

# ----------------------------------------------------
# 1. CONFIGURATION & APP SETUP
# ----------------------------------------------------
st.set_page_config(page_title="Scenario Walkthrough", page_icon="🗣️", layout="centered")

# Dictionary of your Google Sheets. Add or modify sources here.
# Ensure the sheets are set to "Anyone with the link can view".
SHEETS_CONFIG = {
    "🇮🇹 Italian Travel Essentials": "https://docs.google.com/spreadsheets/d/1Xxxxxxx_ExampleLink1/edit?usp=sharing",
    "☕ Cafe & Restaurant Special Pack": "https://docs.google.com/spreadsheets/d/1Yyyyyyy_ExampleLink2/edit?usp=sharing"
}

# ----------------------------------------------------
# 2. HELPER FUNCTIONS
# ----------------------------------------------------
def Google_sheet_to_csv_url(url):
    """Converts a standard Google Sheets sharing URL into a direct CSV export URL."""
    match = re.search(r"docs\.google\.com/spreadsheets/d/([^/]+)", url)
    if match:
        spreadsheet_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
    return url

@st.cache_data(ttl=300)  # Caches sheet data for 5 minutes
def load_scenario_data(sheet_url):
    """Fetches data from Google Sheets, cleans column spaces, and sorts by sequence."""
    try:
        csv_url = google_sheet_to_csv_url(sheet_url)
        df = pd.read_csv(csv_url)
        # Standardize column naming rules
        df.columns = [c.strip().replace(' ', '_').lower() for c in df.columns]
        
        # Validate critical columns
        required = ['scenario_name', 'sequence', 'speaker_tag', 'is_user', 'italian', 'english']
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"Missing columns in Google Sheet: {missing}")
            return pd.DataFrame()
            
        df['sequence'] = pd.to_numeric(df['sequence']).astype(int)
        return df.sort_values(by=['scenario_name', 'sequence']).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# ----------------------------------------------------
# 3. SIDEBAR AND APP STATE INIT
# ----------------------------------------------------
st.sidebar.title("🎛️ App Settings")

selected_sheet_name = st.sidebar.selectbox("Select Scenario Pack", list(SHEETS_CONFIG.keys()))
raw_url = SHEETS_CONFIG[selected_sheet_name]
df_all = load_scenario_data(raw_url)

# Language Toggle Mode
display_mode = st.sidebar.radio(
    "Prompt Language:",
    ["Target Language First (Italian ➡️ English)", "Native Language First (English ➡️ Italian)"]
)
target_first = "Italian" in display_mode

if not df_all.empty():
    scenarios = df_all['scenario_name'].unique().tolist()
    
    # Initialize session tracking states
    if 'current_scenario_idx' not in st.session_state or st.session_state.get('last_sheet') != selected_sheet_name:
        st.session_state.current_scenario_idx = 0
        st.session_state.current_line_sequence = 1
        st.session_state.show_translation = False
        st.session_state.last_sheet = selected_sheet_name

    # Filter data down to the actively selected scenario
    current_scenario = scenarios[st.session_state.current_scenario_idx]
    df_scenario = df_all[df_all['scenario_name'] == current_scenario].sort_values('sequence').reset_index(drop=True)
    
    total_lines = len(df_scenario)
    current_row = df_scenario[df_scenario['sequence'] == st.session_state.current_line_sequence]
    
    if current_row.empty and total_lines > 0:
        # Fallback safeguard if sequence markers get desynced
        st.session_state.current_line_sequence = int(df_scenario['sequence'].min())
        current_row = df_scenario[df_scenario['sequence'] == st.session_state.current_line_sequence]

    # ----------------------------------------------------
    # 4. MAIN INTERFACE RENDERING
    # ----------------------------------------------------
    st.title("🗣️ Scenario Walkthrough")
    st.caption(f"Currently practicing Pack: **{selected_sheet_name}**")
    
    # Scenario Progress Header Card
    with st.container(border=True):
        col_scen_left, col_scen_right = st.columns([3, 1])
        with col_scen_left:
            st.subheader(f"🎬 Scenario: {current_scenario}")
            # Display metadata if available in columns
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
        
        # Establish language roles based on configuration selection
        prompt_text = row['italian'] if target_first else row['english']
        translation_text = row['english'] if target_first else row['italian']
        
        # Clean alignment cues depending on whether it is a User prompt or an NPC response
        alignment = "right" if is_user else "left"
        bg_color = "#e8f0fe" if is_user else "#f1f3f4"
        text_color = "#1a73e8" if is_user else "#3c4043"
        
        # Structural HTML injection for Chat-Bubble Experience
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
        
        # Display translation when triggered
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
    # Line sequence coordinates within the active scenario block
    min_seq = int(df_scenario['sequence'].min())
    max_seq = int(df_scenario['sequence'].max())
    
    is_first_line = (st.session_state.current_line_sequence == min_seq)
    is_last_line = (st.session_state.current_line_sequence == max_seq)

    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])

    with nav_col1:
        # Step back sequentially within current scenario block
        if st.button("⬅️ Previous Line", disabled=is_first_line, use_container_width=True):
            # Locate previous sequential element tracking backward cleanly
            prev_seqs = df_scenario[df_scenario['sequence'] < st.session_state.current_line_sequence]['sequence']
            if not prev_seqs.empty:
                st.session_state.current_line_sequence = int(prev_seqs.max())
                st.session_state.show_translation = False
                st.rerun()

    with nav_col2:
        # Step forward sequentially within current scenario block
        if st.button("Next Line ➡️", disabled=is_last_line, use_container_width=True):
            next_seqs = df_scenario[df_scenario['sequence'] > st.session_state.current_line_sequence]['sequence']
            if not next_seqs.empty:
                st.session_state.current_line_sequence = int(next_seqs.min())
                st.session_state.show_translation = False
                st.rerun()

    with nav_col3:
        # Scenario completion step: advances to the next available block
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
            # Enforce execution barrier: users must finish tracking the entire dialog before proceeding
            st.button("Scenario Locked 🔒", disabled=True, use_container_width=True, 
                      help="Step through to the end of the current conversation line-by-line to unlock the next scenario block.")
else:
    st.info("Please verify your data file setup configuration properties to safely initialize your workbook instances.")
