import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
from collections import defaultdict

def extract_project_funding_data(pdf_file):
    """
    Extracts and combines sponsored research and consultancy project data from a NIRF PDF.

    This function finds the 'Sponsored Research Details' and 'Consultancy Project Details'
    tables, which are structured vertically by financial year. It extracts the data,
    combines it by year, and calculates the total funding.

    Args:
        pdf_file: A file-like object representing the uploaded PDF.

    Returns:
        A pandas DataFrame with the combined project and funding data, or an empty
        DataFrame if the tables are not found.
    """
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Extract basic college info from the first page.
            first_page_text = pdf.pages[0].extract_text()
            college_name_match = re.search(r"Institute Name:\s*(.*?)\s*\[", first_page_text)
            college_id_match = re.search(r"\[(IR-[A-Z]-[A-Z]-\d+)\]", first_page_text)
            
            college_name = college_name_match.group(1).strip() if college_name_match else "Unknown"
            college_id = college_id_match.group(1).strip() if college_id_match else "Unknown"

            sponsored_data = defaultdict(dict)
            consultancy_data = defaultdict(dict)

            # --- Helper function to process the vertical table structure ---
            def process_vertical_table(table, data_dict, project_key, amount_key):
                if not table or len(table) < 2:
                    return
                
                # The first row contains 'Financial Year' and the years themselves.
                years = [y.strip() for y in table[0][1:] if y and y.strip()]
                
                # Iterate over the other rows to find the data we need.
                for row in table[1:]:
                    metric_name = row[0].replace('\n', ' ').strip()
                    values = [v.strip() for v in row[1:] if v and v.strip()]
                    
                    # Ensure we have a value for each year.
                    if len(values) < len(years): continue

                    for i, year in enumerate(years):
                        try:
                            value_int = int(values[i].replace(',', ''))
                            if 'Total no. of Sponsored Projects' in metric_name:
                                data_dict[year][project_key] = value_int
                            elif 'Total no. of Consultancy Projects' in metric_name:
                                data_dict[year][project_key] = value_int
                            elif 'Total Amount Received (Amount in Rupees)' in metric_name:
                                data_dict[year][amount_key] = value_int
                        except (ValueError, IndexError):
                            continue

            # --- Find and process the tables ---
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table: continue
                    
                    # Identify tables by the unique text in their first column.
                    first_column_text = " ".join(str(row[0]) for row in table if row and row[0])
                    
                    if 'Sponsored Projects' in first_column_text:
                        process_vertical_table(table, sponsored_data, 'sponsored_projects', 'sponsored_amount')
                    
                    if 'Consultancy Projects' in first_column_text:
                        process_vertical_table(table, consultancy_data, 'consultancy_projects', 'consultancy_amount')

            # --- Combine the extracted data ---
            combined_data = []
            all_years = sorted(list(set(sponsored_data.keys()) | set(consultancy_data.keys())), reverse=True)
            s_no = 1
            
            for year in all_years:
                s_projects = sponsored_data[year].get('sponsored_projects', 0)
                s_amount = sponsored_data[year].get('sponsored_amount', 0)
                c_projects = consultancy_data[year].get('consultancy_projects', 0)
                c_amount = consultancy_data[year].get('consultancy_amount', 0)
                total_amount = s_amount + c_amount

                combined_data.append({
                    "S.No": s_no,
                    "College Name": college_name,
                    "College ID": college_id,
                    "Financial Year": year,
                    "Total no. of Sponsored Projects": s_projects,
                    "Total Amount Received (Sponsored)": s_amount,
                    "Total no. of Consultancy Projects": c_projects,
                    "Total Amount Received (Consultancy)": c_amount,
                    "Total Sanctioned Amount": total_amount
                })
                s_no += 1
            
            if not combined_data:
                return pd.DataFrame()

            return pd.DataFrame(combined_data)

    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {e}")
        return pd.DataFrame()

def project_funding_tab():
    """
    Streamlit UI function to upload PDFs and display extracted project funding data.
    """
    st.subheader("💰 Sponsored Projects & Consultancy Funding Extractor")
    uploaded_pdfs = st.file_uploader(
        "Upload NIRF PDFs for Project Funding Analysis",
        type="pdf",
        accept_multiple_files=True,
        key="project_funding_uploader" # Unique key
    )

    if uploaded_pdfs:
        all_data = []
        with st.spinner("Extracting project funding data from PDF(s)..."):
            for pdf_file in uploaded_pdfs:
                pdf_file.seek(0)
                df = extract_project_funding_data(pdf_file)
                if not df.empty:
                    all_data.append(df)

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            st.success("✅ Data extracted successfully!")
            st.dataframe(final_df, use_container_width=True)

            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name="Project Funding")
            towrite.seek(0)

            st.download_button(
                label="📥 Download as Excel",
                data=towrite,
                file_name="project_funding_extracted.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ Could not find or extract project funding data from the uploaded PDF(s).")
