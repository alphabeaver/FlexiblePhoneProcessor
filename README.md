# Flexible Phone Data Processor

A Streamlit web application that processes contact data from any data broker by allowing dynamic column mapping and automatic separation of mobile/VoIP phone numbers from landlines.

## Purpose

This tool solves the problem of working with contact data from multiple data brokers that use different column naming conventions and formats. Instead of being locked into one specific format, you can now:

- Upload Excel files from any data broker (LandPortal, DataTree, PropStream, etc.)
- Map columns to a standardized output format using an intuitive interface
- Separate mobile/VoIP numbers for text marketing campaigns
- Generate clean, consistent output files regardless of input format

## Key Features

### Universal Data Broker Compatibility
- Works with Excel exports from any real estate data provider
- Smart column detection suggests mappings automatically
- Manual override capability for custom or unusual formats
- No hardcoded column dependencies

### Intelligent Phone Number Processing
- Separates mobile/VoIP numbers from landlines automatically
- Normalizes phone numbers to 10-digit format
- Handles scientific notation and various formatting
- Processes up to 5 phone number columns per contact

### Standardized Output Format
- Consistent column structure regardless of input source
- Launch Control compatible formatting
- Separate files for mobile contacts vs landline contacts
- Comprehensive QA reporting with data validation

### Smart Column Mapping
- Automatic suggestions based on column name patterns
- Interactive dropdown interface for manual mapping
- Real-time validation of required fields
- Visual feedback on mapping completeness

## Installation and Setup

### Local Installation

1. **Download the files:**
   - app.py (main application)
   - requirements.txt (dependencies)

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   streamlit run app.py
   ```

### Cloud Deployment (Recommended)

1. **Upload to GitHub:**
   - Create a new public repository
   - Upload app.py and requirements.txt

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repository
   - Deploy with one click

## How to Use

### Step 1: Upload Your Data File
- Upload any Excel file (.xlsx or .xls) containing contact information
- File can be from any data broker or custom export
- System will analyze all available columns

### Step 2: Map Your Columns
- Use the **Contact Data Mapping** tab to map basic information:
  - FirstName, LastName (required)
  - Address fields (optional)
  - Property information (optional)

- Use the **Phone Number Mapping** tab to configure phone processing:
  - Map up to 5 phone number columns
  - Map corresponding phone type columns
  - System validates at least one phone mapping is configured

### Step 3: Review Smart Suggestions
The system automatically suggests mappings based on common patterns:
- "Owner 1 First Name" → FirstName
- "Mail Full Address" → MailingAddress
- "Phone" → Phone1
- "Phone (Line Type)" → Phone1 Type

### Step 4: Process Your Data
- Click "Process File" to separate mobile/VoIP from landlines
- Monitor progress with real-time status updates
- Review processing statistics and QA metrics

### Step 5: Download Results
Three files are generated:
- **Cleaned File**: Mobile/VoIP contacts in standardized format
- **Discard File**: Landline/pager contacts for reference
- **QA Report**: Processing statistics and validation results

## Supported Data Formats

### Input Requirements
- Excel files (.xlsx or .xls format)
- Contact information columns
- Phone number columns with corresponding type classifications
- No specific column naming requirements

### Common Data Broker Formats Supported
- **LandPortal**: Owner fields, Mail addresses, Phone + Phone (Line Type)
- **DataTree**: Standard contact fields with phone classifications
- **PropStream**: Owner information with phone type indicators
- **Custom Exports**: Any Excel format with contact and phone data

### Phone Type Classifications
**Accepted Types (Cleaned File):**
- Mobile, VoIP, Cellular, Cell

**Discard Types (Discard File):**
- Landline, Pager, Special Service, Wireline

## Output File Structure

### Cleaned File Format (Launch Control Compatible)
```
FirstName | LastName | Email | MailingAddress | MailingCity | MailingState | MailingZip
PropertyAddress | PropertyCity | PropertyState | PropertyZip
Phone1 | Phone2 | Phone3 | APN | PropertyCounty | Acreage
```

### Discard File Format
Same as cleaned file plus:
```
Phone1_Type | Phone2_Type | Phone3_Type | Phone4_Type | Phone5_Type
Phone4 | Phone5
```

## File Naming Convention
Files are automatically named using this pattern:
- Cleaned File: `[State][County][Date]LCT.xlsx`
- Discard File: `[State][County][Date]LandlinesNoNumber.xlsx`
- QA Report: `[State][County][Date]QAReport.xlsx`

Example: `TXHarris Dec15LCT.xlsx`

## Quality Assurance Features

### Data Validation
- Contact count verification ensures no data loss
- Phone type distribution analysis
- Mobile number leakage detection
- Mapping completeness validation

### Error Detection
- Identifies contacts with mobile numbers in discard file
- Flags processing discrepancies
- Reports missing required field mappings
- Validates phone number formatting

## Technical Requirements

### Dependencies
- Python 3.7+
- Streamlit 1.28.1+
- Pandas 2.0.3+
- OpenPyXL 3.1.2+

### Browser Compatibility
- Chrome, Firefox, Safari, Edge
- Mobile responsive interface
- No browser extensions required

### File Size Limits
- Streamlit Cloud: 200MB file limit
- Local installation: Limited by available memory
- Recommended: Process files under 50MB for optimal performance

## Troubleshooting

### Common Issues

**"No rows with valid mobile/voip phones found"**
- Verify phone type columns contain recognized values
- Check phone type spelling and capitalization
- Ensure phone numbers are properly formatted

**"Missing required fields" error**
- Map at least FirstName and LastName columns
- Verify required field mappings are not set to "None"
- Check that mapped columns exist in your data

**Column mapping suggestions not appearing**
- File may use non-standard column naming
- Manually map columns using dropdown selectors
- Verify file loaded correctly with data preview

**Processing takes too long**
- Large files may require several minutes
- Check progress indicators for status updates
- Consider processing smaller geographic areas separately

### Performance Optimization
- Close other browser tabs during processing
- Use Chrome or Firefox for best performance
- Process files during off-peak hours for cloud deployment

## Use Cases

### Real Estate Marketing
- Text marketing campaign list preparation
- Lead qualification and segmentation
- Multi-source data consolidation

### Data Migration
- Moving between different CRM systems
- Standardizing data from multiple sources
- Cleaning and formatting legacy databases

### Quality Control
- Validating data broker exports
- Identifying data quality issues
- Ensuring consistent formatting standards

## Limitations

- Excel files only (no CSV input)
- Maximum 5 phone numbers per contact
- Cloud deployment limited to 200MB files
- Requires phone type classifications in source data

## Support and Updates

This tool is designed to be maintenance-free once deployed. The flexible column mapping system accommodates new data broker formats without code changes.

For technical issues:
1. Verify file format and column mapping
2. Check browser console for error messages
3. Test with smaller data samples
4. Ensure all required dependencies are installed

## Version History

**v2.0** - Flexible Column Mapping
- Universal data broker compatibility
- Smart column detection and suggestions
- Interactive mapping interface
- Enhanced validation and error handling

**v1.0** - Fixed Format Processor
- LandPortal-specific column mapping
- Basic phone number separation
- Standard output formatting

---

Built with Streamlit and Python for real estate professionals working with multiple data sources.
