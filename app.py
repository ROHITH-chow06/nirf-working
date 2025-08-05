import streamlit as st
import pandas as pd
import io
import re
from collections import namedtuple

# --- Import your page/tab functions ---
# Make sure you have these files in the same directory
from homepage import homepage
from college_specific_tab import college_specific_tab # New import
from expenditure_tab import expenditure_tab, extract_expenditure_data
from student_ratio_tab import student_ratio_tab, extract_student_ratio_data
from student_location_tab import student_location_tab, extract_student_location_data
from student_support_tab import student_support_tab, extract_student_support_data
from project_funding_tab import project_funding_tab, extract_project_funding_data
from university_exam_tab import university_exam_tab, extract_university_exam_data
from median_salary_tab import median_salary_tab, extract_median_salary_data
from phd_data_tab import phd_data_tab, extract_phd_graduated_data
from placement_data_tab import placement_data_tab, extract_placement_data

# It's a best practice to have st.set_page_config as the first Streamlit command.
st.set_page_config(page_title="NIRF PDF Extractor", layout="wide", initial_sidebar_state="expanded")


# --- Logic for Program-wise Data (from your original app.py) ---
ProgramLine = namedtuple('ProgramLine', [
    'SNo', 'CollegeName', 'CollegeCode', 'ProgramName', 'SanctionedIntake', 'TotalStudents'
])

def extract_college_info(text):
    college_name_match = re.search(r"Institute Name:\s*(.*?)\s*\[", text)
    college_code_match = re.search(r"\[(IR-[^\]]+)\]", text)
    college_name = college_name_match.group(1).strip() if college_name_match else "Not Found"
    college_code = college_code_match.group(1).strip() if college_code_match else "Not Found"
    return college_name, college_code

def extract_program_data(pdf_file):
    import pdfplumber
    sanctioned_intake = {}
    total_students = {}
    try:
        with pdfplumber.open(pdf_file) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            if not first_page_text: first_page_text = ""
            college_name, college_code = extract_college_info(first_page_text)
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables: continue
                for table in tables:
                    if not table or not table[0]: continue
                    header = [str(cell).replace('\n', ' ') if cell else '' for cell in table[0]]
                    if "Academic Year" in header[0] and "2022-23" in header:
                        try:
                            year_col_idx = header.index("2022-23")
                            for row in table[1:]:
                                program_name = str(row[0]).replace('\n', ' ').strip()
                                if program_name and (program_name.startswith("UG [") or program_name.startswith("PG [")):
                                    try:
                                        intake_val = row[year_col_idx].strip()
                                        if intake_val and intake_val not in ['-', '']:
                                            sanctioned_intake[program_name] = int(intake_val.replace(',', ''))
                                    except (ValueError, IndexError): continue
                        except (ValueError): continue
                    if "Total Students" in header and "No. of Male Students" in header:
                        try:
                            program_col_idx = 0
                            total_students_col_idx = header.index("Total Students")
                            for row in table[1:]:
                                program_name = str(row[program_col_idx]).replace('\n', ' ').strip()
                                if program_name and (program_name.startswith("UG [") or program_name.startswith("PG [")):
                                    try:
                                        total_val = row[total_students_col_idx].strip()
                                        if total_val: total_students[program_name] = int(total_val.replace(',', ''))
                                    except (ValueError, IndexError): continue
                        except (ValueError): continue
            lines = []
            all_programs = sorted(list(set(sanctioned_intake.keys()) | set(total_students.keys())))
            s_no = 1
            for prog in all_programs:
                intake = sanctioned_intake.get(prog, 0)
                students = total_students.get(prog, 0)
                if intake > 0 or students > 0:
                    lines.append(ProgramLine(s_no, college_name, college_code, prog, intake, students))
                    s_no += 1
            return pd.DataFrame(lines)
    except Exception as e:
        st.error(f"An error occurred while processing program data: {e}")
        return pd.DataFrame()

def program_wise_data_tab():
    st.title("📊 Program-wise Sanctioned vs. Admitted Extractor")
    uploaded_files = st.file_uploader("Upload NIRF PDFs", type=["pdf"], accept_multiple_files=True, key="program_data_uploader")
    if uploaded_files:
        all_dfs = []
        with st.spinner("Extracting program data..."):
            for pdf in uploaded_files:
                pdf.seek(0)
                df = extract_program_data(pdf)
                if not df.empty: all_dfs.append(df)
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            st.dataframe(combined_df, use_container_width=True)
        else:
            st.warning("Could not extract program-wise data from the uploaded files.")

# --- Main App Navigation ---

st.sidebar.title("📚 NIRF PDF Tools")
st.sidebar.markdown("Select a tool from the options below.")

# The master list of all extractor functions for the homepage
MASTER_EXTRACTORS_LIST = [
    ("Program-wise Data", extract_program_data),
    ("Placement & Higher Studies", extract_placement_data),
    ("University Exam Data", extract_university_exam_data),
    ("Median Salary Data", extract_median_salary_data),
    ("Ph.D. Graduated Data", extract_phd_graduated_data),
    ("Student Gender Ratio", extract_student_ratio_data),
    ("Student Location", extract_student_location_data),
    ("Student Financial Support", extract_student_support_data),
    ("Project Funding", extract_project_funding_data),
    ("Expenditure Data", extract_expenditure_data)
]

tool_selection = st.sidebar.radio(
    "Go to",
    ("Home", "College Specific Data", "Program-wise Data", "Placement & Higher Studies", "University Exam Data", "Median Salary Data", "Ph.D. Data", "Student Gender Ratio", "Student Location", "Student Financial Support", "Project Funding", "Expenditure Data")
)

# Based on the selection, call the appropriate function.
if tool_selection == "Home":
    homepage(MASTER_EXTRACTORS_LIST)
elif tool_selection == "College Specific Data":
    college_specific_tab(MASTER_EXTRACTORS_LIST)
elif tool_selection == "Program-wise Data":
    program_wise_data_tab()
elif tool_selection == "Placement & Higher Studies":
    placement_data_tab()
elif tool_selection == "University Exam Data":
    university_exam_tab()
elif tool_selection == "Median Salary Data":
    median_salary_tab()
elif tool_selection == "Ph.D. Data":
    phd_data_tab()
elif tool_selection == "Student Gender Ratio":
    student_ratio_tab()
elif tool_selection == "Student Location":
    student_location_tab()
elif tool_selection == "Student Financial Support":
    student_support_tab()
elif tool_selection == "Project Funding":
    project_funding_tab()
elif tool_selection == "Expenditure Data":
    expenditure_tab()
