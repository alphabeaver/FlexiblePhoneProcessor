import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
import io

# Set page config
st.set_page_config(
    page_title="Flexible Phone Data Processor", 
    page_icon="📞", 
    layout="wide"
)

# ---------- CONFIGURATION ----------
# Define the required output columns and their purposes
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
    'Acreage': {'required': False, 'description': 'Lot size in acres'}
}

# Phone types configuration
ALLOWED_TYPES = ['mobile', 'voip', 'cellular', 'cell']
LANDLINE_TYPES = ['landline', 'pager', 'specialservice', 'special service', 'wireline']

# ---------- SESSION STATE INITIALIZATION ----------
if 'df' not in st.session_state:
    st.session_state.df = None
if 'column_mapping' not in st.session_state:
    st.session_state.column_mapping = {}
if 'phone_mapping' not in st.session_state:
    st.session_state.phone_mapping = []
if 'mapping_complete' not in st.session_state:
    st.session_state.mapping_complete = False

# ---------- HELPER FUNCTIONS ----------
def normalize_phone(phone):
    """Normalize phone number to 10-digit format"""
    if pd.isnull(phone) or phone == '':
        return None
    
    if isinstance(phone, float):
        try:
            phone = int(phone)
        except (ValueError, OverflowError):
            return None
    
    digits = re.sub(r'\D', '', str(phone))
    
    if len(digits) == 10:
        return digits
    elif len(digits) == 11 and digits.startswith('1'):
        return digits[1:]
    else:
        return None

def extract_valid_phones_flexible(row, phone_mappings):
    """Extract valid phones based on flexible column mapping"""
    valid_phones = []
    
    for phone_col, type_col in phone_mappings:
        if phone_col == 'None' or type_col == 'None':
            continue
            
        phone = normalize_phone(row.get(phone_col))
        phone_type = str(row.get(type_col, '')).strip().lower() if pd.notnull(row.get(type_col)) else ''
        
        if phone and phone_type in ALLOWED_TYPES:
            valid_phones.append(phone)
        if len(valid_phones) == 3:
            break
    
    result = valid_phones + [None] * (3 - len(valid_phones))
    return pd.Series(result, index=['Phone1', 'Phone2', 'Phone3'])

def extract_landlines_flexible(row, phone_mappings):
    """Extract landlines based on flexible column mapping"""
    landlines = []
    phone_types = []
    
    for phone_col, type_col in phone_mappings:
        if phone_col == 'None' or type_col == 'None':
            continue
            
        phone = normalize_phone(row.get(phone_col))
        phone_type = str(row.get(type_col, '')).strip() if pd.notnull(row.get(type_col)) else ''
        
        if phone and phone_type.lower() in LANDLINE_TYPES:
            landlines.append(phone)
            phone_types.append(phone_type)
        if len(landlines) == 5:
            break
    
    result_phones = landlines + [None] * (5 - len(landlines))
    result_types = phone_types + [None] * (5 - len(phone_types))
    
    return pd.Series(
        result_phones + result_types, 
        index=['Phone1', 'Phone2', 'Phone3', 'Phone4', 'Phone5', 
               'Phone1_Type', 'Phone2_Type', 'Phone3_Type', 'Phone4_Type', 'Phone5_Type']
    )

def has_valid_phones_flexible(row, phone_mappings):
    """Check if row has valid phones based on flexible mapping"""
    for phone_col, type_col in phone_mappings:
        if phone_col == 'None' or type_col == 'None':
            continue
            
        phone = normalize_phone(row.get(phone_col))
        phone_type = str(row.get(type_col, '')).strip().lower() if pd.notnull(row.get(type_col)) else ''
        
        if phone and phone_type in ALLOWED_TYPES:
            return True
    return False

def smart_column_suggestions(df_columns):
    """Suggest column mappings based on column names"""
    suggestions = {}
    
    # Phone column patterns
    phone_patterns = {
        'phone': r'phone(?!\s*\()',
        'alt_phone_1': r'alt.*phone.*1',
        'alt_phone_2': r'alt.*phone.*2',
        'alt_phone_3': r'alt.*phone.*3',
        'alt_phone_4': r'alt.*phone.*4',
        'alt_phone_5': r'alt.*phone.*5'
    }
    
    phone_type_patterns = {
        'phone_type': r'phone.*\(.*type\)|phone.*line.*type',
        'alt_phone_1_type': r'alt.*phone.*1.*\(.*type\)|alt.*phone.*1.*line.*type',
        'alt_phone_2_type': r'alt.*phone.*2.*\(.*type\)|alt.*phone.*2.*line.*type',
        'alt_phone_3_type': r'alt.*phone.*3.*\(.*type\)|alt.*phone.*3.*line.*type',
        'alt_phone_4_type': r'alt.*phone.*4.*\(.*type\)|alt.*phone.*4.*line.*type',
        'alt_phone_5_type': r'alt.*phone.*5.*\(.*type\)|alt.*phone.*5.*line.*type'
    }
    
    # Data column patterns
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
        'PropertyCounty': [r'county', r'property.*county', r'parcel.*county'],
        'Acreage': [r'acre', r'lot.*acre', r'size.*acre']
    }
    
    # Find phone columns
    phone_suggestions = {}
    for pattern_name, pattern in phone_patterns.items():
        for col in df_columns:
            if re.search(pattern, col.lower()):
                phone_suggestions[pattern_name] = col
                break
    
    for pattern_name, pattern in phone_type_patterns.items():
        for col in df_columns:
            if re.search(pattern, col.lower()):
                phone_suggestions[pattern_name] = col
                break
    
    # Find data columns
    for output_col, patterns in data_patterns.items():
        for pattern in patterns:
            found = False
            for col in df_columns:
                if re.search(pattern, col.lower()):
                    suggestions[output_col] = col
                    found = True
                    break
            if found:
                break
    
    return suggestions, phone_suggestions

def create_column_mapping_interface(df):
    """Create the column mapping interface"""
    st.markdown("## 🔄 Column Mapping")
    st.markdown("Map your file's columns to the required output format:")
    
    # Get smart suggestions
    suggestions, phone_suggestions = smart_column_suggestions(df.columns.tolist())
    
    # Create tabs for different mapping sections
    tab1, tab2 = st.tabs(["📋 Contact Data Mapping", "📞 Phone Number Mapping"])
    
    with tab1:
        st.markdown("### Contact Information Mapping")
        
        # Create mapping interface for contact data
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Required Fields:**")
            for output_col, config in OUTPUT_COLUMNS.items():
                if config['required']:
                    default_idx = 0
                    if output_col in suggestions and suggestions[output_col] in df.columns:
                        default_idx = df.columns.tolist().index(suggestions[output_col]) + 1
                    
                    selected = st.selectbox(
                        f"{output_col} *",
                        options=['None'] + df.columns.tolist(),
                        index=default_idx,
                        help=config['description'],
                        key=f"mapping_{output_col}"
                    )
                    st.session_state.column_mapping[output_col] = selected if selected != 'None' else None
        
        with col2:
            st.markdown("**Optional Fields:**")
            for output_col, config in OUTPUT_COLUMNS.items():
                if not config['required']:
                    default_idx = 0
                    if output_col in suggestions and suggestions[output_col] in df.columns:
                        default_idx = df.columns.tolist().index(suggestions[output_col]) + 1
                    
                    selected = st.selectbox(
                        f"{output_col}",
                        options=['None'] + df.columns.tolist(),
                        index=default_idx,
                        help=config['description'],
                        key=f"mapping_{output_col}"
                    )
                    st.session_state.column_mapping[output_col] = selected if selected != 'None' else None
    
    with tab2:
        st.markdown("### Phone Number Mapping")
        st.markdown("Map up to 5 phone number columns and their corresponding type columns:")
        
        # Initialize phone mapping in session state if not exists
        if not st.session_state.phone_mapping:
            st.session_state.phone_mapping = [['None', 'None'] for _ in range(5)]
        
        for i in range(5):
            col1, col2 = st.columns(2)
            
            with col1:
                # Try to get suggestion for phone column
                phone_key = 'phone' if i == 0 else f'alt_phone_{i}'
                default_phone_idx = 0
                if phone_key in phone_suggestions and phone_suggestions[phone_key] in df.columns:
                    default_phone_idx = df.columns.tolist().index(phone_suggestions[phone_key]) + 1
                
                phone_col = st.selectbox(
                    f"Phone Column {i+1}",
                    options=['None'] + df.columns.tolist(),
                    index=default_phone_idx,
                    key=f"phone_col_{i}"
                )
                st.session_state.phone_mapping[i][0] = phone_col
            
            with col2:
                # Try to get suggestion for phone type column
                type_key = 'phone_type' if i == 0 else f'alt_phone_{i}_type'
                default_type_idx = 0
                if type_key in phone_suggestions and phone_suggestions[type_key] in df.columns:
                    default_type_idx = df.columns.tolist().index(phone_suggestions[type_key]) + 1
                
                type_col = st.selectbox(
                    f"Phone Type Column {i+1}",
                    options=['None'] + df.columns.tolist(),
                    index=default_type_idx,
                    key=f"phone_type_{i}"
                )
                st.session_state.phone_mapping[i][1] = type_col
    
    # Show phone type configuration
    st.markdown("### 📱 Phone Type Configuration")
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("**Accepted Types (for cleaned file):**")
        for ptype in ALLOWED_TYPES:
            st.write(f"✅ {ptype}")
    
    with col2:
        st.error("**Discard Types (for discard file):**")
        for ptype in LANDLINE_TYPES:
            st.write(f"❌ {ptype}")
    
    # Validation
    required_fields = [field for field, config in OUTPUT_COLUMNS.items() if config['required']]
    missing_required = [field for field in required_fields if not st.session_state.column_mapping.get(field)]
    
    if missing_required:
        st.error(f"⚠️ Missing required fields: {', '.join(missing_required)}")
        return False
    
    # Check if at least one phone mapping is configured
    phone_configured = any(mapping[0] != 'None' and mapping[1] != 'None' for mapping in st.session_state.phone_mapping)
    if not phone_configured:
        st.error("⚠️ At least one phone number and type column must be mapped")
        return False
    
    st.success("✅ Column mapping is complete!")
    return True

def process_data_with_mapping(df, column_mapping, phone_mapping):
    """Process the data using the configured mappings"""
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Filter phone mapping to only include configured pairs
    active_phone_mapping = [(p, t) for p, t in phone_mapping if p != 'None' and t != 'None']
    
    # Step 1: Identify rows with valid phones
    status_text.text("🔍 Identifying rows with mobile/voip phones...")
    progress_bar.progress(10)
    
    has_phones_results = []
    for idx, row in df.iterrows():
        has_phones_results.append(has_valid_phones_flexible(row, active_phone_mapping))
        if (idx + 1) % 1000 == 0:
            status_text.text(f"🔍 Processed {idx + 1:,} rows...")
    
    has_phones_mask = pd.Series(has_phones_results, index=df.index)
    rows_with_phones = df[has_phones_mask].copy()
    rows_without_phones = df[~has_phones_mask].copy()
    
    st.info(f"📱 Found {len(rows_with_phones):,} rows with mobile/voip phones")
    st.info(f"📞 Found {len(rows_without_phones):,} rows without mobile/voip phones")
    
    progress_bar.progress(30)
    
    # Step 2: Process cleaned file
    status_text.text("📱 Processing cleaned file...")
    
    df_final = pd.DataFrame()
    if not rows_with_phones.empty:
        phones_results = []
        for idx, row in rows_with_phones.iterrows():
            phones_results.append(extract_valid_phones_flexible(row, active_phone_mapping))
            if len(phones_results) % 500 == 0:
                status_text.text(f"📱 Extracted phones from {len(phones_results):,} rows...")
        
        phones_df = pd.DataFrame(phones_results, index=rows_with_phones.index)
        df_with_phones = pd.concat([rows_with_phones, phones_df], axis=1)
        df_with_phones = df_with_phones.dropna(subset=['Phone1'])
        
        # Create output dataframe using column mapping
        output_data = {}
        for output_col in OUTPUT_COLUMNS.keys():
            mapped_col = column_mapping.get(output_col)
            if mapped_col and mapped_col in df_with_phones.columns:
                output_data[output_col] = df_with_phones[mapped_col].fillna('')
            else:
                output_data[output_col] = pd.Series([''] * len(df_with_phones), index=df_with_phones.index)
        
        # Add phone columns
        for phone_col in ['Phone1', 'Phone2', 'Phone3']:
            output_data[phone_col] = df_with_phones[phone_col].fillna('')
        
        df_final = pd.DataFrame(output_data)
        
        # Handle name fallbacks
        if 'FirstName' in df_final.columns and 'LastName' in df_final.columns:
            full_name_col = None
            for col in df_with_phones.columns:
                if 'full' in col.lower() and 'name' in col.lower():
                    full_name_col = col
                    break
            
            if full_name_col:
                mask = (df_final['FirstName'] == '') & (df_final['LastName'] == '')
                if mask.any():
                    df_final.loc[mask, 'FirstName'] = df_with_phones.loc[mask, full_name_col].fillna('')
    
    progress_bar.progress(60)
    
    # Step 3: Process discard file
    status_text.text("📞 Processing discard file...")
    
    df_discards_final = pd.DataFrame()
    if not rows_without_phones.empty:
        landlines_results = []
        for idx, row in rows_without_phones.iterrows():
            landlines_results.append(extract_landlines_flexible(row, active_phone_mapping))
            if len(landlines_results) % 500 == 0:
                status_text.text(f"📞 Extracted landlines from {len(landlines_results):,} rows...")
        
        landlines_df = pd.DataFrame(landlines_results, index=rows_without_phones.index)
        df_discards_combined = pd.concat([rows_without_phones, landlines_df], axis=1)
        
        # Create discard output using same column mapping
        discard_data = {}
        for output_col in OUTPUT_COLUMNS.keys():
            mapped_col = column_mapping.get(output_col)
            if mapped_col and mapped_col in df_discards_combined.columns:
                discard_data[output_col] = df_discards_combined[mapped_col].fillna('')
            else:
                discard_data[output_col] = pd.Series([''] * len(df_discards_combined), index=df_discards_combined.index)
        
        # Add phone columns with types
        phone_cols_discard = ['Phone1', 'Phone2', 'Phone3', 'Phone4', 'Phone5']
        phone_type_cols = ['Phone1_Type', 'Phone2_Type', 'Phone3_Type', 'Phone4_Type', 'Phone5_Type']
        
        for col in phone_cols_discard + phone_type_cols:
            discard_data[col] = df_discards_combined[col].fillna('')
        
        df_discards_final = pd.DataFrame(discard_data)
        
        # Handle name fallbacks for discard file
        if 'FirstName' in df_discards_final.columns and 'LastName' in df_discards_final.columns:
            full_name_col = None
            for col in df_discards_combined.columns:
                if 'full' in col.lower() and 'name' in col.lower():
                    full_name_col = col
                    break
            
            if full_name_col:
                mask_np = (df_discards_final['FirstName'] == '') & (df_discards_final['LastName'] == '')
                if mask_np.any():
                    df_discards_final.loc[mask_np, 'FirstName'] = df_discards_combined.loc[mask_np, full_name_col].fillna('')
    
    progress_bar.progress(90)
    
    # Step 4: Generate QA report
    status_text.text("📊 Generating QA report...")
    qa_summary, qa_details = generate_qa_data_flexible(df, df_final, df_discards_final, active_phone_mapping)
    
    progress_bar.progress(100)
    status_text.text("✅ Processing complete!")
    
    return df_final, df_discards_final, qa_summary, qa_details

def generate_qa_data_flexible(original_df, cleaned_df, discard_df, phone_mapping):
    """Generate QA report data for flexible mapping"""
    
    # Count phone types in original data
    phone_type_counts = {}
    total_phones_original = 0
    
    for phone_col, type_col in phone_mapping:
        if phone_col in original_df.columns and type_col in original_df.columns:
            for idx, row in original_df.iterrows():
                phone = normalize_phone(row[phone_col])
                phone_type = str(row[type_col]).strip() if pd.notnull(row[type_col]) else ''
                if phone and phone_type:
                    total_phones_original += 1
                    if phone_type not in phone_type_counts:
                        phone_type_counts[phone_type] = 0
                    phone_type_counts[phone_type] += 1
    
    # Count mobile phones in discard file
    discard_mobile_contacts = 0
    discard_mobile_phones = 0
    
    if not discard_df.empty:
        for idx, row in discard_df.iterrows():
            contact_has_mobile = False
            for i in range(1, 6):  # Phone1 through Phone5
                phone_col = f'Phone{i}'
                type_col = f'Phone{i}_Type'
                
                if phone_col in discard_df.columns and type_col in discard_df.columns:
                    phone = row.get(phone_col)
                    phone_type = str(row.get(type_col, '')).strip()
                    
                    if pd.notnull(phone) and phone != '' and phone_type.lower() in ALLOWED_TYPES:
                        discard_mobile_phones += 1
                        contact_has_mobile = True
            
            if contact_has_mobile:
                discard_mobile_contacts += 1
    
    # Calculate unique contacts processed
    cleaned_contacts = len(cleaned_df) if not cleaned_df.empty else 0
    discard_contacts = len(discard_df) if not discard_df.empty else 0
    total_processed = cleaned_contacts + discard_contacts
    
    # Create summary data
    summary_data = [
        ['Total Contacts in Original File', f"{len(original_df):,}"],
        ['Contacts in Cleaned File', f"{cleaned_contacts:,}"],
        ['Contacts in Discard File', f"{discard_contacts:,}"],
        ['Total Contacts Processed', f"{total_processed:,}"],
        ['Contact Count Verification', '✅ MATCH' if len(original_df) == total_processed else '❌ MISMATCH'],
        ['', ''],
        ['Total Phone Numbers (All Types)', f"{total_phones_original:,}"],
    ]
    
    # Add phone type breakdown
    for phone_type, count in sorted(phone_type_counts.items()):
        summary_data.append([f'{phone_type} Phone Numbers', f"{count:,}"])
    
    summary_data.extend([
        ['', ''],
        ['Contacts with Mobile Phones in Discard File', f"{discard_mobile_contacts:,}"],
        ['Total Mobile Phone Numbers in Discard File', f"{discard_mobile_phones:,}"],
    ])
    
    summary = pd.DataFrame(summary_data, columns=['QA CHECK', 'RESULT'])
    
    # Placeholder for detailed missing phones
    details = pd.DataFrame(columns=['FirstName', 'LastName', 'Phone 1', 'Phone 2', 'Phone 3', 'APN'])
    
    return summary, details

def main():
    st.title("📞 Flexible Phone Data Processor")
    st.markdown("Upload any Excel file and map columns to the required output format for phone number processing")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ About This Tool")
        st.markdown("**Supported Input Formats:**")
        st.success("✅ Any Excel file with phone data")
        st.success("✅ Flexible column mapping")
        st.success("✅ Smart column suggestions")
        
        st.markdown("---")
        st.markdown("**Processing Steps:**")
        st.write("1. Upload Excel file")
        st.write("2. Map columns to output format") 
        st.write("3. Process phone numbers")
        st.write("4. Download results")
        
        st.markdown("---")
        st.markdown("**Output Files:**")
        st.write("📱 Cleaned file (Mobile/VoIP)")
        st.write("📞 Discard file (Landlines)")
        st.write("📊 QA Report")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose an Excel file", 
        type=['xlsx', 'xls'],
        help="Upload any Excel file with contact and phone data"
    )
    
    if uploaded_file is not None:
        try:
            # Load the file
            with st.spinner("📖 Loading Excel file..."):
                df = pd.read_excel(uploaded_file)
                st.session_state.df = df
            
            # Display file info
            st.success("✅ File loaded successfully!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Rows", f"{len(df):,}")
            with col2:
                st.metric("Total Columns", f"{len(df.columns):,}")
            with col3:
                st.metric("File Size", f"{uploaded_file.size / 1024 / 1024:.1f} MB")
            
            # Show preview
            with st.expander("📋 Data Preview", expanded=False):
                st.dataframe(df.head(10), use_container_width=True)
                
                st.markdown("**Available Columns:**")
                cols = st.columns(3)
                for i, col in enumerate(df.columns):
                    with cols[i % 3]:
                        st.write(f"• {col}")
            
            # Column mapping interface
            mapping_valid = create_column_mapping_interface(df)
            
            if mapping_valid:
                st.session_state.mapping_complete = True
                
                # Process button
                if st.button("🚀 Process File", type="primary", use_container_width=True):
                    
                    # Process the file with mappings
                    cleaned_df, discard_df, qa_summary, qa_details = process_data_with_mapping(
                        df, 
                        st.session_state.column_mapping, 
                        st.session_state.phone_mapping
                    )
                    
                    # Display results
                    st.markdown("## 📊 Processing Results")
                    
                    # Metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📱 Cleaned Records", f"{len(cleaned_df):,}" if not cleaned_df.empty else "0")
                    with col2:
                        st.metric("📞 Discard Records", f"{len(discard_df):,}" if not discard_df.empty else "0")
                    with col3:
                        total_processed = (len(cleaned_df) if not cleaned_df.empty else 0) + (len(discard_df) if not discard_df.empty else 0)
                        st.metric("📋 Total Processed", f"{total_processed:,}")
                    
                    # QA Summary
                    st.markdown("### 📋 QA Summary")
                    st.dataframe(qa_summary, use_container_width=True, hide_index=True)
                    
                    # Download files
                    st.markdown("### 📥 Download Files")
                    
                    # Generate filenames
                    date_str = datetime.now().strftime("%b%d")
                    
                    # Extract state and county from data
                    if not cleaned_df.empty:
                        state = cleaned_df.get('PropertyState', pd.Series()).dropna()
                        state = state.iloc[0] if len(state) > 0 else 'Unknown'
                        county_raw = cleaned_df.get('PropertyCounty', pd.Series()).dropna()
                        county = re.sub(r'\s+', '', str(county_raw.iloc[0])) if len(county_raw) > 0 else 'Unknown'
                    else:
                        state = "Unknown"
                        county = "Unknown"
                    
                    # Create download buttons
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if not cleaned_df.empty:
                            cleaned_excel = io.BytesIO()
                            cleaned_df.to_excel(cleaned_excel, index=False, engine='openpyxl')
                            cleaned_excel.seek(0)
                            
                            st.download_button(
                                label="📱 Download Cleaned File",
                                data=cleaned_excel,
                                file_name=f"{state}{county}{date_str}LCT.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                        else:
                            st.info("No cleaned data to download")
                    
                    with col2:
                        if not discard_df.empty:
                            discard_excel = io.BytesIO()
                            discard_df.to_excel(discard_excel, index=False, engine='openpyxl')
                            discard_excel.seek(0)
                            
                            st.download_button(
                                label="📞 Download Discard File",
                                data=discard_excel,
                                file_name=f"{state}{county}{date_str}LandlinesNoNumber.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                        else:
                            st.info("No discard data to download")
                    
                    with col3:
                        # QA Report
                        qa_excel = io.BytesIO()
                        with pd.ExcelWriter(qa_excel, engine='openpyxl') as writer:
                            qa_summary.to_excel(writer, sheet_name="Summary", index=False)
                            if not qa_details.empty:
                                qa_details.to_excel(writer, sheet_name="Missing Phones", index=False)
                        qa_excel.seek(0)
                        
                        st.download_button(
                            label="📊 Download QA Report",
                            data=qa_excel,
                            file_name=f"{state}{county}{date_str}QAReport.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    
                    # Show data previews
                    if not cleaned_df.empty:
                        with st.expander("📱 Cleaned Data Preview", expanded=False):
                            st.success("✅ Mapped to standardized output format")
                            st.dataframe(cleaned_df.head(20), use_container_width=True)
                            
                            # Show column mapping used
                            st.markdown("**Column Mapping Applied:**")
                            mapping_display = []
                            for output_col, input_col in st.session_state.column_mapping.items():
                                if input_col:
                                    mapping_display.append(f"**{output_col}** ← {input_col}")
                            
                            if mapping_display:
                                cols = st.columns(2)
                                for i, mapping in enumerate(mapping_display):
                                    with cols[i % 2]:
                                        st.markdown(mapping)
                    
                    if not discard_df.empty:
                        with st.expander("📞 Discard Data Preview", expanded=False):
                            st.dataframe(discard_df.head(20), use_container_width=True)
        
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            with st.expander("Error Details"):
                st.exception(e)
    
    else:
        st.info("👆 Please upload an Excel file to get started")
        
        # Show instructions
        with st.expander("📖 Instructions", expanded=True):
            st.markdown("""
            **How to use this flexible processor:**
            
            1. **Upload any Excel file** containing contact and phone data
            2. **Map your columns** to the required output format using the interface
            3. **Configure phone mappings** for up to 5 phone number columns
            4. **Process the file** to separate mobile/VoIP from landlines
            5. **Download results** in the standardized format
            
            **Key Features:**
            - **Smart Suggestions**: Automatically suggests column mappings based on names
            - **Flexible Input**: Works with any Excel format from different data brokers
            - **Standardized Output**: Always produces consistent format regardless of input
            - **Phone Type Detection**: Separates mobile/VoIP from landlines automatically
            
            **Supported Phone Types:**
            - **Kept (Cleaned File)**: Mobile, VoIP, Cellular, Cell
            - **Discarded**: Landline, Pager, Special Service, Wireline
            
            **Output Format:**
            - **FirstName, LastName**: Contact name fields
            - **Email**: Email address (can be empty)
            - **Mailing/Property Address Fields**: Complete address information
            - **Phone1, Phone2, Phone3**: Up to 3 mobile/VoIP numbers
            - **APN, PropertyCounty, Acreage**: Property details
            """)
        
        # Show example mappings
        with st.expander("💡 Example Column Mappings", expanded=False):
            st.markdown("""
            **Common input formats this tool can handle:**
            
            **LandPortal Format:**
            - Owner 1 First Name → FirstName
            - Owner 1 Last Name → LastName
            - Mail Full Address → MailingAddress
            - Phone + Phone (Line Type) → Phone1
            
            **DataTree Format:**
            - First Name → FirstName
            - Last Name → LastName
            - Mailing Address → MailingAddress
            - Cell Phone + Phone Type → Phone1
            
            **PropStream Format:**
            - Owner First → FirstName
            - Owner Last → LastName
            - Owner Address → MailingAddress
            - Phone Number + Line Type → Phone1
            
            **Custom Format:**
            - Any column can be mapped to any output field
            - System will suggest mappings based on column names
            - Manual adjustment available for all mappings
            """)

if __name__ == "__main__":
    main()