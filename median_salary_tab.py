import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
import numpy as np

def extract_college_info(text):
    """Extracts college name and ID from text."""
    college_name_match = re.search(r"Institute Name:\s*(.*?)\s*\[", text)
    college_code_match = re.search(r"\[(IR-[^\]]+)\]", text)
    college_name = college_name_match.group(1).strip() if college_name_match else "Not Found"
    college_code = college_code_match.group(1).strip() if college_code_match else "Not Found"
    return college_name, college_code

def find_program_name_for_table(page, table_obj, previous_page_text=""):
    """
    Finds the program name associated with a table, looking on the current page first,
    then on the previous page's text if the table is at the top of the current page.
    """
    table_y_position = table_obj.bbox[1]
    text_above_table = page.crop((0, 0, page.width, table_y_position)).extract_text()
    
    if text_above_table:
        matches = re.findall(r"(UG \[\d+ Years? Program\(s\)\]|PG \[\d+ Years? Program\(s\)\])", text_above_table)
        if matches:
            return matches[-1]

    if table_y_position < 150 and previous_page_text:
        matches = re.findall(r"(UG \[\d+ Years? Program\(s\)\]|PG \[\d+ Years? Program\(s\)\])", previous_page_text)
        if matches:
            return matches[-1]
    
    return "Unknown Program"

def extract_median_salary_data(pdf_file):
    """
    Extracts median salary data, with each academic year as a separate row,
    and adds a column for the average salary per program.
    """
    all_salary_data = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            if not first_page_text: first_page_text = ""
            college_name, college_code = extract_college_info(first_page_text)

            previous_page_text = ""
            for page in pdf.pages:
                table_objects = page.find_tables()
                if not table_objects:
                    previous_page_text = page.extract_text() or ""
                    continue

                for table_obj in table_objects:
                    table_data = table_obj.extract()
                    if not table_data or len(table_data) < 2: continue
                    
                    header_row = [str(cell).replace('\n', ' ') if cell else '' for cell in table_data[0]]

                    if not any("Median salary of placed graduates" in col for col in header_row):
                        continue

                    program_header = find_program_name_for_table(page, table_obj, previous_page_text)
                    prog_name_match = re.search(r"(UG|PG) \[(\d+)", program_header)
                    if not prog_name_match: continue
                    prog_type, prog_years = prog_name_match.groups()
                    prog_name = f"{prog_type}-{prog_years}"

                    try:
                        grad_year_col = header_row.index("Academic Year", 1)
                        salary_col = next(i for i, col in enumerate(header_row) if "Median salary" in col)
                    except (ValueError, StopIteration):
                        continue

                    for row in table_data[1:]:
                        try:
                            grad_year = row[grad_year_col]
                            salary_str = re.search(r'(\d[\d,]+)', str(row[salary_col]))
                            if salary_str:
                                salary = int(salary_str.group(1).replace(',', ''))
                                all_salary_data.append({
                                    "CollegeName": college_name,
                                    "CollegeCode": college_code,
                                    "ProgramName": prog_name,
                                    "Academic Year": grad_year,
                                    "Median Salary": salary
                                })
                        except (ValueError, IndexError, TypeError):
                            continue
                
                previous_page_text = page.extract_text() or ""
        
        if not all_salary_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_salary_data)
        
        # --- NEW: Calculate and format the average salary column ---
        
        # Calculate the average salary for each program group
        df['Average Median Salary'] = df.groupby('ProgramName')['Median Salary'].transform('mean')
        
        # Sort values to ensure consistent ordering before hiding duplicates
        df = df.sort_values(by=['ProgramName', 'Academic Year'], ascending=[True, False])
        
        # Identify duplicate program entries to hide the average value
        mask = df.duplicated(subset='ProgramName', keep='first')
        
        # Set the average for duplicate rows to NaN, so it appears blank
        df.loc[mask, 'Average Median Salary'] = np.nan
        
        # Format the numbers into a more readable currency format for display
        df['Median Salary'] = df['Median Salary'].apply(lambda x: f"₹{x:,.0f}")
        df['Average Median Salary'] = df['Average Median Salary'].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "")

        # Add the S.No column at the end to ensure it's sequential
        df.insert(0, 'SNo', range(1, 1 + len(df)))
        
        return df

    except Exception as e:
        st.error(f"An error occurred during median salary extraction: {e}")
        return pd.DataFrame()


def median_salary_tab():
    """Streamlit UI for displaying Median Salary Data."""
    st.subheader("💰 Median Salary Extractor")
    uploaded_files = st.file_uploader(
        "Upload one or more NIRF PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="median_salary_uploader"
    )

    if uploaded_files:
        all_dfs = []
        with st.spinner("Extracting median salary data..."):
            for uploaded_file in uploaded_files:
                df = extract_median_salary_data(uploaded_file)
                if not df.empty:
                    all_dfs.append(df)

        if all_dfs:
            st.success(f"✅ Extracted data from {len(all_dfs)} PDF(s)!")
            combined_df = pd.concat(all_dfs, ignore_index=True)
            # Reset S.No after combining data from multiple files
            combined_df['SNo'] = range(1, 1 + len(combined_df))
            st.dataframe(combined_df, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                combined_df.to_excel(writer, index=False, sheet_name="Median Salary Data")
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download Median Salary Data as Excel",
                data=processed_data,
                file_name="median_salary_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Could not extract median salary data from the uploaded PDFs.")
