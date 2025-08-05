import streamlit as st
import pandas as pd
import io
import requests
import re # <-- FIX: Added the missing import statement

# Assuming url_utils.py exists for this function
from url_utils import extract_pdf_links_from_url

def college_specific_tab(master_extractors_list):
    """
    Streamlit UI for a page that runs all extractions on a single PDF
    and provides a consolidated Excel download.
    """
    st.title("📄 NIRF College Specific Data Extraction")
    st.info(
        "Upload a single NIRF PDF or provide a direct URL to a PDF to generate a complete report. "
        "All available data tables will be extracted and displayed below."
    )

    # --- PDF Input Methods ---
    st.subheader("Option 1: Extract from PDF URL")
    url_input = st.text_input(
        "Enter the direct URL to a single NIRF PDF file:",
        key="college_specific_url_input"
    )

    st.subheader("Option 2: Extract from an Uploaded PDF")
    # Note: We only process the first uploaded file for this specific page.
    uploaded_file = st.file_uploader(
        "Or upload a single NIRF PDF file here:",
        type="pdf",
        accept_multiple_files=False, # Set to False for single file processing
        key="college_specific_file_uploader"
    )

    # --- Processing Logic ---
    pdf_file_to_process = None
    if uploaded_file:
        pdf_file_to_process = uploaded_file
    elif url_input:
        if url_input.lower().endswith('.pdf'):
            try:
                with st.spinner(f"Downloading PDF from {url_input}..."):
                    response = requests.get(url_input, timeout=15)
                    response.raise_for_status()
                    # Create an in-memory file-like object
                    pdf_file_to_process = io.BytesIO(response.content)
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to download PDF: {e}")
        else:
            st.warning("Please provide a direct URL ending in .pdf")

    if pdf_file_to_process:
        # --- Run all extractions ---
        all_results = {}
        college_name = "Unknown College"
        college_code = "Unknown Code"
        
        # Get college info first from the program_data extractor
        program_data_func = next((func for name, func in master_extractors_list if name == "Program-wise Data"), None)
        if program_data_func:
            pdf_file_to_process.seek(0)
            temp_df = program_data_func(pdf_file_to_process)
            if not temp_df.empty:
                college_name = temp_df['CollegeName'].iloc[0]
                college_code = temp_df['CollegeCode'].iloc[0]

        st.header(f"📊 Extracted Data for: {college_name}")
        st.subheader(f"College Code: {college_code}")

        with st.spinner("Running all data extractors..."):
            for name, func in master_extractors_list:
                try:
                    pdf_file_to_process.seek(0)
                    df = func(pdf_file_to_process)
                    if not df.empty:
                        all_results[name] = df
                except Exception as e:
                    st.error(f"Error running '{name}' extractor: {e}")

        # --- Display all results ---
        for name, df in all_results.items():
            st.subheader(f"📋 {name}")
            st.dataframe(df, use_container_width=True)

        # --- Consolidated Excel Download Button ---
        if all_results:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for sheet_name, df in all_results.items():
                    # Sanitize sheet name for Excel (max 31 chars, no invalid chars)
                    safe_sheet_name = re.sub(r'[\\/*?:"<>|]', "", sheet_name)[:31]
                    df.to_excel(writer, index=False, sheet_name=safe_sheet_name)
            
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download Complete Report as Excel",
                data=processed_data,
                file_name=f"complete_report_{college_code}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_full_report"
            )
