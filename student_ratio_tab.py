import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

def extract_student_ratio_data(pdf_file):
    """
    Extracts student gender ratio data from a specific table in a NIRF PDF.

    This function opens a PDF, finds the college name and ID, then looks for the
    'Total Actual Student Strength' table. It extracts program names, total students,
    and female students, calculates the female ratio, and returns a pandas DataFrame.

    Args:
        pdf_file: A file-like object representing the uploaded PDF.

    Returns:
        A pandas DataFrame with the extracted student ratio data. Returns an empty
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
                
                # Extract tables from the current page.
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue

                    # Clean the header row for reliable identification.
                    # Headers can sometimes have newlines.
                    header = [str(cell).replace('\n', ' ') if cell else '' for cell in table[0]]

                    # Check for the specific headers of the "Total Actual Student Strength" table.
                    if 'No. of Male Students' in header and 'No. of Female Students' in header and 'Total Students' in header:
                        table_found = True
                        
                        try:
                            # Get the column indices based on header names.
                            program_col_idx = 0  # Program name is typically the first column.
                            female_col_idx = header.index('No. of Female Students')
                            total_col_idx = header.index('Total Students')
                        except ValueError:
                            # If a required header is missing, skip this table.
                            continue

                        # Iterate through the rows of the identified table, skipping the header.
                        for row in table[1:]:
                            program_name_raw = row[program_col_idx]
                            
                            # Ensure the program name cell is not empty.
                            if not program_name_raw or not program_name_raw.strip():
                                continue
                            
                            # Clean up the program name.
                            program_name = program_name_raw.replace('\n', ' ').strip()

                            # Process only the rows that correspond to UG/PG programs.
                            if program_name.startswith("UG [") or program_name.startswith("PG ["):
                                try:
                                    # Extract and clean the numeric strings.
                                    total_students_str = row[total_col_idx].replace(',', '').strip()
                                    female_students_str = row[female_col_idx].replace(',', '').strip()

                                    if total_students_str and female_students_str:
                                        total_students = int(total_students_str)
                                        female_students = int(female_students_str)

                                        # Calculate the female ratio, handling division by zero.
                                        ratio = round((female_students / total_students) * 100, 2) if total_students > 0 else 0

                                        data.append({
                                            "S.No": s_no,
                                            "College Name": college_name,
                                            "College ID": college_id,
                                            "Program": program_name,
                                            "Total Students": total_students,
                                            "Female Students": female_students,
                                            "Female Ratio (%)": ratio
                                        })
                                        s_no += 1
                                except (ValueError, TypeError, IndexError):
                                    # This will catch errors if a cell is empty, not a number, or doesn't exist.
                                    # Continue to the next row.
                                    continue
                        # Once the correct table is found and processed, exit the loop.
                        if table_found:
                            break
    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {e}")
        return pd.DataFrame() # Return an empty dataframe on error

    return pd.DataFrame(data)

def student_ratio_tab():
    """
    Streamlit UI function to upload PDFs and display extracted student ratio data.
    """
    st.subheader("📊 Student Gender Ratio Extractor")
    uploaded_pdfs = st.file_uploader("Upload NIRF PDFs", type="pdf", accept_multiple_files=True, key="student_ratio_uploader")

    if uploaded_pdfs:
        all_data = []
        with st.spinner("Extracting data from PDF(s)..."):
            for pdf_file in uploaded_pdfs:
                # Rewind the file buffer before passing it to the extraction function.
                pdf_file.seek(0)
                df = extract_student_ratio_data(pdf_file)
                if not df.empty:
                    all_data.append(df)

        if all_data:
            # Combine data from all uploaded PDFs into a single DataFrame.
            final_df = pd.concat(all_data, ignore_index=True)
            st.success("✅ Data extracted successfully!")
            st.dataframe(final_df, use_container_width=True)

            # Prepare the data for Excel download.
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name="Student Ratio")
            # Seek to the beginning of the stream.
            towrite.seek(0)

            st.download_button(
                label="📥 Download as Excel",
                data=towrite,
                file_name="student_ratio_extracted.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ Could not find or extract student ratio data from the uploaded PDF(s). Please check the file format.")
