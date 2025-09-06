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

def extract_phd_intake_data(pdf_file):
    """
    Extracts the number of students pursuing a Ph.D. (Full Time and Part Time).
    This logic is robust and specifically targets the correct section of the table,
    inspired by the proven logic from phd_data_tab.py.
    """
    try:
        with pdfplumber.open(pdf_file) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            if not first_page_text: first_page_text = ""
            college_name, college_code = extract_college_info(first_page_text)

            phd_data = []
            data_found = False
            
            for page in pdf.pages:
                if data_found: break
                tables = page.extract_tables()
                if not tables: continue

                for table in tables:
                    if not table: continue
                    table_text = " ".join(" ".join(map(str, row)) for row in table)

                    if "Ph.D Student Details" in table_text and "pursuing doctoral program" in table_text:
                        
                        year_match = re.search(r'till (\d{4}-\d{2})', table_text)
                        academic_year = year_match.group(1) if year_match else "Unknown"

                        full_time_students = 0
                        part_time_students = 0

                        # Find the row index for the "Total Students" header as an anchor
                        total_students_header_row_idx = -1
                        for i, row in enumerate(table):
                            row_text = " ".join([str(cell) for cell in row if cell])
                            if "Total Students" in row_text and "graduated" not in row_text.lower():
                                total_students_header_row_idx = i
                                break
                        
                        # If the anchor is found, scan the rows below it for the data
                        if total_students_header_row_idx != -1:
                            for row in table[total_students_header_row_idx + 1:]:
                                row_text = " ".join([str(cell) for cell in row if cell])
                                
                                # Stop scanning if we hit the 'graduated' section to avoid errors
                                if "graduated" in row_text.lower():
                                    break
                                
                                # Find Full Time students
                                if "Full Time" in row_text:
                                    numbers = re.findall(r'(\d+)', row_text)
                                    if numbers:
                                        full_time_students = int(numbers[0])
                                
                                # Find Part Time students
                                if "Part Time" in row_text:
                                    numbers = re.findall(r'(\d+)', row_text)
                                    if numbers:
                                        part_time_students = int(numbers[0])

                        if full_time_students > 0:
                            phd_data.append({
                                "College Name": college_name,
                                "College Code": college_code,
                                "Program Name": "Ph.D. - Full Time",
                                "Academic Year": academic_year,
                                "Total Students": full_time_students
                            })
                        
                        if part_time_students > 0:
                             phd_data.append({
                                "College Name": college_name,
                                "College Code": college_code,
                                "Program Name": "Ph.D. - Part Time",
                                "Academic Year": academic_year,
                                "Total Students": part_time_students
                            })
                        
                        if phd_data:
                            data_found = True
                            break
                if data_found:
                    break
            
            if not phd_data: return pd.DataFrame()

            df = pd.DataFrame(phd_data)
            df.insert(0, 'S.No', range(1, 1 + len(df)))
            return df

    except Exception as e:
        st.error(f"An error occurred during Ph.D. Intake extraction: {e}")
        return pd.DataFrame()

def phd_intake_tab():
    """Streamlit UI for displaying Ph.D. Student Intake Data."""
    st.subheader("🔬 Ph.D. Student Intake (Pursuing)")
    uploaded_files = st.file_uploader(
        "Upload one or more NIRF PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="phd_intake_uploader"
    )

    if uploaded_files:
        all_dfs = []
        with st.spinner("Extracting Ph.D. student intake data..."):
            for uploaded_file in uploaded_files:
                df = extract_phd_intake_data(uploaded_file)
                if not df.empty:
                    all_dfs.append(df)

        if all_dfs:
            st.success(f"✅ Extracted data from {len(all_dfs)} PDF(s)!")
            combined_.df = pd.concat(all_dfs, ignore_index=True)
            st.dataframe(combined_df, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                combined_df.to_excel(writer, index=False, sheet_name="PhD Intake Data")
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download Ph.D. Intake Data as Excel",
                data=processed_data,
                file_name="phd_intake_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ Could not extract Ph.D. student intake data from the uploaded PDFs.")

