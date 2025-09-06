import streamlit as st
import pandas as pd
import io
import requests
import re

# Assuming url_utils.py exists and is correct
from url_utils import extract_pdf_links_from_url

def reformat_data_for_full_report(df, extractor_name):
    """
    Transforms a standard DataFrame from any extractor into a two-column
    'Parameter' and 'Value' format for the full report. This is a more robust
    implementation with specific logic for each data type.
    """
    report_rows = []
    
    # Standard columns to ignore when creating parameter names
    ignore_cols = ['SNo', 'S.No', 'CollegeName', 'CollegeCode', 'ProgramName', 'Program', 'Academic Year', 'Financial Year', 'GraduationYear']

    if df.empty:
        return pd.DataFrame()

    # Iterate through each row of the input dataframe to create parameter-value pairs
    for _, row in df.iterrows():
        # Create a context string (e.g., from Program Name or Year) to make parameters unique
        context = ""
        if 'ProgramName' in row and pd.notna(row['ProgramName']):
            context += f" ({row['ProgramName']})"
        if 'Program' in row and pd.notna(row['Program']):
            context += f" ({row['Program']})"
        if 'Academic Year' in row and pd.notna(row['Academic Year']):
            context += f" ({row['Academic Year']})"
        if 'Financial Year' in row and pd.notna(row['Financial Year']):
            context += f" ({row['Financial Year']})"
        if 'GraduationYear' in row and pd.notna(row['GraduationYear']):
            context += f" (Graduating {row['GraduationYear']})"

        # Create a key-value pair for each relevant column in the row
        for col_name, value in row.items():
            if col_name not in ignore_cols:
                parameter_name = f"{col_name}{context}".strip()
                report_rows.append({'Parameter': parameter_name, 'Value': value})

    return pd.DataFrame(report_rows)


def full_report_tab(master_extractors_list):
    st.title("📑 NIRF Full Report Generator")
    st.info(
        "Upload multiple NIRF PDFs or provide a URL to a page containing PDF links. "
        "The tool will generate a consolidated two-column report for each college, with a final option to download all reports in a single Excel file."
    )

    pdf_files_to_process = []
    
    with st.form(key="full_report_form"):
        st.subheader("Option 1: Extract from URL")
        url_input = st.text_input("Enter a URL to scrape for PDF files:")

        st.subheader("Option 2: Extract from Uploaded PDFs")
        uploaded_files = st.file_uploader(
            "Or upload one or more NIRF PDF files here:",
            type="pdf",
            accept_multiple_files=True,
            key="full_report_uploader"
        )
        
        submit_button = st.form_submit_button(label="🚀 Generate Full Report", type="primary")

    if submit_button:
        if url_input:
            with st.spinner("Scraping URL for PDF links..."):
                try:
                    pdf_links = extract_pdf_links_from_url(url_input)
                    st.success(f"Found {len(pdf_links)} PDF links. Downloading and processing...")
                    for link in pdf_links:
                        response = requests.get(link, timeout=15)
                        pdf_files_to_process.append(io.BytesIO(response.content))
                except Exception as e:
                    st.error(f"Failed to process URL: {e}")
        
        if uploaded_files:
            pdf_files_to_process.extend(uploaded_files)

        if not pdf_files_to_process:
            st.warning("Please provide a URL or upload files to generate a report.")
            return

        # --- Process each PDF and generate reports ---
        all_college_reports = {}
        progress_bar = st.progress(0, text="Starting report generation...")

        for i, pdf_file in enumerate(pdf_files_to_process):
            report_data = []
            college_name, college_code = "Unknown College", f"PDF_{i+1}"
            
            for name, func in master_extractors_list:
                try:
                    pdf_file.seek(0)
                    df = func(pdf_file)
                    if not df.empty:
                        if college_name == "Unknown College" and 'CollegeName' in df.columns:
                            college_name = df['CollegeName'].iloc[0]
                            college_code = df['CollegeCode'].iloc[0]
                        
                        report_df = reformat_data_for_full_report(df, name)
                        if not report_df.empty:
                            report_data.append(report_df)
                except Exception as e:
                    st.error(f"Error in '{name}' for {college_code}: {e}")
            
            progress_bar.progress((i + 1) / len(pdf_files_to_process), f"Processed {college_name}")

            if report_data:
                final_report_df = pd.concat(report_data, ignore_index=True)
                # Remove duplicate parameters if any, keeping the first instance
                final_report_df = final_report_df.drop_duplicates(subset='Parameter', keep='first')
                all_college_reports[f"{college_name} | {college_code}"] = final_report_df
        
        progress_bar.empty()

        # --- Display reports in tabs and provide Excel download ---
        if all_college_reports:
            st.success("✅ All reports generated successfully!")
            tab_names = list(all_college_reports.keys())
            tabs = st.tabs(tab_names)
            
            for i, tab_name in enumerate(tab_names):
                with tabs[i]:
                    st.dataframe(all_college_reports[tab_name], use_container_width=True, hide_index=True)
            
            # --- Consolidated Multi-Sheet Excel Download ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for sheet_name, report_df in all_college_reports.items():
                    # Sanitize sheet name for Excel
                    safe_sheet_name = re.sub(r'[\\/*?:"<>|]', "", sheet_name)[:31]
                    report_df.to_excel(writer, index=False, sheet_name=safe_sheet_name)
            
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download All Reports as Excel (One Sheet per College)",
                data=processed_data,
                file_name="nirf_full_report_all_colleges.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_full_report_excel"
            )
        else:
            st.warning("Could not extract any data from the provided PDFs.")

