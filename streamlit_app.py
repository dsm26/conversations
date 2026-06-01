import streamlit as st
import pandas as pd
import toml
import os
import time
import urllib.parse
import streamlit.components.v1 as components

# Global Fallback Constants if configuration parameters are missing
DEFAULT_TARGET_CODE = "it-IT"
DEFAULT_TARGET_COL = "italian"
DEFAULT_NATIVE_COL = "english"

# Force structural layout optimization for mobile viewports
st.set_page_config(page_title="Scenario Walkthrough", page_icon="💡", layout="centered")

# ==============================================================================
# INDESTRUCTIBLE MOBILE GRID & TARGETED INTERFACE BLOCKS
# ==============================================================================
st.markdown(
    """
    <style>
    /* Target all variations of Streamlit horizontal column layouts */
    div[data-testid="stHorizontalBlock"], 
    .stHorizontalBlock, 
    div[data-fieldname="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important; /* Stop vertical stacking on phone screens */
        width: 100% !important;
        gap: 10px !important;
        align-items: center !important;
    }
    
    /* Force column items to split the row space precisely split without blowing out */
    div[data-testid="stHorizontalBlock"] > div,
    .stHorizontalBlock > div {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        width: 100% !important;
    }

    /* Keep button text content strictly bound from accidental wrapping */
    .stButton > button {
        white-space: nowrap !important;
        word-break: keep-all !important;
        width: 100% !important;
        height: 42px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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
# 2. DATA INGESTION (DYNAMIC EXTRACTION ENGINE)
# ----------------------------------------------------
def build_google_sheet_csv_url(spreadsheet_id, worksheet_name):
    """Constructs a direct CSV export URL using the Google Visualization API."""
    base_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
    encoded_worksheet = urllib.parse.quote(worksheet_name)
    return f"{base_url}?tqx=out:csv&sheet={encoded_worksheet}"

@st.cache_data(ttl=60)
def load_scenario_data(spreadsheet_id, worksheet_name, target_col, native_col):
    """Fetches, sanitizes, and verifies Google Sheet configurations agnostic of language types."""
    start_time = time.perf_counter()
    try:
        csv_url = build_google_sheet_csv_url(spreadsheet_id, worksheet_name)
        df = pd.read_csv(csv_url)
        
        df.columns = [c.strip().replace(' ', '_').lower() for c in df.columns]
        
        # Verify base alignment keys
        required = ['scenario_name', 'conversation_id', 'sequence', 'speaker_tag', 'is_user', target_col, native_col]
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"⚠️ **Column Alignment Error! Missing structural columns:** {missing}")
            return pd.DataFrame(), 0.0
            
        df['sequence'] = pd.to_numeric(df['sequence']).fillna(0).astype(int)
        df['conversation_id'] = pd.to_numeric(df['conversation_id']).fillna(1).astype(int)
        df['scenario_name'] = df['scenario_name'].fillna('').astype(str).str.strip()
        df['speaker_tag'] = df['speaker_tag'].fillna('').astype(str).str.strip()
        df[target_col] = df[target_col].fillna('').astype(str).str.strip()
        df[native_col] = df[native_col].fillna('').astype(str).str.strip()
        df['is_user'] = df['is_user'].fillna('FALSE').astype(str).str.strip().str.upper() == 'TRUE'
        
        elapsed_time = time.perf_counter() - start_time
        return df.sort_values(by=['scenario_name', 'conversation_id', 'sequence']).reset_index(drop=True), elapsed_time
    except Exception as e:
        st.error(f"Error loading worksheet '{worksheet_name}': {e}")
        return pd.DataFrame(), 0.0

# ----------------------------------------------------
# 3. SIDEBAR AND APP STATE INIT
# ----------------------------------------------------
st.sidebar.title("🎛️ App Settings")

if CONVERSATIONS_LIST:
    display_names = [item["display_name"] for item in CONVERSATIONS_LIST]
    selected_display = st.sidebar.selectbox("Select Scenario Pack", display_names)
    
    # Extract dynamic item configuration boundaries
    selected_config = next(item for item in CONVERSATIONS_LIST if item["display_name"] == selected_display)
    
    selected_id = selected_config["id"]
    target_lang_code = selected_config.get("target_lang_code", DEFAULT_TARGET_CODE)
    target_column = selected_config.get("target_column", DEFAULT_TARGET_COL).lower()
    native_column = selected_config.get("native_column", DEFAULT_NATIVE_COL).lower()
    
    # Read UI dynamic mode labels
    primary_label = selected_config.get("primary_mode_label", "Target Language First")
    secondary_label = selected_config.get("secondary_mode_label", "Native Language First")

    df_all, load_duration = load_scenario_data(
        selected_config["spreadsheet_id"], 
        selected_config["worksheet_name"],
        target_column,
        native_column
    )
else:
    df_all = pd.DataFrame()
    load_duration = 0.0
    selected_id = None
    target_lang_code = DEFAULT_TARGET_CODE
    target_column = DEFAULT_TARGET_COL
    native_column = DEFAULT_NATIVE_COL
    primary_label, secondary_label = "Target First", "Native First"

# Sidebar Sheet Reload button
if st.sidebar.button("Reload GoogleSheet"):
    st.cache_data.clear()
    st.rerun()

display_mode = st.sidebar.radio(
    "Prompt Language:",
    [primary_label, secondary_label]
)
target_first = display_mode == primary_label

# DYNAMIC SLOW PLAYBACK SPEED SLIDER
st.sidebar.write("---")
slow_speed_percent = st.sidebar.slider(
    "Slow Playback Speed:",
    min_value=10,
    max_value=90,
    value=30,
    step=5,
    format="%d%%"
)
slow_playback_rate = slow_speed_percent / 100.0

if not df_all.empty:
    scenario_counts = df_all.groupby('scenario_name')['conversation_id'].nunique().to_dict()
    unique_scenarios = sorted(list(scenario_counts.keys()))
    sidebar_labels = [f"{name} ({scenario_counts[name]})" for name in unique_scenarios]
    
    # Core Global State Initialization Block
    if 'current_scenario_idx' not in st.session_state or st.session_state.get('last_deck_id') != selected_id:
        st.session_state.current_scenario_idx = 0
        st.session_state.current_conversation_id = None
        st.session_state.current_line_sequence = 1
        st.session_state.show_translation = False
        st.session_state.last_deck_id = selected_id

    st.sidebar.write("---")
    
    # CALLBACK NAVIGATION STATE SYNC FIX
    def handle_scenario_jump():
        if "scenario_selector_widget" in st.session_state:
            chosen_label = st.session_state.scenario_selector_widget
            st.session_state.current_scenario_idx = sidebar_labels.index(chosen_label)
            st.session_state.current_conversation_id = None
            st.session_state.current_line_sequence = 1
            st.session_state.show_translation = False

    st.sidebar.selectbox(
        "Jump to scenario:",
        sidebar_labels,
        index=st.session_state.current_scenario_idx,
        key="scenario_selector_widget",
        on_change=handle_scenario_jump
    )

    st.sidebar.markdown("---")
    st.sidebar.metric(label="Data Fetch Time", value=f"{load_duration:.4f}s")
    st.sidebar.caption(f"Loaded {len(df_all)} total dialog segments.")

    current_scenario = unique_scenarios[st.session_state.current_scenario_idx]
    df_scenario = df_all[df_all['scenario_name'] == current_scenario].sort_values(['conversation_id', 'sequence']).reset_index(drop=True)
    
    available_conv_ids = sorted(df_scenario['conversation_id'].unique().tolist())
    if st.session_state.current_conversation_id not in available_conv_ids:
        st.session_state.current_conversation_id = available_conv_ids[0]

    df_current_conv = df_scenario[df_scenario['conversation_id'] == st.session_state.current_conversation_id].sort_values('sequence').reset_index(drop=True)
    
    total_lines = len(df_current_conv)
    current_row = df_current_conv[df_current_conv['sequence'] == st.session_state.current_line_sequence]
    
    if current_row.empty and total_lines > 0:
        st.session_state.current_line_sequence = int(df_current_conv['sequence'].min())
        current_row = df_current_conv[df_current_conv['sequence'] == st.session_state.current_line_sequence]

    min_seq = int(df_current_conv['sequence'].min())
    max_seq = int(df_current_conv['sequence'].max())
    
    is_first_line_of_conv = (st.session_state.current_line_sequence == min_seq)
    is_first_conv_of_topic = (available_conv_ids.index(st.session_state.current_conversation_id) == 0)
    is_last_line_of_conv = (st.session_state.current_line_sequence == max_seq)
    
    is_on_absolute_first_card_of_topic = is_first_line_of_conv and is_first_conv_of_topic

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
    st.caption(f"Conversation {current_conv_num} of {total_convs_for_scenario} | Line {st.session_state.current_line_sequence} of {total_lines}")

    if not current_row.empty:
        row = current_row.iloc[0]
        
        speaker_name = str(row['speaker_tag'])
        is_user = bool(row['is_user'])
        
        user_suffix = " (You)" if is_user else ""
        full_speaker_label = f"**{speaker_name}{user_suffix}**"
        
        prompt_text = str(row[target_column]) if target_first else str(row[native_column])
        translation_text = str(row[native_column]) if target_first else str(row[target_column])
        
        st.markdown(full_speaker_label)
        
        # Native fluid container eliminates clipping and light/dark theme bugs entirely
        with st.container(border=True):
            st.markdown(f"### {prompt_text}")
            if st.session_state.show_translation:
                st.markdown(f" :red[*{translation_text}*]")

    # ----------------------------------------------------
    # 5. INLINE AUDIO & TRANSLATE ROW CONTROL
    # ----------------------------------------------------
    safe_speech_text = str(row[target_column]).replace("'", "\\'") if not current_row.empty else ""
    
    top_actions_left, top_actions_right = st.columns(2)
    
    with top_actions_left:
        tts_html = f"""
        <div style="display: flex; justify-content: flex-start; align-items: center; gap: 25px; height: 44px; margin-top: 2px;">
            <button onclick="speakText({slow_playback_rate})" style="background: none; border: none; font-size: 28px; cursor: pointer; padding: 2px; touch-action: manipulation;" title="Slow Speed">🐢</button>
            <button onclick="speakText(0.85)" style="background: none; border: none; font-size: 28px; cursor: pointer; padding: 2px; touch-action: manipulation;" title="Normal Speed">🔊</button>
        </div>
        <script>
        function speakText(playbackRate) {{
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                var utterance = new SpeechSynthesisUtterance('{safe_speech_text}');
                utterance.lang = '{target_lang_code}';
                utterance.rate = playbackRate;
                window.speechSynthesis.speak(utterance);
            }}
        }}
        </script>
        """
        components.html(tts_html, height=44)
        
    with top_actions_right:
        if st.button("Translate", use_container_width=True):
            st.session_state.show_translation = not st.session_state.show_translation
            st.rerun()

    # ----------------------------------------------------
    # 6. DYNAMIC BACK / FORWARD NAVIGATION MATRIX
    # ----------------------------------------------------
    st.write("") 
    nav_left_col, nav_right_col = st.columns(2)

    with nav_left_col:
        if is_on_absolute_first_card_of_topic and st.session_state.current_scenario_idx == 0:
            st.button("Previous Topic", disabled=True, use_container_width=True)
            
        elif is_on_absolute_first_card_of_topic:
            if st.button("Previous Topic", use_container_width=True):
                st.session_state.current_scenario_idx -= 1
                prev_scenario = unique_scenarios[st.session_state.current_scenario_idx]
                df_prev_scen = df_all[df_all['scenario_name'] == prev_scenario]
                
                prev_available_convs = sorted(df_prev_scen['conversation_id'].unique().tolist())
                st.session_state.current_conversation_id = prev_available_convs[-1]
                
                df_prev_conv = df_prev_scen[df_prev_scen['conversation_id'] == st.session_state.current_conversation_id]
                st.session_state.current_line_sequence = int(df_prev_conv['sequence'].max())
                st.session_state.show_translation = False
                st.rerun()
                
        else:
            if st.button("Previous", use_container_width=True):
                if is_first_line_of_conv:
                    current_conv_idx = available_conv_ids.index(st.session_state.current_conversation_id)
                    st.session_state.current_conversation_id = available_conv_ids[current_conv_idx - 1]
                    df_back_conv = df_scenario[df_scenario['conversation_id'] == st.session_state.current_conversation_id]
                    st.session_state.current_line_sequence = int(df_back_conv['sequence'].max())
                else:
                    prev_seqs = df_current_conv[df_current_conv['sequence'] < st.session_state.current_line_sequence]['sequence']
                    st.session_state.current_line_sequence = int(prev_seqs.max())
                st.session_state.show_translation = False
                st.rerun()

    with nav_right_col:
        if is_last_line_of_conv:
            current_conv_idx = available_conv_ids.index(st.session_state.current_conversation_id)
            
            if current_conv_idx < len(available_conv_ids) - 1:
                if st.button("Next conversation", type="primary", use_container_width=True):
                    st.session_state.current_conversation_id = available_conv_ids[current_conv_idx + 1]
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
            elif st.session_state.current_scenario_idx < len(unique_scenarios) - 1:
                if st.button("Next Topic", type="primary", use_container_width=True):
                    st.session_state.current_scenario_idx += 1
                    st.session_state.current_conversation_id = None
                    st.session_state.current_line_sequence = 1
                    st.session_state.show_translation = False
                    st.rerun()
            else:
                st.balloons()
                st.success("🏆 Completed all setups!")
                if st.button("Restart", use_container_width=True):
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

    # ----------------------------------------------------
    # 7. MACRO CONVERSATION CONTEXT VIEWER BLOCK
    # ----------------------------------------------------
    st.markdown("---")
    show_full_context = st.toggle("Show Full conversation", value=False)
    
    if show_full_context:
        primary_col = target_column if target_first else native_column
        secondary_col = native_column if target_first else target_column
        
        primary_title = primary_label.split()[0] if primary_label else "Target"
        
        with st.container(border=True):
            st.markdown(f"#### {primary_title}")
            for idx, line in df_current_conv.iterrows():
                line_number = idx + 1
                is_current = (line['sequence'] == st.session_state.current_line_sequence)
                speaker = f"**{line['speaker_tag']}**"
                text_content = line[primary_col]
                
                if is_current:
                    st.markdown(f"{line_number}. {speaker}: :green[{text_content}]")
                else:
                    st.markdown(f"{line_number}. {speaker}: {text_content}")
                    
            st.markdown("---")
            
            st.markdown("#### Translation")
            for idx, line in df_current_conv.iterrows():
                line_number = idx + 1
                is_current = (line['sequence'] == st.session_state.current_line_sequence)
                speaker = f"**{line['speaker_tag']}**"
                text_content = line[secondary_col]
                
                if is_current:
                    st.markdown(f"{line_number}. {speaker}: :red[*{text_content}*]")
                else:
                    st.markdown(f"{line_number}. {speaker}: *{text_content}*")
else:
    st.info("Verify your setup configurations inside conversations.toml to load your data sets.")
