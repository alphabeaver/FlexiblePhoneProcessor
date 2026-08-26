import csv
import io
import re
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Launch Control Template Converter",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

OUTPUT_COLUMNS = {
    'FirstName': {'required': True, 'description': 'Contact first name'},
    'LastName': {'required': True, 'description': 'Contact last name'},
    'Email': {'required': False, 'description': 'Email address (can be empty)'},
    'MailingAddress': {'required': False, 'description': 'Mailing street address'},
    'MailingCity': {'required': False, 'description': 'Mailing city'},
    'MailingState': {'required': False, 'description': 'Mailing state'},
    'MailingZip': {'required': False, 'description': 'Mailing zip code'},
    'PropertyAddress': {'required': False, 'description': 'Property street address'},
    'PropertyCity': {'required': False, 'description': 'Property city'},
    'PropertyState': {'required': False, 'description': 'Property state'},
    'PropertyZip': {'required': False, 'description': 'Property zip code'},
    'APN': {'required': False, 'description': 'Assessor Parcel Number'},
    'PropertyCounty': {'required': False, 'description': 'Property county'},
    'Acreage': {'required': False, 'description': 'Lot size in acres'},
}

PHONE_COLUMNS = ['Phone1', 'Phone2', 'Phone3']

# Launch Control template order: phones sit between the property block and APN.
FINAL_COLUMN_ORDER = [
    'FirstName', 'LastName', 'Email',
    'MailingAddress', 'MailingCity', 'MailingState', 'MailingZip',
    'PropertyAddress', 'PropertyCity', 'PropertyState', 'PropertyZip',
    'Phone1', 'Phone2', 'Phone3',
    'APN', 'PropertyCounty', 'Acreage',
]

MAX_PHONE_COLUMNS = 5

STATE_ABBREV = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI',
    'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY',
}
VALID_ABBREVS = set(STATE_ABBREV.values())


# ---------------------------------------------------------------- file loading

def is_csv_upload(uploaded_file):
    return str(uploaded_file.name).lower().endswith(('.csv', '.txt'))


def sniff_csv_settings(uploaded_file):
    """Work out a CSV's encoding and delimiter from its first chunk."""
    uploaded_file.seek(0)
    head = uploaded_file.read(64 * 1024)
    uploaded_file.seek(0)

    if isinstance(head, str):
        head = head.encode('utf-8')

    encoding = 'utf-8-sig'
    try:
        sample = head.decode('utf-8-sig')
    except UnicodeDecodeError:
        # Windows-authored broker exports are usually cp1252.
        encoding = 'cp1252'
        sample = head.decode('cp1252', errors='replace')

    try:
        sep = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
    except csv.Error:
        sep = ','

    return {'sep': sep, 'encoding': encoding}


def detect_header_row(uploaded_file, csv_settings=None, max_scan=25):
    """Find the first row that looks like a header row.

    Some broker exports put a fully blank row A above the real column titles;
    the first row carrying at least two non-empty cells is the header.
    """
    uploaded_file.seek(0)
    if csv_settings is not None:
        preview = pd.read_csv(
            uploaded_file, header=None, nrows=max_scan, dtype=str, **csv_settings
        )
    else:
        preview = pd.read_excel(uploaded_file, header=None, nrows=max_scan)

    for i in range(len(preview)):
        row = preview.iloc[i]
        filled = row.notna() & (row.astype(str).str.strip() != '')
        if filled.sum() >= 2:
            return i
    return 0


def load_table(uploaded_file):
    """Read an .xlsx/.xls/.csv upload, skipping blank leading rows."""
    csv_settings = sniff_csv_settings(uploaded_file) if is_csv_upload(uploaded_file) else None

    header_idx = detect_header_row(uploaded_file, csv_settings)

    uploaded_file.seek(0)
    if csv_settings is not None:
        df = pd.read_csv(
            uploaded_file, header=header_idx, low_memory=False, **csv_settings
        )
    else:
        df = pd.read_excel(uploaded_file, header=header_idx)

    df.columns = [str(c).strip() for c in df.columns]

    dead_cols = [
        c for c in df.columns
        if c.startswith('Unnamed:') and df[c].isna().all()
    ]
    if dead_cols:
        df = df.drop(columns=dead_cols)

    df = df.dropna(how='all').reset_index(drop=True)
    return df, header_idx


# ------------------------------------------------------------ phone extraction

def normalize_phone_series(series):
    """Vectorized 10-digit normalization for a whole column."""
    idx = series.index

    # Numeric path first: catches ints, floats and scientific notation cleanly.
    num = pd.to_numeric(series, errors='coerce')
    num = num.where((num >= 1e9) & (num < 1e12))

    digits = pd.Series('', index=idx, dtype=object)
    numeric_rows = num.notna()
    if numeric_rows.any():
        digits.loc[numeric_rows] = num[numeric_rows].round().astype('int64').astype(str)

    text_rows = ~numeric_rows
    if text_rows.any():
        digits.loc[text_rows] = (
            series[text_rows].fillna('').astype(str).str.replace(r'\D', '', regex=True)
        )

    lengths = digits.str.len()
    out = pd.Series('', index=idx, dtype=object)

    ten = lengths == 10
    out[ten] = digits[ten]

    eleven = (lengths == 11) & digits.str.startswith('1')
    out[eleven] = digits[eleven].str[1:]

    return out


def build_phone_frame(df, phone_cols):
    """Take the first 3 distinct valid numbers per row, in mapped order."""
    n = len(df)
    blank = pd.DataFrame(
        {c: pd.Series([''] * n, index=df.index, dtype=object) for c in PHONE_COLUMNS},
        index=df.index,
    )

    usable = [c for c in phone_cols if c in df.columns]
    if not usable or n == 0:
        return blank, {'total_valid': 0, 'rows_with_any': 0, 'duplicates_dropped': 0}

    normalized = [normalize_phone_series(df[c]) for c in usable]
    arr = np.column_stack([s.to_numpy(dtype=object) for s in normalized])

    total_valid = int((arr != '').sum())
    rows_with_any = int((arr != '').any(axis=1).sum())

    picked = np.empty((n, 3), dtype=object)
    picked[:] = ''
    duplicates_dropped = 0

    for i in range(n):
        seen = []
        for value in arr[i]:
            if not value:
                continue
            if value in seen:
                duplicates_dropped += 1
                continue
            seen.append(value)
            if len(seen) == 3:
                break
        for j, value in enumerate(seen):
            picked[i, j] = value

    frame = pd.DataFrame(picked, columns=PHONE_COLUMNS, index=df.index)
    return frame, {
        'total_valid': total_valid,
        'rows_with_any': rows_with_any,
        'duplicates_dropped': duplicates_dropped,
    }


# -------------------------------------------------------------- column mapping

def smart_column_suggestions(df_columns):
    """Suggest mappings from column names."""
    phone_patterns = {
        0: r'phone(?!\s*\()',
        1: r'alt.*phone.*1',
        2: r'alt.*phone.*2',
        3: r'alt.*phone.*3',
        4: r'alt.*phone.*4',
    }

    data_patterns = {
        'FirstName': [r'first.*name', r'owner.*1.*first', r'fname'],
        'LastName': [r'last.*name', r'owner.*1.*last', r'lname', r'surname'],
        'Email': [r'email', r'e.mail'],
        'MailingAddress': [r'mail.*address', r'mailing.*address'],
        'MailingCity': [r'mail.*city', r'mailing.*city'],
        'MailingState': [r'mail.*state', r'mailing.*state'],
        'MailingZip': [r'mail.*zip', r'mailing.*zip'],
        'PropertyAddress': [r'property.*address', r'parcel.*address', r'site.*address'],
        'PropertyCity': [r'property.*city', r'parcel.*city', r'site.*city'],
        'PropertyState': [r'property.*state', r'parcel.*state', r'site.*state'],
        'PropertyZip': [r'property.*zip', r'parcel.*zip', r'site.*zip'],
        'APN': [r'^apn$', r'parcel.*number', r'assessor.*parcel'],
        'PropertyCounty': [r'property.*county', r'parcel.*county', r'county'],
        'Acreage': [r'acre', r'lot.*acre', r'size.*acre'],
    }

    lowered = [(col, col.lower()) for col in df_columns]

    suggestions = {}
    for output_col, patterns in data_patterns.items():
        for pattern in patterns:
            match = next((col for col, low in lowered if re.search(pattern, low)), None)
            if match:
                suggestions[output_col] = match
                break

    phone_suggestions = {}
    for slot, pattern in phone_patterns.items():
        match = next((col for col, low in lowered if re.search(pattern, low)), None)
        if match:
            phone_suggestions[slot] = match

    return suggestions, phone_suggestions


def _default_index(columns, suggested):
    if suggested and suggested in columns:
        return columns.index(suggested) + 1
    return 0


def create_column_mapping_interface(df):
    """Render the mapping UI and return True when the mapping is usable."""
    st.markdown("## 🔄 Column Mapping")
    st.markdown("Map your file's columns to the Launch Control output format:")

    columns = df.columns.tolist()
    options = ['None'] + columns
    suggestions, phone_suggestions = smart_column_suggestions(columns)

    tab1, tab2 = st.tabs(["📋 Contact Data Mapping", "📞 Phone Number Mapping"])

    with tab1:
        st.markdown("### Contact Information Mapping")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Required Fields:**")
            for output_col, config in OUTPUT_COLUMNS.items():
                if not config['required']:
                    continue
                selected = st.selectbox(
                    f"{output_col} *",
                    options=options,
                    index=_default_index(columns, suggestions.get(output_col)),
                    help=config['description'],
                    key=f"mapping_{output_col}",
                )
                st.session_state.column_mapping[output_col] = (
                    selected if selected != 'None' else None
                )

        with col2:
            st.markdown("**Optional Fields:**")
            for output_col, config in OUTPUT_COLUMNS.items():
                if config['required']:
                    continue
                selected = st.selectbox(
                    output_col,
                    options=options,
                    index=_default_index(columns, suggestions.get(output_col)),
                    help=config['description'],
                    key=f"mapping_{output_col}",
                )
                st.session_state.column_mapping[output_col] = (
                    selected if selected != 'None' else None
                )

    with tab2:
        st.markdown("### Phone Number Mapping")
        st.markdown(
            f"Map up to {MAX_PHONE_COLUMNS} phone columns. The first 3 valid numbers "
            "per contact are exported, **in the order mapped below**, regardless of "
            "line type. Duplicate numbers are skipped."
        )

        mapping = []
        for i in range(MAX_PHONE_COLUMNS):
            selected = st.selectbox(
                f"Phone Column {i + 1}",
                options=options,
                index=_default_index(columns, phone_suggestions.get(i)),
                key=f"phone_col_{i}",
            )
            mapping.append(selected)

        st.session_state.phone_mapping = mapping
        st.info(
            "💡 Order matters — Phone Column 1 fills the Phone1 slot first, "
            "then 2, then 3."
        )

    missing_required = [
        field for field, config in OUTPUT_COLUMNS.items()
        if config['required'] and not st.session_state.column_mapping.get(field)
    ]
    if missing_required:
        st.error(f"⚠️ Missing required fields: {', '.join(missing_required)}")
        return False

    if not any(col != 'None' for col in st.session_state.phone_mapping):
        st.error("⚠️ At least one phone number column must be mapped")
        return False

    st.success("✅ Column mapping is complete!")
    return True


# ------------------------------------------------------------------ processing

def _clean_source_series(series):
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna('')
    return series.fillna('').astype(str).str.strip()


def build_output(df, column_mapping, phones_df):
    data = {}
    for output_col in FINAL_COLUMN_ORDER:
        if output_col in PHONE_COLUMNS:
            data[output_col] = phones_df[output_col]
            continue

        source_col = column_mapping.get(output_col)
        if source_col and source_col in df.columns:
            data[output_col] = _clean_source_series(df[source_col])
        else:
            data[output_col] = pd.Series([''] * len(df), index=df.index, dtype=object)

    final_df = pd.DataFrame(data, index=df.index)
    return final_df[FINAL_COLUMN_ORDER]


def apply_full_name_fallback(df, final_df):
    """Fall back to a 'full name' column when first and last are both blank."""
    full_name_col = next(
        (c for c in df.columns if 'full' in c.lower() and 'name' in c.lower()), None
    )
    if not full_name_col:
        return final_df

    blank = (final_df['FirstName'].astype(str) == '') & (
        final_df['LastName'].astype(str) == ''
    )
    if blank.any():
        final_df.loc[blank, 'FirstName'] = (
            df.loc[blank, full_name_col].fillna('').astype(str).str.strip()
        )
    return final_df


def generate_qa_report(original_df, final_df, phone_stats):
    rows = [
        ['Total Contacts in Original File', f"{len(original_df):,}"],
        ['Contacts in Output File', f"{len(final_df):,}"],
        [
            'Contact Count Verification',
            '✅ MATCH' if len(original_df) == len(final_df) else '❌ MISMATCH',
        ],
        ['', ''],
        ['Contacts with At Least One Phone', f"{phone_stats['rows_with_any']:,}"],
        ['Contacts with No Phone', f"{len(final_df) - phone_stats['rows_with_any']:,}"],
        ['Total Phone Numbers in Original Data', f"{phone_stats['total_valid']:,}"],
        ['Duplicate Numbers Skipped', f"{phone_stats['duplicates_dropped']:,}"],
        ['', ''],
        ['Phone Distribution in Output:', ''],
    ]
    for col in PHONE_COLUMNS:
        rows.append([f'Contacts with {col}', f"{int((final_df[col] != '').sum()):,}"])

    return pd.DataFrame(rows, columns=['QA CHECK', 'RESULT'])


def process_data_with_mapping(df, column_mapping, phone_mapping):
    progress = st.progress(0)
    status = st.empty()

    active_phone_cols = [c for c in phone_mapping if c != 'None']

    status.text("📞 Extracting the top 3 phone numbers per contact...")
    progress.progress(30)
    phones_df, phone_stats = build_phone_frame(df, active_phone_cols)

    status.text("📋 Formatting output data...")
    progress.progress(65)
    final_df = build_output(df, column_mapping, phones_df)
    final_df = apply_full_name_fallback(df, final_df)

    status.text("📊 Generating QA report...")
    progress.progress(85)
    qa_summary = generate_qa_report(df, final_df, phone_stats)

    progress.progress(100)
    status.text("✅ Processing complete!")

    return final_df, qa_summary


# -------------------------------------------------------------------- filenames

def _most_common_value(series):
    if series is None or len(series) == 0:
        return ''
    values = series.astype(str).str.strip()
    values = values[values != '']
    if values.empty:
        return ''
    return values.mode().iloc[0]


def to_state_abbrev(value):
    text = str(value).strip()
    if not text:
        return ''
    if len(text) == 2 and text.upper() in VALID_ABBREVS:
        return text.upper()
    return STATE_ABBREV.get(text.lower(), '')


def clean_county_name(value):
    text = str(value).strip()
    if not text:
        return ''
    text = re.sub(r'\b(county|parish|borough|census area)\b', '', text, flags=re.I)
    parts = re.findall(r'[A-Za-z0-9]+', text)
    return ''.join(part.capitalize() for part in parts)


def parse_from_filename(source_name):
    """Best-effort state and county recovery from the uploaded file's name."""
    stem = re.sub(r'\.(xlsx|xls|csv|txt)$', '', str(source_name or ''), flags=re.I)

    # Underscores are word characters, so \b will not separate "Colorado_Fremont".
    state = ''
    for name, abbrev in STATE_ABBREV.items():
        if re.search(rf'(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])', stem, flags=re.I):
            state = abbrev
            break
    if not state:
        for token in re.findall(r'(?<![A-Z])([A-Z]{2})(?![A-Za-z])', stem):
            if token in VALID_ABBREVS:
                state = token
                break

    county_match = re.search(r'([A-Za-z]+)[\s_-]*county', stem, flags=re.I)
    county = clean_county_name(county_match.group(1)) if county_match else ''

    return state, county


def suggest_filename(final_df, source_name):
    """LC + STATE + County + YY + MON, e.g. LCALLimestone26AUG."""
    state = to_state_abbrev(_most_common_value(final_df.get('PropertyState')))
    county = clean_county_name(_most_common_value(final_df.get('PropertyCounty')))

    if not state or not county:
        fallback_state, fallback_county = parse_from_filename(source_name)
        state = state or fallback_state
        county = county or fallback_county

    now = datetime.now()
    return f"LC{state}{county}{now.strftime('%y')}{now.strftime('%b').upper()}"


def sanitize_filename(name):
    cleaned = re.sub(r'[\\/:*?"<>|]', '', str(name)).strip()
    cleaned = re.sub(r'\.(xlsx|xls|csv|txt)$', '', cleaned, flags=re.I)
    return cleaned or 'LaunchControlExport'


def to_excel_bytes(df):
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return buffer.getvalue()


# ------------------------------------------------------------------------- app

def init_session_state():
    defaults = {
        'column_mapping': {},
        'phone_mapping': [],
        'file_id': None,
        'results': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_for_new_file(file_id):
    """Clear stale widget state so a new file's columns map cleanly."""
    stale = [
        k for k in st.session_state
        if k.startswith('mapping_') or k.startswith('phone_col_')
    ]
    for key in stale:
        del st.session_state[key]

    st.session_state.column_mapping = {}
    st.session_state.phone_mapping = []
    st.session_state.results = None
    st.session_state.file_id = file_id


def render_results(results):
    final_df = results['final_df']

    st.markdown("## 📊 Processing Results")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📱 Total Records", f"{len(final_df):,}")
    with col2:
        st.metric("Records with Phone1", f"{int((final_df['Phone1'] != '').sum()):,}")
    with col3:
        st.metric("Records with Phone2", f"{int((final_df['Phone2'] != '').sum()):,}")

    st.markdown("### 📋 QA Summary")
    st.dataframe(results['qa_summary'], use_container_width=True, hide_index=True)

    st.markdown("### 📥 Download File")
    st.caption(
        "Suggested name is LC + state + county + year + month. "
        "Edit it to add acreage or any other detail."
    )

    name = st.text_input(
        "File name",
        value=results['suggested_name'],
        key="download_filename",
        help="The .xlsx extension is added automatically.",
    )
    final_name = f"{sanitize_filename(name)}.xlsx"
    st.caption(f"Saving as **{final_name}**")

    st.download_button(
        label="📥 Download Launch Control File",
        data=results['excel_bytes'],
        file_name=final_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    with st.expander("📋 Output Preview"):
        st.dataframe(final_df.head(20), use_container_width=True)


def main():
    init_session_state()

    st.title("📞 Launch Control Template Converter")
    st.markdown(
        "Upload any broker export and convert it to the Launch Control import "
        "template with the top 3 phone numbers per contact."
    )

    with st.sidebar:
        st.header("⚙️ About This Tool")
        st.success("✅ Reads .xlsx, .xls and .csv exports")
        st.success("✅ Works with any broker's column names")
        st.success("✅ Skips a blank leading row automatically")
        st.success("✅ Takes the first 3 distinct phone numbers")
        st.success("✅ Suggests a standardized, editable file name")

    uploaded_file = st.file_uploader(
        "Choose an Excel or CSV file",
        type=['xlsx', 'xls', 'csv'],
        help="Upload any Excel or CSV file with contact and phone data",
    )

    if uploaded_file is None:
        st.session_state.file_id = None
        st.session_state.results = None
        st.info("👆 Please upload an Excel or CSV file to get started")
        with st.expander("📖 Instructions", expanded=True):
            st.markdown(
                """
                **How to use this converter:**

                1. Upload any Excel (.xlsx/.xls) or CSV export with contact and phone data
                2. Map your columns to the Launch Control fields
                3. Map your phone columns in priority order
                4. Process the file
                5. Adjust the suggested file name and download

                **What it does:**
                - Detects and skips a blank first row before the real headers
                - Auto-detects CSV delimiter and encoding
                - Keeps every contact row, one row in, one row out
                - Exports the first 3 distinct valid numbers per contact
                - Names the file `LC` + state + county + year + month
                """
            )
        return

    try:
        file_id = f"{uploaded_file.name}:{uploaded_file.size}"
        if st.session_state.file_id != file_id:
            reset_for_new_file(file_id)

        with st.spinner("📖 Loading file..."):
            df, header_idx = load_table(uploaded_file)

        st.success("✅ File loaded successfully!")
        if header_idx > 0:
            st.info(
                f"ℹ️ Skipped {header_idx} blank row(s) — using row {header_idx + 1} "
                "as the column headers."
            )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rows", f"{len(df):,}")
        with col2:
            st.metric("Total Columns", f"{len(df.columns):,}")
        with col3:
            st.metric("File Size", f"{uploaded_file.size / 1024 / 1024:.1f} MB")

        if df.empty:
            st.warning("⚠️ This file has headers but no data rows.")
            return

        with st.expander("📋 Data Preview"):
            st.dataframe(df.head(10), use_container_width=True)
            st.markdown("**Available Columns:** " + ", ".join(df.columns.tolist()))

        if not create_column_mapping_interface(df):
            return

        if st.button("🚀 Process File", type="primary", use_container_width=True):
            final_df, qa_summary = process_data_with_mapping(
                df,
                st.session_state.column_mapping,
                st.session_state.phone_mapping,
            )
            st.session_state.pop('download_filename', None)
            st.session_state.results = {
                'final_df': final_df,
                'qa_summary': qa_summary,
                'excel_bytes': to_excel_bytes(final_df),
                'suggested_name': suggest_filename(final_df, uploaded_file.name),
            }

        if st.session_state.results:
            render_results(st.session_state.results)

    except Exception as e:
        st.error(f"❌ Error processing file: {e}")
        with st.expander("Error Details"):
            st.exception(e)


if __name__ == "__main__":
    main()
