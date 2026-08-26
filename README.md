# Launch Control Template Converter

A Streamlit web app that converts a contact export from any data broker into the
Launch Control import template, keeping the top three phone numbers per contact.

## Purpose

Every data broker names its columns differently. This tool lets you map whatever
columns your export happens to have onto one standardized Launch Control layout,
so you can pull data from any source and import it the same way every time.

- Upload an Excel or CSV export from any provider (Land Insights, DataTree, PropStream, etc.)
- Map columns to the Launch Control format with smart suggestions
- Export the first three phone numbers per contact, deduplicated
- Get a consistent output file no matter what the input looked like

## Key Features

### Universal broker compatibility
- Reads `.xlsx`, `.xls` and `.csv` exports
- Detects CSV delimiter (comma, tab, semicolon, pipe) and encoding automatically
- Skips a blank leading row when the real headers start on row 2
- Smart column detection suggests mappings; every mapping can be overridden
- No hardcoded column dependencies

### Phone number handling
- Takes the first 3 valid numbers per contact, in the order you map the columns
- Keeps every line type — mobile, landline, VoIP, all of it
- Skips duplicates, so the same number never lands in two slots
- Normalizes to 10 digits, stripping formatting, country codes and scientific notation
- Reads up to 5 phone columns per contact

### Standardized output
- One output row per input row — no contacts dropped
- Launch Control compatible column order
- QA report with contact counts, phone distribution and duplicate counts

### Editable file naming
- Suggests `LC` + state + county + 2-digit year + 3-letter month, e.g. `LCALLimestone26AUG`
- State and county come from the mapped data, falling back to the uploaded file's name
- The suggestion lands in an editable field so you can append acreage or any other detail

## Installation and setup

### Local

```bash
pip install -r requirements.txt
streamlit run LaunchControlTemplateConverter.py
```

### Streamlit Cloud

Deployed from this repo with `LaunchControlTemplateConverter.py` as the entry point.

## How to use

### 1. Upload your file
Any `.xlsx`, `.xls` or `.csv` export with contact and phone data. If the file has a
blank first row above the headers, the app detects it and tells you which row it
used for column titles.

### 2. Map your columns
**Contact Data Mapping** covers the standard fields — FirstName and LastName are
required, everything else is optional.

**Phone Number Mapping** takes up to 5 phone columns. Order matters: Phone Column 1
fills the Phone1 slot first, then 2, then 3.

### 3. Review the suggestions
Mappings are suggested from the column names:
- "Owner 1 First Name" → FirstName
- "Mail Full Address" → MailingAddress
- "Phone" → Phone Column 1
- "Alt Phone 1" → Phone Column 2

### 4. Process
Click **Process File**. A 50,000-row file with 5 phone columns processes in well
under a second.

### 5. Name it and download
The suggested file name appears in an editable field. Change it however you like,
then download.

## Output format

```
FirstName | LastName | Email
MailingAddress | MailingCity | MailingState | MailingZip
PropertyAddress | PropertyCity | PropertyState | PropertyZip
Phone1 | Phone2 | Phone3
APN | PropertyCounty | Acreage
```

Output is always `.xlsx`, whatever the input format was.

## QA report

Every run reports:
- Original vs. output contact counts, with a match check
- Contacts with at least one phone, and contacts with none
- Total valid phone numbers found in the source data
- Duplicate numbers skipped
- How many contacts got a Phone1, Phone2 and Phone3

## Technical requirements

- Python 3.13
- Streamlit 1.40+
- Pandas 2.2+
- NumPy 1.26+
- OpenPyXL 3.1.2+

### File size
- Streamlit Cloud caps uploads at 200MB
- Local runs are limited by available memory

## Troubleshooting

**Column mapping suggestions not appearing**
The file uses non-standard column names. Map them manually with the dropdowns.

**"Missing required fields"**
FirstName and LastName both need a mapping.

**"This file has headers but no data rows"**
The upload parsed correctly but contained no contacts.

**Wrong columns detected in a CSV**
The delimiter sniffer works from the first 64KB. An unusual delimiter in a file
whose first rows are mostly empty can throw it off — re-export as `.xlsx` if so.

## Limitations

- Maximum 5 phone number columns per contact, 3 exported
- Contacts with no phone number are still exported, with blank phone fields
- Cloud deployment capped at 200MB per file

## Version history

**v3.0** — Launch Control Template Converter
- CSV input with delimiter and encoding detection
- Blank leading row detection
- All phone types kept; first 3 distinct numbers exported
- Editable standardized file naming
- Vectorized processing (50k rows in under a second)
- Removed the mobile/landline split and the discard file

**v2.0** — Flexible column mapping
- Universal data broker compatibility
- Smart column detection and suggestions
- Interactive mapping interface

**v1.0** — Fixed format processor
- LandPortal-specific column mapping
- Basic phone number separation

---

Built with Streamlit and Python for real estate professionals working with multiple data sources.
