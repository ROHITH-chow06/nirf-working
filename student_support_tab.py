import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

def extract_student_support_data(pdf_file):
    """
    Extracts student financial support and demographic data from a NIRF PDF.

    This function locates the 'Total Actual Student Strength' table and extracts data
    related to economically backward, socially challenged, and fee reimbursement status
    for students in each program.

    Args:
        pdf_file: A file-like object representing the uploaded PDF.

    Returns:
        A pandas DataFrame with the extracted data. Returns an empty
        DataFrame if the target table or columns are not found.
    """
    try:
        with pdfplumber.open(pdf_file) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            college_name_match = re.search(r"Institute Name:\s*(.*?)\s*\[", first_page_text)
            college_id_match = re.search(r"\[(IR-[A-Z]-[A-Z]-\d+)\]", first_page_text)
            
            college_name = college_name_match.group(1).strip() if college_name_match else "Unknown"
            college_id = college_id_match.group(1).strip() if college_id_match else "Unknown"

            data = []
            s_no = 1
            table_found = False

            for page in pdf.pages:
                if table_found:
                    break
                
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue

                    # Clean header row, merging multi-line cells for reliable matching.
                    header = [str(cell).replace('\n', ' ') if cell else '' for cell in table[0]]

                    # Define the headers we need to find in the table.
                    # Note: Some headers are long and might be split across lines.
                    required_headers = [
                        'Economically Backward (Including male & female)',
                        'Socially Challenged (SC+ST+OBC Including male & female)',
                        'No. of students receiving full tuition fee reimbursement from the State and Central Government',
                        'No. of students receiving full tuition fee reimbursement from Institution Funds',
                        'No. of students receiving full tuition fee reimbursement from the Private Bodies',
                        'No. of students who are not receiving full tuition fee reimbursement'
                    ]
                    
                    # Check if all required headers are present.
                    if all(h in header for h in required_headers):
                        table_found = True
                        
                        try:
                            # Get column indices for the required data.
                            program_col_idx = 0
                            eb_col_idx = header.index(required_headers[0])
                            sc_col_idx = header.index(required_headers[1])
                            gov_fee_col_idx = header.index(required_headers[2])
                            inst_fee_col_idx = header.index(required_headers[3])
                            pvt_fee_col_idx = header.index(required_headers[4])
                            no_fee_col_idx = header.index(required_headers[5])
                        except ValueError:
                            continue

                        # Process rows in the found table.
                        for row in table[1:]:
                            program_name_raw = row[program_col_idx]
                            if not program_name_raw or not program_name_raw.strip():
                                continue
                            
                            program_name = program_name_raw.replace('\n', ' ').strip()

                            if program_name.startswith("UG [") or program_name.startswith("PG ["):
                                try:
                                    # Extract data, clean it, and convert to integer.
                                    eb_count = int(row[eb_col_idx].replace(',', '').strip())
                                    sc_count = int(row[sc_col_idx].replace(',', '').strip())
                                    gov_fee = int(row[gov_fee_col_idx].replace(',', '').strip())
                                    inst_fee = int(row[inst_fee_col_idx].replace(',', '').strip())
                                    pvt_fee = int(row[pvt_fee_col_idx].replace(',', '').strip())
                                    no_fee = int(row[no_fee_col_idx].replace(',', '').strip())

                                    data.append({
                                        "S.No": s_no,
                                        "College Name": college_name,
                                        "College ID": college_id,
                                        "Program": program_name,
                                        "Economically Backward": eb_count,
                                        "Socially Challenged (SC+ST+OBC)": sc_count,
                                        "Reimbursed by Govt.": gov_fee,
                                        "Reimbursed by Institution": inst_fee,
                                        "Reimbursed by Private Bodies": pvt_fee,
                                        "Not Reimbursed": no_fee
                                    })
                                    s_no += 1
                                except (ValueError, TypeError, IndexError):
                                    continue
                        if table_found:
                            break
    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {e}")
        return pd.DataFrame()

    return pd.DataFrame(data)

def student_support_tab():
    """
    Streamlit UI function to upload PDFs and display extracted student support data.
    """
    st.subheader("📄 Student Support & Fee Status Extractor")
    uploaded_pdfs = st.file_uploader(
        "Upload NIRF PDFs for Support & Fee Analysis",
        type="pdf",
        accept_multiple_files=True,
        key="student_support_uploader" # Unique key
    )

    if uploaded_pdfs:
        all_data = []
        with st.spinner("Extracting support and fee data from PDF(s)..."):
            for pdf_file in uploaded_pdfs:
                pdf_file.seek(0)
                df = extract_student_support_data(pdf_file)
                if not df.empty:
                    all_data.append(df)

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            st.success("✅ Data extracted successfully!")
            st.dataframe(final_df, use_container_width=True)

            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name="Student Support")
            towrite.seek(0)

            st.download_button(
                label="📥 Download as Excel",
                data=towrite,
                file_name="student_support_extracted.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ Could not find or extract student support data from the uploaded PDF(s).")
