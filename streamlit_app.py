import streamlit as st
import pandas as pd
import toml
import os
import urllib.parse

# ----------------------------------------------------
# 1. CONFIGURATION & TOML SETUP
# ----------------------------------------------------
st.set_page_config(page_title="Scenario Walkthrough", page_icon="🗣️", layout="centered")

# 📱 RIGID 50/50 MOBILE VIEWPORT LOCK
st.html("""
    <style>
        /* Force single container row to fit side-by-side on all mobile screens */
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 12px !important;
            width: 100% !important;
        }
        [data-testid="column"] {
            flex: 1 1 50% !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        /* Tighten vertical rhythm spacing within each stacked column */
        [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] > div > div {
            gap: 12px !important;
        }
        /* Lock button styles from expanding or wrapping text line heights */
        .stButton > button {
            white-space: nowrap !important;
            word-break: keep-all !important;
            width: 100% !important;
        }
    </style>
""")

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
        
        required = ['scenario_name', 'conversation_id', 'sequence', 'speaker_tag', 'is_user', 'italian', 'english']
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"⚠️ **Column Alignment Error in Tab '{worksheet_name}'**")
            return pd.DataFrame()
            
        df['sequence'] = pd.to_numeric(df['sequence']).fillna(0).astype(int)
        df['conversation_id'] = pd.to_numeric(df['conversation_id']).fillna(1).astype(int)
        df['scenario_name'] = df['scenario_name'].fillna('').astype(str).str.strip()
        df['speaker_tag'] = df['speaker_tag'].fillna('').astype(str).str.strip()
        df['italian'] = df['italian'].fillna('').astype(str).str.strip()
        df['english'] = df['english'].fillna('').astype(str).str.strip()
        df['is_user'] = df['is_user'].fillna('FALSE').astype(str).str.strip().str.upper() == 'TRUE'
        
        return df.sort_values(by=['scenario_name', 'conversation_id', 'sequence']).reset_index(drop=True)
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

display_mode = st.sidebar.radio(
    "Prompt Language:",
    ["Italian First", "English first"]
)
target_first = "Italian" in display_mode

if not df_all.empty:
    scenario_counts = df_all.groupby('scenario_name')['conversation_id'].nunique().to_dict()
    unique_scenarios = sorted(list(scenario_counts.keys()))
    sidebar_labels = [f"{name} ({scenario_counts[name]})" for name in unique_scenarios]
    
    if 'current_scenario_idx' not in st.session_state or st.session_state.get('last_deck_id') != selected_id:
        st.session_state.current_scenario_idx = 0
        st.session_state.current_conversation_id = None
        st.session_state.current_line_sequence = 1
        st.session_state.show_translation = False
        st.session_state.last_deck_id = selected_id

    st.sidebar.write("---")
    selected_sidebar_label = st.sidebar.selectbox(
        "Available Scenarios:",
        sidebar_labels,
        index=st.session_state.current_scenario_idx,
        key="scenario_selector_widget"
    )
    
    new_idx = sidebar_labels.index(selected_sidebar_label)
    if new_idx != st.session_state.current_scenario_idx:
        st.session_state.current_scenario_idx = new_idx
        st.session_state.current_conversation_id = None
        st.session_state.current_line_sequence = 1
        st.session_state.show_translation = False

    current_scenario = unique_scenarios[st.session_state.current_scenario_idx]
    df_scenario = df_all[df_all['scenario_name'] == current_scenario].sort_values(['conversation_id', 'sequence']).reset_index(drop=True)
    
    available_conv_ids = sorted(df_scenario['conversation_id'].unique().tolist())
    if st.session_state.current_conversation_id not in available_conv_ids:
        st.session_state.current_conversation_id = available_conv_ids[0]

    df_current_conv = df_scenario[df_scenario['scenario_name'] == current_scenario]
    df_current_conv = df_current_conv[df_current_conv['conversation_id'] == st.session_state.current_conversation_id].sort_values('sequence').reset_index(drop=True)
    
    total_lines = len(df_current_conv)
    current_row = df_current_conv[df_current_conv['sequence'] == st.session_state.current_line_sequence]
    
    if current_row.empty and total_lines > 0:
        st.session_state.current_line_sequence = int(df_current_conv['sequence'].min())
        current_row = df_current_conv[df_current_conv['sequence'] == st.session_state.current_line_sequence]

# ----------------------------------------------------
    # 4. MAIN INTERFACE RENDERING
    # ----------------------------------------------------
    st.html(f"""
        <div style="margin-top: 10px; margin-bottom: 2px;">
            <span style="font-size: 24px; font-weight: 700; color: #202124; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">
                {current_scenario}
            </span>
        </div>
    """)
    
    current_conv_num = available_conv_ids.index(st.session_state.current_conversation_id) + 1
    total_convs_for_scenario = len(available_conv_ids)
    st.caption(f"Practicing conversation {current_conv_num} of {total_convs_for_scenario}")

    # Dialogue Display Window
    if not current_row.empty:
        row = current_row.iloc[0]
        
        speaker_name = str(row['speaker_tag'])
        is_user = bool(row['is_user'])
        
        user_suffix = " (You)" if is_user else ""
        full_speaker_label = f"**{speaker_name}{user_suffix}**"
        
        prompt_text = str(row['italian']) if target_first else str(row['english'])
        translation_text = str(row['english']) if target_first else str(row['italian'])
        
        st.markdown(full_speaker_label)
        
        with st.container(border=True):
            st.code(prompt_text, language="text", wrap_lines=True)
            
            if st.session_state.show_translation:
                st.markdown(f"*{translation_text}*")

    # ----------------------------------------------------
    # 5. FIXED MULTI-ROW CONTROLS (SINGLE HORIZONTAL ELEMENT)
    # ----------------------------------------------------
    min_seq = int(df_current_conv['sequence'].min())
    max_seq = int(df_current_conv['sequence'].max())
    
    is_first_line = (st.session_state.current_line_sequence == min_seq)
    is_last_line = (st.session_state.current_line_sequence == max_seq)

    st.write("") 
    
    # We use exactly one horizontal block to keep things strictly bounded within 100vw
    col_left, col_right = st.columns(2)

    with col_left:
        # Row 1, Left: Empty space block matching standard button height (42px)
        st.html('<div style="height: 42px;"></div>')
        
        # Row 2, Left: Previous button
        if st.button("⬅️ Previous", disabled=is_first_line, use_container_width=True):
            prev_seqs = df_current_conv[df_current_conv['sequence'] < st.session_state.current_line_sequence]['sequence']
            if not prev_seqs.empty:
                st.session_state.current_line_sequence = int(prev_seqs.max())
                st.session_state.show_translation = False
                st.rerun()

    with col_right:
        # Row 1, Right: Translate button
        if st.button("Translate", use_container_width=True):
            st.session_state.show_translation = not st.session_state.show_translation
            st.rerun()
            
        # Row 2, Right: Next button stack
        if is_last_line:
            current_conv_idx = available_conv_ids.index(st.session_state.current_conversation_id)
            
            if current_conv_idx < len(available_conv_ids) - 1:
                if st.button("Next conversation", type="primary", use_container_width=True):
                    st.session_state.current_conversation_id = available_conv_ids[current_conv_idx + 1]
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
            elif st.session_state.current_scenario_idx < len(unique_scenarios) - 1:
                if st.button("Next Topic ➡️", type="primary", use_container_width=True):
                    st.session_state.current_scenario_idx += 1
                    st.session_state.current_conversation_id = None
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
            else:
                st.balloons()
                st.success("🏆 Completed all setups!")
                if st.button("🔄 Restart", use_container_width=True):
                    st.session_state.current_scenario_idx = 0
                    st.session_state.current_conversation_id = None
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
        else:
            if st.button("Next", use_container_width=True):
                next_seqs = df_current_conv[df_current_conv['sequence'] > st.session_state.current_line_sequence]['sequence']
                if not next_seqs.empty:
                    st.session_state.current_line_sequence = int(next_seqs.min())
                    st.session_state.show_translation = False
                    st.rerun()
else:
    st.info("Verify your setup configurations inside conversations.toml to load your data sets.")
