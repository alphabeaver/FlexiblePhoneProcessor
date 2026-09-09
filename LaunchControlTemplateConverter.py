import csv
import io
import re
import zipfile
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


def load_uploads(uploaded_files):
    """Read every upload, keeping one bad file from killing the whole batch."""
    loaded, empty, failed = [], [], []

    for uploaded_file in uploaded_files:
        try:
            df, header_idx = load_table(uploaded_file)
        except Exception as e:
            failed.append((uploaded_file.name, str(e)))
            continue

        if df.empty:
            empty.append(uploaded_file.name)
            continue

        loaded.append({
            'name': uploaded_file.name,
            'size': uploaded_file.size,
            'df': df,
            'header_idx': header_idx,
        })

    return loaded, empty, failed


def describe_column_differences(loaded):
    """Compare each file's columns against the first file's.

    The first upload is the template the mapping is built from; anything a later
    file is missing simply comes out blank for that file's rows.
    """
    canonical = list(loaded[0]['df'].columns)
    canonical_set = set(canonical)

    differences = []
    for item in loaded[1:]:
        cols = set(item['df'].columns)
        missing = [c for c in canonical if c not in cols]
        extra = [c for c in item['df'].columns if c not in canonical_set]
        if missing or extra:
            differences.append({'name': item['name'], 'missing': missing, 'extra': extra})

    return canonical, differences


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


def create_column_mapping_interface(df, file_count=1, template_name=None):
    """Render the mapping UI and return True when the mapping is usable.

    One mapping covers the whole batch — the column names come from the first
    upload and are applied to every file.
    """
    st.markdown("## 🔄 Column Mapping")
    if file_count > 1:
        st.markdown(
            f"Map the columns once — the same mapping is applied to all "
            f"**{file_count} files**. Column names are read from "
            f"**{template_name}**."
        )
    else:
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


def rows_with_a_phone(final_df):
    if final_df.empty:
        return 0
    return int((final_df[PHONE_COLUMNS] != '').any(axis=1).sum())


def generate_qa_report(per_file, final_df, duplicates_removed, deduped):
    source_rows = sum(item['source_rows'] for item in per_file)
    total_valid = sum(item['phone_stats']['total_valid'] for item in per_file)
    within_row_dupes = sum(item['phone_stats']['duplicates_dropped'] for item in per_file)
    with_phone = rows_with_a_phone(final_df)
    expected = source_rows - duplicates_removed

    rows = [['Files Processed', f"{len(per_file):,}"]] if len(per_file) > 1 else []
    rows += [
        ['Total Contacts in Source File(s)', f"{source_rows:,}"],
    ]
    if deduped:
        rows.append(['Duplicate Rows Removed Across Files', f"{duplicates_removed:,}"])
    rows += [
        ['Contacts in Output File', f"{len(final_df):,}"],
        [
            'Contact Count Verification',
            '✅ MATCH' if expected == len(final_df) else '❌ MISMATCH',
        ],
        ['', ''],
        ['Contacts with At Least One Phone', f"{with_phone:,}"],
        ['Contacts with No Phone', f"{len(final_df) - with_phone:,}"],
        ['Total Phone Numbers in Source Data', f"{total_valid:,}"],
        ['Duplicate Numbers Skipped', f"{within_row_dupes:,}"],
        ['', ''],
        ['Phone Distribution in Output:', ''],
    ]
    for col in PHONE_COLUMNS:
        rows.append([f'Contacts with {col}', f"{int((final_df[col] != '').sum()):,}"])

    return pd.DataFrame(rows, columns=['QA CHECK', 'RESULT'])


def generate_file_breakdown(per_file):
    rows = []
    for item in per_file:
        frame = item['final_df']
        rows.append({
            'File': item['name'],
            'Rows': f"{len(frame):,}",
            'With Phone': f"{rows_with_a_phone(frame):,}",
            'Phone1': f"{int((frame['Phone1'] != '').sum()):,}",
            'Phone2': f"{int((frame['Phone2'] != '').sum()):,}",
            'Phone3': f"{int((frame['Phone3'] != '').sum()):,}",
        })
    return pd.DataFrame(rows)


def process_one_frame(df, column_mapping, phone_mapping):
    active_phone_cols = [c for c in phone_mapping if c != 'None']
    phones_df, phone_stats = build_phone_frame(df, active_phone_cols)
    final_df = build_output(df, column_mapping, phones_df)
    final_df = apply_full_name_fallback(df, final_df)
    return final_df, phone_stats


def process_all_files(loaded, column_mapping, phone_mapping):
    """Run one mapping across every uploaded file."""
    progress = st.progress(0)
    status = st.empty()

    per_file = []
    for i, item in enumerate(loaded):
        status.text(f"📞 Processing {item['name']} ({i + 1} of {len(loaded)})...")
        final_df, phone_stats = process_one_frame(item['df'], column_mapping, phone_mapping)
        per_file.append({
            'name': item['name'],
            'source_rows': len(item['df']),
            'final_df': final_df,
            'phone_stats': phone_stats,
            'suggested_name': suggest_filename(final_df, item['name']),
        })
        progress.progress(int((i + 1) / len(loaded) * 90))

    status.text("📊 Generating QA report...")
    progress.progress(100)
    status.text("✅ Processing complete!")

    return per_file


def combine_outputs(per_file, drop_duplicates):
    """Stack every file's output into the single frame Launch Control imports."""
    combined = pd.concat(
        [item['final_df'] for item in per_file], ignore_index=True
    )

    if not drop_duplicates:
        return combined, 0

    before = len(combined)
    combined = combined.drop_duplicates().reset_index(drop=True)
    return combined, before - len(combined)


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


def unique_names(names, hints=None):
    """Keep zip entries distinct when files land on the same suggested name.

    Several pulls from one county all suggest the same LC name, so a collision
    falls back to the upload's own file name before resorting to a counter.
    """
    hints = hints or [''] * len(names)
    duplicated = {name for name in names if names.count(name) > 1}

    out, used = [], set()
    for name, hint in zip(names, hints):
        candidate = f"{name}_{hint}" if name in duplicated and hint else name
        final, suffix = candidate, 2
        while final in used:
            final = f"{candidate}_{suffix}"
            suffix += 1
        used.add(final)
        out.append(final)
    return out


def to_zip_bytes(per_file):
    """One .xlsx per upload, each under its own suggested Launch Control name."""
    names = unique_names(
        [sanitize_filename(item['suggested_name']) for item in per_file],
        [sanitize_filename(item['name']) for item in per_file],
    )
    entries = [f"{name}.xlsx" for name in names]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for entry, item in zip(entries, per_file):
            archive.writestr(entry, to_excel_bytes(item['final_df']))
    buffer.seek(0)
    return buffer.getvalue(), entries


# ------------------------------------------------------------------------- app

def init_session_state():
    defaults = {
        'column_mapping': {},
        'phone_mapping': [],
        'file_signature': None,
        'columns_signature': None,
        'loaded': None,
        'results': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_mapping_widgets():
    """Clear stale widget state so a new column layout maps cleanly.

    Only called when the column names change — adding another file that shares
    the template keeps the mapping already on screen.
    """
    stale = [
        k for k in st.session_state
        if k.startswith('mapping_') or k.startswith('phone_col_')
    ]
    for key in stale:
        del st.session_state[key]

    st.session_state.column_mapping = {}
    st.session_state.phone_mapping = []


def render_results(results):
    final_df = results['combined_df']
    per_file = results['per_file']
    separate = results['output_mode'] == 'separate'

    st.markdown("## 📊 Processing Results")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📁 Files", f"{len(per_file):,}")
    with col2:
        st.metric("📱 Total Records", f"{len(final_df):,}")
    with col3:
        st.metric("Records with Phone1", f"{int((final_df['Phone1'] != '').sum()):,}")
    with col4:
        st.metric("Records with Phone2", f"{int((final_df['Phone2'] != '').sum()):,}")

    if results['duplicates_removed']:
        st.info(
            f"🧹 Removed {results['duplicates_removed']:,} duplicate row(s) that "
            "appeared in more than one file."
        )

    if results['file_breakdown'] is not None:
        st.markdown("### 📁 Per-File Breakdown")
        st.dataframe(
            results['file_breakdown'], use_container_width=True, hide_index=True
        )

    st.markdown("### 📋 QA Summary")
    st.dataframe(results['qa_summary'], use_container_width=True, hide_index=True)

    if separate:
        st.markdown("### 📥 Download Files")
        st.caption(
            "Each upload is exported as its own .xlsx inside the zip, named "
            "LC + state + county + year + month. The name below is the zip's."
        )
        extension, mime, label = '.zip', 'application/zip', '📥 Download Zip of Files'
    else:
        st.markdown("### 📥 Download File")
        st.caption(
            "Suggested name is LC + state + county + year + month. "
            "Edit it to add acreage or any other detail."
        )
        extension = '.xlsx'
        mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        label = '📥 Download Launch Control File'

    name = st.text_input(
        "File name",
        value=results['suggested_name'],
        key="download_filename",
        help=f"The {extension} extension is added automatically.",
    )
    final_name = f"{sanitize_filename(name)}{extension}"
    st.caption(f"Saving as **{final_name}**")

    st.download_button(
        label=label,
        data=results['download_bytes'],
        file_name=final_name,
        mime=mime,
        use_container_width=True,
    )

    if separate:
        with st.expander("📦 Files in the Zip"):
            for entry in results['zip_entries']:
                st.markdown(f"- `{entry}`")

    with st.expander("📋 Output Preview"):
        st.dataframe(final_df.head(20), use_container_width=True)


def main():
    init_session_state()

    st.title("📞 Launch Control Template Converter")
    st.markdown(
        "Upload one or more broker exports that share the same template and "
        "convert them to the Launch Control import format with the top 3 phone "
        "numbers per contact."
    )

    with st.sidebar:
        st.header("⚙️ About This Tool")
        st.success("✅ Reads .xlsx, .xls and .csv exports")
        st.success("✅ Converts many files at once with one mapping")
        st.success("✅ Works with any broker's column names")
        st.success("✅ Skips a blank leading row automatically")
        st.success("✅ Takes the first 3 distinct phone numbers")
        st.success("✅ Suggests a standardized, editable file name")

    uploaded_files = st.file_uploader(
        "Choose Excel or CSV files",
        type=['xlsx', 'xls', 'csv'],
        accept_multiple_files=True,
        help="Upload one or more files that share the same column layout",
    )

    if not uploaded_files:
        st.session_state.file_signature = None
        st.session_state.columns_signature = None
        st.session_state.loaded = None
        st.session_state.results = None
        st.info("👆 Please upload one or more Excel or CSV files to get started")
        with st.expander("📖 Instructions", expanded=True):
            st.markdown(
                """
                **How to use this converter:**

                1. Upload one or more Excel (.xlsx/.xls) or CSV exports with contact
                   and phone data — pull them from the same source so they share a
                   column layout
                2. Map your columns to the Launch Control fields — the mapping is
                   read from the first file and applied to all of them
                3. Map your phone columns in priority order
                4. Choose one combined file or one file per upload
                5. Process, adjust the suggested file name and download

                **What it does:**
                - Detects and skips a blank first row before the real headers
                - Auto-detects CSV delimiter and encoding
                - Keeps every contact row, one row in, one row out
                - Exports the first 3 distinct valid numbers per contact
                - Flags any file whose columns don't match the first one
                - Names the file `LC` + state + county + year + month
                """
            )
        return

    try:
        file_signature = tuple(sorted((f.name, f.size) for f in uploaded_files))
        if st.session_state.file_signature != file_signature:
            with st.spinner(f"📖 Loading {len(uploaded_files)} file(s)..."):
                st.session_state.loaded = load_uploads(uploaded_files)
            st.session_state.file_signature = file_signature
            st.session_state.results = None

        loaded, empty, failed = st.session_state.loaded

        for name, message in failed:
            st.error(f"❌ Could not read **{name}**: {message}")
        for name in empty:
            st.warning(f"⚠️ **{name}** has headers but no data rows — skipped.")

        if not loaded:
            st.error("❌ None of the uploaded files had readable data rows.")
            return

        st.success(f"✅ Loaded {len(loaded)} file(s) successfully!")

        skipped_rows = [item for item in loaded if item['header_idx'] > 0]
        if skipped_rows:
            st.info(
                "ℹ️ Skipped blank leading row(s) in: "
                + ", ".join(
                    f"{item['name']} (row {item['header_idx'] + 1} used as headers)"
                    for item in skipped_rows
                )
            )

        canonical_columns, differences = describe_column_differences(loaded)

        columns_signature = tuple(canonical_columns)
        if st.session_state.columns_signature != columns_signature:
            reset_mapping_widgets()
            st.session_state.columns_signature = columns_signature
            st.session_state.results = None

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Files", f"{len(loaded):,}")
        with col2:
            st.metric("Total Rows", f"{sum(len(i['df']) for i in loaded):,}")
        with col3:
            st.metric("Total Columns", f"{len(canonical_columns):,}")
        with col4:
            total_size = sum(i['size'] for i in loaded)
            st.metric("Total Size", f"{total_size / 1024 / 1024:.1f} MB")

        if differences:
            st.warning(
                f"⚠️ {len(differences)} file(s) don't match the column layout of "
                f"**{loaded[0]['name']}**. The mapping below is built from that "
                "file — any mapped column a file is missing comes out blank for "
                "its rows."
            )
            with st.expander("Show column differences"):
                for diff in differences:
                    st.markdown(f"**{diff['name']}**")
                    if diff['missing']:
                        st.markdown("- Missing: " + ", ".join(diff['missing']))
                    if diff['extra']:
                        st.markdown("- Extra: " + ", ".join(diff['extra']))

        with st.expander("📋 Data Preview"):
            index = 0
            if len(loaded) > 1:
                index = st.selectbox(
                    "Preview file",
                    options=list(range(len(loaded))),
                    format_func=lambda i: loaded[i]['name'],
                    key="preview_file",
                )
            preview_df = loaded[index]['df']
            st.dataframe(preview_df.head(10), use_container_width=True)
            st.markdown(
                "**Available Columns:** " + ", ".join(preview_df.columns.tolist())
            )

        if not create_column_mapping_interface(
            loaded[0]['df'], len(loaded), loaded[0]['name']
        ):
            return

        output_mode = 'combined'
        drop_dupes = False
        if len(loaded) > 1:
            st.markdown("## 📦 Output")
            output_mode = st.radio(
                "How should these files be exported?",
                options=['combined', 'separate'],
                format_func=lambda v: (
                    'One combined file' if v == 'combined'
                    else 'One file per upload (.zip)'
                ),
                horizontal=True,
                key="output_mode",
            )
            if output_mode == 'combined':
                drop_dupes = st.checkbox(
                    "Remove exact duplicate rows across files",
                    value=True,
                    key="drop_dupes",
                    help=(
                        "Catches the same list uploaded twice. A row is only "
                        "dropped when every output column matches another row."
                    ),
                )

        # Results are built for one set of output settings; changing them makes
        # the download on screen stale, so drop it and ask for a re-run.
        results = st.session_state.results
        if results and (
            results['output_mode'] != output_mode
            or results['dedupe_enabled'] != drop_dupes
        ):
            st.session_state.results = None

        button_label = "🚀 Process File" if len(loaded) == 1 else "🚀 Process Files"
        if st.button(button_label, type="primary", use_container_width=True):
            per_file = process_all_files(
                loaded,
                st.session_state.column_mapping,
                st.session_state.phone_mapping,
            )
            combined, duplicates_removed = combine_outputs(per_file, drop_dupes)

            if output_mode == 'separate':
                download_bytes, zip_entries = to_zip_bytes(per_file)
            else:
                download_bytes, zip_entries = to_excel_bytes(combined), []

            st.session_state.pop('download_filename', None)
            st.session_state.results = {
                'per_file': per_file,
                'combined_df': combined,
                'duplicates_removed': duplicates_removed,
                'qa_summary': generate_qa_report(
                    per_file, combined, duplicates_removed, drop_dupes
                ),
                'file_breakdown': (
                    generate_file_breakdown(per_file) if len(per_file) > 1 else None
                ),
                'output_mode': output_mode,
                'dedupe_enabled': drop_dupes,
                'download_bytes': download_bytes,
                'zip_entries': zip_entries,
                'suggested_name': suggest_filename(combined, loaded[0]['name']),
            }

        if st.session_state.results:
            render_results(st.session_state.results)

    except Exception as e:
        st.error(f"❌ Error processing files: {e}")
        with st.expander("Error Details"):
            st.exception(e)


if __name__ == "__main__":
    main()
