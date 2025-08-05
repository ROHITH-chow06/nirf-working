import streamlit as st
import pandas as pd
import io
import requests

# This utility needs to be in a file named url_utils.py
from url_utils import extract_pdf_links_from_url

def run_all_extractions(pdf_files, extractors_list):
    """
    Runs all registered extraction functions on a list of PDF files and displays the results.
    """
    if not pdf_files:
        st.warning("No PDF files to process.")
        return

    st.info(f"Found {len(pdf_files)} PDF(s) to process. Starting all extractions...")

    # A dictionary to hold all extracted dataframes
    all_results = {name: [] for name, _ in extractors_list}

    # Progress bar for better user feedback
    progress_bar = st.progress(0, text="Starting...")
    total_steps = len(pdf_files) * len(extractors_list)
    current_step = 0

    for i, pdf_file in enumerate(pdf_files):
        for name, func in extractors_list:
            progress_text = f"Processing PDF {i+1}/{len(pdf_files)} - Running '{name}'..."
            progress_bar.progress(current_step / total_steps, text=progress_text)
            try:
                # Reset file buffer for each function
                pdf_file.seek(0)
                df = func(pdf_file)
                if not df.empty:
                    all_results[name].append(df)
            except Exception as e:
                st.error(f"Error running '{name}' on PDF {i+1}: {e}")
            
            current_step += 1

    progress_bar.empty()

    # --- Display all results in expandable sections ---
    st.success("Extraction complete! See results below.")
    
    for name, dfs in all_results.items():
        if dfs:
            with st.expander(f"📊 Results: {name}", expanded=True):
                final_df = pd.concat(dfs, ignore_index=True)
                st.dataframe(final_df, use_container_width=True)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df.to_excel(writer, index=False, sheet_name=name)
                processed_data = output.getvalue()

                st.download_button(
                    label=f"📥 Download {name} as Excel",
                    data=processed_data,
                    file_name=f"nirf_{name.replace(' ', '_').lower()}_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{name.replace(' ', '_')}"
                )
        else:
            st.warning(f"No data could be extracted for '{name}'.")


def homepage(master_extractors_list):
    """
    The main UI for the Home page of the application.
    Accepts a master list of all extractor functions.
    """
    st.title("🚀 NIRF Data Extractor Dashboard")
    st.markdown(
        "Welcome! Use this page to extract all available data from NIRF PDFs. "
        "You can either provide a URL to a NIRF webpage containing PDF links, or upload PDF files directly."
    )

    with st.form(key="extraction_form"):
        st.subheader("Option 1: Extract from Webpage URL")
        url_input = st.text_input(
            "Enter the URL of a NIRF webpage:",
            key="url_input"
        )

        st.subheader("Option 2: Extract from Uploaded PDFs")
        uploaded_files = st.file_uploader(
            "Or upload one or more NIRF PDF files here:",
            type="pdf",
            accept_multiple_files=True,
            key="home_file_uploader"
        )
        
        submit_button = st.form_submit_button(label="✨ Run Full Extraction", type="primary")

    if submit_button:
        pdf_files_to_process = []
        
        if url_input:
            with st.spinner("Scraping URL for PDF links..."):
                pdf_links = extract_pdf_links_from_url(url_input)
                if pdf_links:
                    st.success(f"Found {len(pdf_links)} PDF links.")
                    for link in pdf_links:
                        try:
                            response = requests.get(link, timeout=15)
                            response.raise_for_status()
                            pdf_files_to_process.append(io.BytesIO(response.content))
                        except requests.exceptions.RequestException as e:
                            st.error(f"Failed to download PDF from {link}: {e}")
                elif url_input and not pdf_links:
                    st.warning("No PDF links were found at the provided URL.")
        
        if uploaded_files:
            pdf_files_to_process.extend(uploaded_files)
        
        if not pdf_files_to_process:
            st.error("Please provide a URL with valid PDF links or upload PDF files to run the extraction.")
        else:
            run_all_extractions(pdf_files_to_process, master_extractors_list)
