import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
import numpy as np

def format_indian_currency(number):
    """Formats a number into Indian currency style (₹ ##,##,##,###)."""
    s = str(int(number))
    if len(s) <= 3:
        return '₹ ' + s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        formatted = ','.join(reversed(parts)) + ',' + last3
        return '₹ ' + formatted

def extract_expenditure_data(pdf_file):
    """
    Extracts capital and operational expenditure data from specific tables in a NIRF PDF,
    then calculates and appends the average expenditure over the years.
    This version is more robust and identifies tables by their content.
    """
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Get College Info from the first page
            first_page_text = pdf.pages[0].extract_text()
            if not first_page_text: first_page_text = ""
            name_match = re.search(r'Institute Name:\s*(.*?)\s*\[', first_page_text)
            id_match = re.search(r'\[(IR-[A-Z]-[A-Z]-\d+)\]', first_page_text)
            college_name = name_match.group(1).strip() if name_match else "Unknown"
            college_id = id_match.group(1).strip() if id_match else "Unknown"

            capital_exp = {}
            operational_exp = {}
            
            # Keywords to identify rows within the tables
            capital_keys = ["Library", "New Equipment", "Engineering Workshops", "creation of Capital Assets"]
            operational_keys = ["Salaries", "Maintenance of Academic Infrastructure", "Seminars"]

            # Find and process both expenditure tables
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue
                
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    
                    # Check the content of the first column to identify the table type
                    first_col_text = " ".join([str(row[0]) for row in table if row and row[0]])
                    
                    is_capital_table = "Capital Expenditure" in first_col_text
                    is_operational_table = "Operational Expenditure" in first_col_text

                    if not (is_capital_table or is_operational_table):
                        continue

                    # The header with years is the first row containing year-like strings
                    header = []
                    for row in table:
                        if any(re.match(r'\d{4}-\d{2}', str(cell)) for cell in row):
                            header = [str(cell).replace('\n', ' ') if cell else '' for cell in row]
                            break
                    
                    if not header:
                        continue

                    years = [h for h in header if re.match(r'\d{4}-\d{2}', h)]
                    if not years:
                        continue

                    # Now process the rows of the identified table
                    for row in table:
                        if not row or not row[0]:
                            continue
                        
                        row_title = str(row[0]).replace('\n', ' ')
                        
                        target_dict = None
                        keys_to_check = []
                        if is_capital_table:
                            target_dict = capital_exp
                            keys_to_check = capital_keys
                        elif is_operational_table:
                            target_dict = operational_exp
                            keys_to_check = operational_keys

                        # Check if the row title matches any of our keywords
                        if any(key.lower() in row_title.lower() for key in keys_to_check):
                            for year in years:
                                try:
                                    year_col_idx = header.index(year)
                                    if year_col_idx >= len(row) or not row[year_col_idx]: continue

                                    val_str = str(row[year_col_idx]).split('(')[0].strip()
                                    value = int(re.sub(r'[^0-9]', '', val_str))
                                    target_dict[year] = target_dict.get(year, 0) + value
                                except (ValueError, IndexError):
                                    continue
            
            # --- Combine and structure the data ---
            all_years = sorted(list(set(capital_exp.keys()) | set(operational_exp.keys())), reverse=True)
            
            if not all_years:
                return pd.DataFrame()

            rows = []
            for idx, year in enumerate(all_years, 1):
                cap = capital_exp.get(year, 0)
                op = operational_exp.get(year, 0)
                rows.append({
                    "S.No": idx,
                    "College Name": college_name,
                    "College ID": college_id,
                    "Academic Year": year,
                    "Capital Expenditure": format_indian_currency(cap),
                    "Operational Expenditure": format_indian_currency(op),
                    "Total Expenditure": format_indian_currency(cap + op)
                })

            # --- Calculate and add the Average row ---
            avg_cap = np.mean(list(capital_exp.values())) if capital_exp else 0
            avg_op = np.mean(list(operational_exp.values())) if operational_exp else 0
            avg_total = avg_cap + avg_op

            rows.append({
                "S.No": "",
                "College Name": "",
                "College ID": "",
                "Academic Year": "**Average**",
                "Capital Expenditure": format_indian_currency(avg_cap),
                "Operational Expenditure": format_indian_currency(avg_op),
                "Total Expenditure": format_indian_currency(avg_total)
            })

            return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"An error occurred in expenditure extraction: {e}")
        return pd.DataFrame()


def expenditure_tab():
    st.subheader("🏛️ NIRF Expenditure Data Extractor")
    uploaded_pdfs = st.file_uploader("Upload one or more NIRF PDFs", type="pdf", accept_multiple_files=True, key="expenditure_uploader")

    if uploaded_pdfs:
        all_dfs = []
        with st.spinner("Extracting expenditure data from all files..."):
            for pdf in uploaded_pdfs:
                df = extract_expenditure_data(pdf)
                if not df.empty:
                    all_dfs.append(df)

        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            st.success(f"✅ Extracted data from {len(uploaded_pdfs)} PDF(s)!")

            def highlight_row(s):
                return ['background-color: #FFF4E5; font-weight: bold' if v == '**Average**' else '' for v in s]

            styled_df = combined_df.style.apply(highlight_row, subset=["Academic Year"])
            st.dataframe(styled_df, use_container_width=True)

            # Excel Export
            numeric_df = combined_df[combined_df["Academic Year"] != "**Average**"].copy()
            for col in ["Capital Expenditure", "Operational Expenditure", "Total Expenditure"]:
                if col in numeric_df.columns:
                    # CORRECTED LINE: This regex now removes all non-digit characters.
                    numeric_df[col] = numeric_df[col].replace('[^0-9]', '', regex=True).astype(float)

            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                numeric_df.to_excel(writer, index=False, sheet_name="Expenditure Data")
            towrite.seek(0)

            st.download_button(
                label="📥 Download as Excel",
                data=towrite,
                file_name="nirf_expenditure_combined.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Could not extract expenditure data from the uploaded PDFs.")
