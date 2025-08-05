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

def extract_placement_data(pdf_file):
    """
    Extracts placement and higher studies data by finding and parsing specific tables.
    """
    all_placement_data = []
    
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

                    # Identify the table by checking for essential column headers
                    required_cols = ["No. of students graduating in minimum stipulated time", "No. of students placed", "No. of students selected for Higher Studies"]
                    if not all(col in header_row for col in required_cols):
                        continue

                    program_header = find_program_name_for_table(page, table_obj, previous_page_text)
                    prog_name_match = re.search(r"(UG|PG)-(\d+)", program_header.replace(" ", "").replace("[", "-").replace("YearsProgram(s)]", ""))
                    if not prog_name_match: continue
                    prog_type, prog_years = prog_name_match.groups()
                    prog_name = f"{prog_type}-{prog_years}"
                    
                    try:
                        grad_year_col = header_row.index("Academic Year", 1)
                        graduated_col = header_row.index("No. of students graduating in minimum stipulated time")
                        placed_col = header_row.index("No. of students placed")
                        higher_studies_col = header_row.index("No. of students selected for Higher Studies")
                    except (ValueError, StopIteration):
                        continue

                    for row in table_data[1:]:
                        try:
                            grad_year = row[grad_year_col]
                            graduated = int(row[graduated_col].replace(',', ''))
                            placed = int(row[placed_col].replace(',', ''))
                            higher_studies = int(row[higher_studies_col].replace(',', ''))
                            
                            placement_pct = round((placed / graduated) * 100, 2) if graduated > 0 else 0.0
                            higher_pct = round((higher_studies / graduated) * 100, 2) if graduated > 0 else 0.0

                            all_placement_data.append({
                                "CollegeName": college_name,
                                "CollegeCode": college_code,
                                "ProgramName": prog_name,
                                "GraduationYear": grad_year,
                                "Graduated": graduated,
                                "Placed": placed,
                                "Placement %": placement_pct,
                                "Higher Studies": higher_studies,
                                "Higher Studies %": higher_pct
                            })
                        except (ValueError, IndexError, TypeError):
                            continue
                
                previous_page_text = page.extract_text() or ""
        
        if not all_placement_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_placement_data)
        df.insert(0, 'SNo', range(1, 1 + len(df)))
        return df

    except Exception as e:
        st.error(f"An error occurred during placement data extraction: {e}")
        return pd.DataFrame()


def placement_data_tab():
    """Streamlit UI for displaying Placement & Higher Studies Data."""
    st.subheader("🎯 Placement & Higher Studies Extractor")
    uploaded_files = st.file_uploader(
        "Upload one or more NIRF PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="placement_data_uploader"
    )

    if uploaded_files:
        all_dfs = []
        with st.spinner("Extracting placement & higher studies data..."):
            for uploaded_file in uploaded_files:
                df = extract_placement_data(uploaded_file)
                if not df.empty:
                    all_dfs.append(df)

        if all_dfs:
            final_df = pd.concat(all_dfs, ignore_index=True)
            final_df['SNo'] = range(1, 1 + len(final_df))
            st.success(f"✅ Extracted data from {len(all_dfs)} PDF(s)!")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Records", len(final_df))
            with col2:
                st.metric("Avg Placement %", f"{final_df['Placement %'].mean():.1f}%")
            with col3:
                st.metric("Avg Higher Studies %", f"{final_df['Higher Studies %'].mean():.1f}%")
            with col4:
                st.metric("Total Graduated", f"{final_df['Graduated'].sum():,}")

            st.dataframe(final_df, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False, sheet_name="Placement Data")
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download as Excel",
                data=processed_data,
                file_name="placement_higher_studies_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.subheader("📈 Program-wise Summary")
            program_summary = final_df.groupby('ProgramName').agg({
                'Graduated': 'sum',
                'Placed': 'sum',
                'Higher Studies': 'sum',
                'Placement %': 'mean',
                'Higher Studies %': 'mean'
            }).reset_index()
            program_summary['Placement %'] = program_summary['Placement %'].round(2)
            program_summary['Higher Studies %'] = program_summary['Higher Studies %'].round(2)
            st.dataframe(program_summary, use_container_width=True)
        else:
            st.warning("⚠️ No placement data could be extracted. Please check the uploaded PDFs.")
