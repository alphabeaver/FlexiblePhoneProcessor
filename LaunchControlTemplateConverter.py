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

def extract_all_phones_flexible(row, phone_mappings):
    """Extract ALL valid phone numbers regardless of type, limit to 3"""
    valid_phones = []
    
    for phone_col, type_col in phone_mappings:
        if phone_col == 'None' or phone_col not in row.index:
            continue
            
        phone = normalize_phone(row.get(phone_col))
        
        # Accept ANY phone that normalizes successfully, regardless of type
        if phone:
            valid_phones.append(phone)
        if len(valid_phones) == 3:  # Stop after 3 phones
            break
    
    result = valid_phones + [None] * (3 - len(valid_phones))
    return pd.Series(result, index=['Phone1', 'Phone2', 'Phone3'])

def has_any_phone_flexible(row, phone_mappings):
    """Check if row has ANY valid phone number"""
    for phone_col, type_col in phone_mappings:
        if phone_col == 'None' or phone_col not in row.index:
            continue
            
        phone = normalize_phone(row.get(phone_col))
        
        if phone:
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
        st.markdown("Map up to 5 phone number columns. The app will extract the top 3 phone numbers in order, **regardless of type (mobile, landline, VoIP, etc.)**")
        
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
                # Phone type column (now optional, just for reference)
                type_key = 'phone_type' if i == 0 else f'alt_phone_{i}_type'
                default_type_idx = 0
                if type_key in phone_suggestions and phone_suggestions[type_key] in df.columns:
                    default_type_idx = df.columns.tolist().index(phone_suggestions[type_key]) + 1
                
                type_col = st.selectbox(
                    f"Phone Type Column {i+1} (optional)",
                    options=['None'] + df.columns.tolist(),
                    index=default_type_idx,
                    key=f"phone_type_{i}"
                )
                st.session_state.phone_mapping[i][1] = type_col
        
        st.info("💡 **Phone type columns are optional** — the app will accept all phone numbers regardless of whether they're marked as mobile, landline, VoIP, etc.")
    
    # Validation
    required_fields = [field for field, config in OUTPUT_COLUMNS.items() if config['required']]
    missing_required = [field for field in required_fields if not st.session_state.column_mapping.get(field)]
    
    if missing_required:
        st.error(f"⚠️ Missing required fields: {', '.join(missing_required)}")
        return False
    
    # Check if at least one phone mapping is configured
    phone_configured = any(mapping[0] != 'None' for mapping in st.session_state.phone_mapping)
    if not phone_configured:
        st.error("⚠️ At least one phone number column must be mapped")
        return False
    
    st.success("✅ Column mapping is complete!")
    return True

def process_data_with_mapping(df, column_mapping, phone_mapping):
    """Process the data using the configured mappings"""
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Filter phone mapping to only include configured phone columns
    active_phone_mapping = [(p, t) for p, t in phone_mapping if p != 'None']
    
    # Step 1: Extract top 3 phones for each row
    status_text.text("📞 Extracting top 3 phone numbers (all types)...")
    progress_bar.progress(20)
    
    phones_results = []
    for idx, row in df.iterrows():
        phones_results.append(extract_all_phones_flexible(row, active_phone_mapping))
        if (idx + 1) % 1000 == 0:
            status_text.text(f"📞 Processed {idx + 1:,} rows...")
    
    phones_df = pd.DataFrame(phones_results, index=df.index)
    df_with_phones = pd.concat([df, phones_df], axis=1)
    
    progress_bar.progress(50)
    
    # Step 2: Create output dataframe with standardized format
    status_text.text("📋 Formatting output data...")
    
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
    
    # Handle name fallbacks if FirstName and LastName are empty
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
    
    progress_bar.progress(75)
    
    # Step 3: Generate QA report
    status_text.text("📊 Generating QA report...")
    qa_summary = generate_qa_report(df, df_final, active_phone_mapping)
    
    progress_bar.progress(100)
    status_text.text("✅ Processing complete!")
    
    return df_final, qa_summary

def generate_qa_report(original_df, final_df, phone_mapping):
    """Generate QA report"""
    
    # Count total valid phones in original data
    total_phones_original = 0
    for phone_col, _ in phone_mapping:
        if phone_col in original_df.columns:
            for idx, row in original_df.iterrows():
                phone = normalize_phone(row[phone_col])
                if phone:
                    total_phones_original += 1
    
    # Count rows with at least one phone
    rows_with_any_phone = 0
    for idx, row in original_df.iterrows():
        if has_any_phone_flexible(row, phone_mapping):
            rows_with_any_phone += 1
    
    # Count distribution of phones in final output
    phone1_count = (final_df['Phone1'] != '').sum()
    phone2_count = (final_df['Phone2'] != '').sum()
    phone3_count = (final_df['Phone3'] != '').sum()
    
    # Create summary
    summary_data = [
        ['Total Contacts in Original File', f"{len(original_df):,}"],
        ['Contacts in Output File', f"{len(final_df):,}"],
        ['Contact Count Verification', '✅ MATCH' if len(original_df) == len(final_df) else '❌ MISMATCH'],
        ['', ''],
        ['Contacts with At Least One Phone', f"{rows_with_any_phone:,}"],
        ['Total Phone Numbers in Original Data', f"{total_phones_original:,}"],
        ['', ''],
        ['Phone Distribution in Output:', ''],
        ['Contacts with Phone1', f"{phone1_count:,}"],
        ['Contacts with Phone2', f"{phone2_count:,}"],
        ['Contacts with Phone3', f"{phone3_count:,}"],
    ]
    
    summary = pd.DataFrame(summary_data, columns=['QA CHECK', 'RESULT'])
    
    return summary

def main():
    st.title("📞 Flexible Phone Data Processor")
    st.markdown("Upload any Excel file and extract the top 3 phone numbers per contact in LaunchControl format")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ About This Tool")
        st.markdown("**What It Does:**")
        st.success("✅ Keeps ALL phone types (mobile, landline, VoIP, pager, etc.)")
        st.success("✅ Extracts top 3 phone numbers per contact")
        st.success("✅ Outputs standardized LaunchControl format")
        st.success("✅ Smart column suggestions")
        
        st.markdown("---")
        st.markdown("**Processing Steps:**")
        st.write("1. Upload Excel file")
        st.write("2. Map columns to output format") 
        st.write("3. Process phone numbers")
        st.write("4. Download results")
        
        st.markdown("---")
        st.markdown("**Output Format:**")
        st.write("📱 Single file with all contacts")
        st.write("📞 Phone1, Phone2, Phone3 (all types)")
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
                    final_df, qa_summary = process_data_with_mapping(
                        df, 
                        st.session_state.column_mapping, 
                        st.session_state.phone_mapping
                    )
                    
                    # Display results
                    st.markdown("## 📊 Processing Results")
                    
                    # Metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📱 Total Records", f"{len(final_df):,}")
                    with col2:
                        phone1_count = (final_df['Phone1'] != '').sum()
                        st.metric("Records with Phone1", f"{phone1_count:,}")
                    with col3:
                        phone2_count = (final_df['Phone2'] != '').sum()
                        st.metric("Records with Phone2", f"{phone2_count:,}")
                    
                    # QA Summary
                    st.markdown("### 📋 QA Summary")
                    st.dataframe(qa_summary, use_container_width=True, hide_index=True)
                    
                    # Download file
                    st.markdown("### 📥 Download File")
                    
                    # Generate filename
                    date_str = datetime.now().strftime("%b%d")
                    
                    # Extract state and county from data
                    state = 'Unknown'
                    county = 'Unknown'
                    if not final_df.empty and 'PropertyState' in final_df.columns:
                        state_vals = final_df['PropertyState'].dropna()
                        if len(state_vals) > 0:
                            state = str(state_vals.iloc[0])
                    
                    if not final_df.empty and 'PropertyCounty' in final_df.columns:
                        county_vals = final_df['PropertyCounty'].dropna()
                        if len(county_vals) > 0:
                            county = re.sub(r'\s+', '', str(county_vals.iloc[0]))
                    
                    # Create download button
                    final_excel = io.BytesIO()
                    final_df.to_excel(final_excel, index=False, engine='openpyxl')
                    final_excel.seek(0)
                    
                    st.download_button(
                        label="📥 Download Processed File (LaunchControl Format)",
                        data=final_excel,
                        file_name=f"{state}{county}{date_str}LCT.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    # Show data preview
                    with st.expander("📋 Data Preview", expanded=False):
                        st.success("✅ All records with standardized output format")
                        st.dataframe(final_df.head(20), use_container_width=True)
                        
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
        
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            with st.expander("Error Details"):
                st.exception(e)
    
    else:
        st.info("👆 Please upload an Excel file to get started")
        
        # Show instructions
        with st.expander("📖 Instructions", expanded=True):
            st.markdown("""
            **How to use this processor:**
            
            1. **Upload any Excel file** containing contact and phone data
            2. **Map your columns** to the required output format using the interface
            3. **Configure phone mappings** for up to 5 phone number columns
            4. **Process the file** to extract top 3 phones per contact
            5. **Download results** in the standardized LaunchControl format
            
            **Key Features:**
            - **Smart Suggestions**: Automatically suggests column mappings based on names
            - **Flexible Input**: Works with any Excel format from different data brokers
            - **All Phone Types**: Keeps mobile, landline, VoIP, pager — everything
            - **Top 3 Priority**: Extracts the first 3 valid phone numbers in order
            - **Standardized Output**: Always produces consistent format regardless of input
            
            **Output Format:**
            - **FirstName, LastName**: Contact name fields
            - **Email**: Email address (can be empty)
            - **Mailing/Property Address Fields**: Complete address information
            - **Phone1, Phone2, Phone3**: Top 3 phone numbers (any type)
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
            - Phone → Phone Column 1
            - Alt Phone 1 → Phone Column 2
            - Alt Phone 2 → Phone Column 3
            
            **DataTree Format:**
            - First Name → FirstName
            - Last Name → LastName
            - Mailing Address → MailingAddress
            - Cell Phone → Phone Column 1
            
            **PropStream Format:**
            - Owner First → FirstName
            - Owner Last → LastName
            - Owner Address → MailingAddress
            - Phone Number → Phone Column 1
            
            **Custom Format:**
            - Any column can be mapped to any output field
            - System will suggest mappings based on column names
            - Manual adjustment available for all mappings
            """)

if __name__ == "__main__":
    main()
