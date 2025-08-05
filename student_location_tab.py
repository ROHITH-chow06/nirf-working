import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

def extract_student_location_data(pdf_file):
    """
    Extracts student location data from a specific table in a NIRF PDF.

    This function opens a PDF, finds the college name and ID, then looks for the
    'Total Actual Student Strength' table. It extracts total students, students from
    outside the state, and students from outside the country, calculates their
    respective percentages, and returns a pandas DataFrame.

    Args:
        pdf_file: A file-like object representing the uploaded PDF.

    Returns:
        A pandas DataFrame with the extracted student location data. Returns an empty
        DataFrame if the target table is not found or data cannot be extracted.
    """
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Extract institute name and ID from the first page's text for context.
            first_page_text = pdf.pages[0].extract_text()
            college_name_match = re.search(r"Institute Name:\s*(.*?)\s*\[", first_page_text)
            college_id_match = re.search(r"\[(IR-[A-Z]-[A-Z]-\d+)\]", first_page_text)
            
            college_name = college_name_match.group(1).strip() if college_name_match else "Unknown"
            college_id = college_id_match.group(1).strip() if college_id_match else "Unknown"

            data = []
            s_no = 1
            table_found = False

            # We'll search for the correct table on the first few pages.
            for page in pdf.pages:
                if table_found:
                    break
                
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue

                    # Clean the header row to handle newlines and make identification reliable.
                    header = [str(cell).replace('\n', ' ') if cell else '' for cell in table[0]]

                    # Define the headers for the target table.
                    required_headers = [
                        'Total Students',
                        'Outside State (Including male & female)',
                        'Outside Country (Including male & female)'
                    ]

                    # Check if all required headers are present in the current table.
                    if all(h in header for h in required_headers):
                        table_found = True
                        
                        try:
                            # Get the column indices based on header names.
                            program_col_idx = 0  # Program name is typically the first column.
                            total_col_idx = header.index('Total Students')
                            outside_state_col_idx = header.index('Outside State (Including male & female)')
                            outside_country_col_idx = header.index('Outside Country (Including male & female)')
                        except ValueError:
                            # If a required header is missing (should not happen due to check above), skip.
                            continue

                        # Iterate through the rows of the identified table, skipping the header.
                        for row in table[1:]:
                            program_name_raw = row[program_col_idx]
                            
                            if not program_name_raw or not program_name_raw.strip():
                                continue
                            
                            program_name = program_name_raw.replace('\n', ' ').strip()

                            # Process only the rows that correspond to UG/PG programs.
                            if program_name.startswith("UG [") or program_name.startswith("PG ["):
                                try:
                                    # Extract and clean the numeric strings.
                                    total_students_str = row[total_col_idx].replace(',', '').strip()
                                    outside_state_str = row[outside_state_col_idx].replace(',', '').strip()
                                    outside_country_str = row[outside_country_col_idx].replace(',', '').strip()

                                    if total_students_str and outside_state_str and outside_country_str:
                                        total_students = int(total_students_str)
                                        outside_state = int(outside_state_str)
                                        outside_country = int(outside_country_str)

                                        # Calculate ratios, handling division by zero.
                                        state_ratio = round((outside_state / total_students) * 100, 2) if total_students > 0 else 0
                                        country_ratio = round((outside_country / total_students) * 100, 2) if total_students > 0 else 0

                                        data.append({
                                            "S.No": s_no,
                                            "College Name": college_name,
                                            "College ID": college_id,
                                            "Program": program_name,
                                            "Total Students": total_students,
                                            "Outside State (Count & %)": f"{outside_state} ({state_ratio:.2f}%)",
                                            "Outside Country (Count & %)": f"{outside_country} ({country_ratio:.2f}%)"
                                        })
                                        s_no += 1
                                except (ValueError, TypeError, IndexError):
                                    # Catches errors if a cell is empty, not a number, or doesn't exist.
                                    continue
                        if table_found:
                            break
    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {e}")
        return pd.DataFrame()

    return pd.DataFrame(data)

def student_location_tab():
    """
    Streamlit UI function to upload PDFs and display extracted student location data.
    """
    st.subheader("📍 Student Location Extractor")
    uploaded_pdfs = st.file_uploader("Upload NIRF PDFs", type="pdf", accept_multiple_files=True, key="student_location")

    if uploaded_pdfs:
        all_data = []
        with st.spinner("Extracting location data from PDF(s)..."):
            for pdf_file in uploaded_pdfs:
                pdf_file.seek(0)
                df = extract_student_location_data(pdf_file)
                if not df.empty:
                    all_data.append(df)

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            st.success("✅ Location data extracted successfully!")
            st.dataframe(final_df, use_container_width=True)

            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name="Student Location")
            towrite.seek(0)

            st.download_button(
                label="📥 Download as Excel",
                data=towrite,
                file_name="student_location_extracted.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ Could not find or extract student location data from the uploaded PDF(s).")
