import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

def extract_college_info(text):
    """Extracts college name and ID from text."""
    college_name_match = re.search(r"Institute Name:\s*(.*?)\s*\[", text)
    college_code_match = re.search(r"\[(IR-[^\]]+)\]", text)
    college_name = college_name_match.group(1).strip() if college_name_match else "Not Found"
    college_code = college_code_match.group(1).strip() if college_code_match else "Not Found"
    return college_name, college_code

def extract_phd_graduated_data(pdf_file):
    """
    Extracts PhD graduation data by finding and parsing the specific
    'Ph.D Student Details' table.
    """
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Get College Info from the first page
            first_page_text = pdf.pages[0].extract_text()
            if not first_page_text: first_page_text = ""
            college_name, college_code = extract_college_info(first_page_text)

            full_time_grads = {}
            part_time_grads = {}
            years = []

            # Find the specific table on any page
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables: continue

                for table in tables:
                    if not table or len(table) < 2: continue
                    
                    # Check if this is the PhD details table by looking for unique text
                    table_text = " ".join([" ".join(map(str, row)) for row in table])
                    if "No. of Ph.D students graduated" not in table_text:
                        continue
                        
                    # Find the header row with the academic years
                    header_row = []
                    for row in table:
                        if any(re.match(r'\d{4}-\d{2}', str(cell)) for cell in row):
                            header_row = [str(cell).replace('\n', ' ') for cell in row]
                            years = [h for h in header_row if re.match(r'\d{4}-\d{2}', h)]
                            break
                    
                    if not years: continue
                    
                    # Extract data for Full Time and Part Time rows
                    for row in table:
                        row_title = str(row[0]).strip()
                        if "Full Time" in row_title:
                            for i, year in enumerate(years):
                                try:
                                    # Data is usually offset by 1 column from the title
                                    full_time_grads[year] = int(row[i+1])
                                except (ValueError, IndexError, TypeError):
                                    full_time_grads[year] = 0
                        elif "Part Time" in row_title:
                             for i, year in enumerate(years):
                                try:
                                    part_time_grads[year] = int(row[i+1])
                                except (ValueError, IndexError, TypeError):
                                    part_time_grads[year] = 0
                    # Once table is found and processed, no need to check other tables
                    break 
            
            # --- Structure the data into the desired format ---
            if not years:
                return pd.DataFrame()

            rows = []
            sorted_years = sorted(years, reverse=True)
            
            # Row 1: Full Time
            ft_row = {"ProgramName": "Ph.D. Graduated - Full Time"}
            for year in sorted_years:
                ft_row[year] = full_time_grads.get(year, 0)
            ft_row["Total"] = sum(ft_row[year] for year in sorted_years)
            rows.append(ft_row)
            
            # Row 2: Part Time
            pt_row = {"ProgramName": "Ph.D. Graduated - Part Time"}
            for year in sorted_years:
                pt_row[year] = part_time_grads.get(year, 0)
            pt_row["Total"] = sum(pt_row[year] for year in sorted_years)
            rows.append(pt_row)

            # Row 3: Total
            total_row = {"ProgramName": "Ph.D. Graduated - Total"}
            for year in sorted_years:
                total_row[year] = ft_row[year] + pt_row[year]
            total_row["Total"] = sum(total_row[year] for year in sorted_years)
            rows.append(total_row)

            df = pd.DataFrame(rows)
            df.insert(0, 'CollegeCode', college_code)
            df.insert(0, 'CollegeName', college_name)
            df.insert(0, 'SNo', range(1, 1 + len(df)))
            
            return df

    except Exception as e:
        st.error(f"An error occurred during PhD data extraction: {e}")
        return pd.DataFrame()


def phd_data_tab():
    """Streamlit UI for displaying PhD Graduation Data."""
    st.subheader("🎓 Ph.D. Graduation Data Extractor")
    uploaded_files = st.file_uploader(
        "Upload one or more NIRF PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="phd_data_uploader"
    )

    if uploaded_files:
        all_dfs = []
        with st.spinner("Extracting Ph.D. graduation data..."):
            for uploaded_file in uploaded_files:
                df = extract_phd_graduated_data(uploaded_file)
                if not df.empty:
                    all_dfs.append(df)

        if all_dfs:
            st.success(f"✅ Extracted data from {len(all_dfs)} PDF(s)!")
            combined_df = pd.concat(all_dfs, ignore_index=True)
            st.dataframe(combined_df, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                combined_df.to_excel(writer, index=False, sheet_name="PhD Graduated Data")
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download Ph.D. Data as Excel",
                data=processed_data,
                file_name="phd_graduated_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Could not extract Ph.D. graduation data from the uploaded PDFs.")
