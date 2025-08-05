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

def find_program_name_for_table(page, table_obj, previous_page_text=""):
    """
    Finds the program name associated with a table, looking on the current page first,
    then on the previous page's text if the table is at the top of the current page.
    """
    table_y_position = table_obj.bbox[1]
    
    # Crop the page to only include text above the table
    text_above_table = page.crop((0, 0, page.width, table_y_position)).extract_text()
    
    # First, search for a header in the text immediately above the table on the same page.
    if text_above_table:
        matches = re.findall(r"(UG \[\d+ Years? Program\(s\)\]|PG \[\d+ Years? Program\(s\)\])", text_above_table)
        if matches:
            # The last match is the one closest to the table.
            return matches[-1]

    # If no header is found above and the table is near the top of the page (e.g., y < 150),
    # it's likely that the header is at the bottom of the previous page.
    if table_y_position < 150 and previous_page_text:
        matches = re.findall(r"(UG \[\d+ Years? Program\(s\)\]|PG \[\d+ Years? Program\(s\)\])", previous_page_text)
        if matches:
            # The last header from the previous page is the most likely candidate.
            return matches[-1]
    
    return "Unknown Program"


def extract_university_exam_data(pdf_file):
    """
    Extracts university examination data by finding and parsing specific tables
    related to placement and higher studies for each program.
    """
    all_exam_data = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            if not first_page_text: first_page_text = ""
            college_name, college_code = extract_college_info(first_page_text)

            previous_page_text = ""
            for page in pdf.pages:
                # Use find_tables() to get Table objects with bbox properties
                table_objects = page.find_tables()
                if not table_objects:
                    previous_page_text = page.extract_text() or ""
                    continue

                for table_obj in table_objects:
                    # .extract() gets the table data as a list of lists
                    table_data = table_obj.extract()
                    if not table_data or len(table_data) < 2: continue
                    
                    header_row = [str(cell).replace('\n', ' ') if cell else '' for cell in table_data[0]]

                    # Identify the table by checking for essential column headers
                    required_cols = ["No. of first year students admitted in the year", "No. of students graduating in minimum stipulated time"]
                    if not all(col in header_row for col in required_cols):
                        continue

                    # If it's the right kind of table, find its program name
                    program_header = find_program_name_for_table(page, table_obj, previous_page_text)
                    prog_name_match = re.search(r"(UG|PG) \[(\d+)", program_header)
                    if not prog_name_match: continue
                    prog_type, prog_years = prog_name_match.groups()
                    prog_name = f"{prog_type}-{prog_years}"

                    # Find the indices of the columns we need
                    try:
                        admit_year_col = header_row.index("Academic Year")
                        admitted_col = header_row.index("No. of first year students admitted in the year")
                        grad_year_col = header_row.index("Academic Year", admit_year_col + 1)
                        graduated_col = header_row.index("No. of students graduating in minimum stipulated time")
                        lateral_entry_col = header_row.index("No. of students admitted through Lateral entry") if "No. of students admitted through Lateral entry" in header_row else -1
                    except ValueError:
                        continue

                    for row in table_data[1:]:
                        try:
                            admit_year = row[admit_year_col]
                            grad_year = row[grad_year_col]
                            
                            admitted = int(row[admitted_col].replace(',', ''))
                            graduated = int(row[graduated_col].replace(',', ''))
                            
                            lateral_admitted = 0
                            if lateral_entry_col != -1 and row[lateral_entry_col] and row[lateral_entry_col].strip().isdigit():
                                lateral_admitted = int(row[lateral_entry_col].replace(',', ''))
                            
                            total_admitted = admitted + lateral_admitted
                            percentage = round((graduated / total_admitted) * 100, 2) if total_admitted > 0 else 0.0

                            all_exam_data.append({
                                "CollegeName": college_name,
                                "CollegeCode": college_code,
                                "ProgramName": prog_name,
                                "AdmitYear": admit_year,
                                "GraduationYear": grad_year,
                                "TotalAdmitted": total_admitted,
                                "Graduated": graduated,
                                "Percentage": percentage
                            })
                        except (ValueError, IndexError, TypeError):
                            continue
                
                previous_page_text = page.extract_text() or ""
        
        if not all_exam_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_exam_data)
        df.insert(0, 'SNo', range(1, 1 + len(df)))
        return df

    except Exception as e:
        st.error(f"An error occurred during exam data extraction: {e}")
        return pd.DataFrame()


def university_exam_tab():
    """Streamlit UI for displaying University Examination Data."""
    st.subheader("📘 University Examination Data Extractor")
    uploaded_files = st.file_uploader(
        "Upload one or more NIRF PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="university_exam_uploader"
    )

    if uploaded_files:
        all_dfs = []
        with st.spinner("Extracting university examination data..."):
            for uploaded_file in uploaded_files:
                df = extract_university_exam_data(uploaded_file)
                if not df.empty:
                    all_dfs.append(df)

        if all_dfs:
            st.success(f"✅ Extracted data from {len(all_dfs)} PDF(s)!")
            combined_df = pd.concat(all_dfs, ignore_index=True)
            st.dataframe(combined_df, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                combined_df.to_excel(writer, index=False, sheet_name="Exam Data")
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download University Exam Data as Excel",
                data=processed_data,
                file_name="university_exam_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Could not extract university examination data from the uploaded PDFs.")
