#!/usr/bin/python3.6
# The above python path is set to work on the CBU cluster without the need to load a specific python module.

# ============================================================
# Requires Python 3.6 or higher! (because of f-strings)
#
# This script is used to convert multiple subjects from DICOM to BIDS.
# The script calls the 'heudiconv_script.sh' bash script for each subject in the SUBJECT_LIST.
#
# Usage:
#   Configure the variables below and run the script: ./dicom_to_bids_multiple_subjects.py
#
# ============================================================

# ------------------------------------------------------------
# Import packages
# ------------------------------------------------------------
import os # To check if files and folders exist
import sys # To exit the script in case of error
import subprocess # To run shell commands

# Check if it's Python 3.6 or higher
if sys.version_info < (3, 6):
    sys.stderr.write("You need Python 3.6 or higher to run this script\n")
    sys.exit(1)
    
# ------------------------------------------------------------
#
# !FILL IN THE VARIABLES BELOW!
#
# ------------------------------------------------------------

# Your project's root directory
PROJECT_PATH = '/imaging/correia/da05/wiki/BIDS_conversion/MRI'

# Location of the heudiconv_script bash script
HEUDICONV_SCRIPT = f"{PROJECT_PATH}/code/heudiconv_script.sh"

# Location of the heudiconv heuristic file
HEURISTIC_FILE = f"{PROJECT_PATH}/code/bids_heuristic.py"

# Location of the output data (Heudiconv will create the folder if it doesn't exist)
OUTPUT_PATH = f"{PROJECT_PATH}/data/bids/"

# Root location of dicom files
DICOM_ROOT = '/mridata/cbu'

# Your MRI project code, to locate your data
PROJECT_CODE = 'MR09029'

# List of subject IDs and their corresponding CBU codes as they appear in the DICOM_ROOT folder
SUBJECT_LIST= {
    '02': 'CBU090938', # sub-id how to appear in BIDS and CBU code as in raw dicom folder
    '03': 'CBU090964',
    '04': 'CBU090928'
}
# ------------------------------------------------------------

# ------------------------------------------------------------
# You don't have to change anything below this line!
#
# It is assumed that your raw data are located in /mridata/cbu/{cbu_code}_{PROJECT_CODE}
# If you want to change this, edit the dicom_path variable below and possibly the SUBJECT_LIST above
# ------------------------------------------------------------

# ------------------------------------------------------------
# Set up other variables needed for the script
# ------------------------------------------------------------

# Get the subject IDs and CBU codes from the SUBJECT_LIST
subject_ids = list(SUBJECT_LIST.keys())
cbu_codes = list(SUBJECT_LIST.values())

# Get the paths to the raw data for each subject
dicom_paths = [f"{DICOM_ROOT}/{code}_{PROJECT_CODE}" for code in cbu_codes]

# Convert subject and dicom lists to space-separated strings as needed for the bash script
SUBJECT_ID_LIST = ' '.join(subject_ids)
DICOM_PATH_LIST = ' '.join(dicom_paths)

# Get the number of subjects to know how many jobs to submit
n_subjects = len(SUBJECT_LIST)  

# Specify and create a folder for the job logs
JOB_OUTPUT_PATH = f"{PROJECT_PATH}/work/heudiconv_job_logs"
if not os.path.isdir(JOB_OUTPUT_PATH):
    os.makedirs(JOB_OUTPUT_PATH)
 
# ------------------------------------------------------------
# Do some checks before running the script
# ------------------------------------------------------------

# Check if the heuristic file exists. If not, exit the script.
if not os.path.isfile(HEURISTIC_FILE):
    sys.stderr.write(f"Heuristic file not found: {HEURISTIC_FILE}. Exiting...\n")
    sys.exit(1)

# Check if all dicom paths exist. If not, print out which doesn't and exit the script.
for dicom_path in dicom_paths:
    if not os.path.isdir(dicom_path):
        sys.stderr.write(f"Dicom path not found: {dicom_path}. Exiting...\n")
        sys.exit(1)

# Check if the heudiconv_script exists. If not, exit the script.
if not os.path.isfile(HEUDICONV_SCRIPT):
    sys.stderr.write(f"Heudiconv script not found: {HEUDICONV_SCRIPT}. Exiting...\n")
    sys.exit(1)

# ------------------------------------------------------------
# Construct a command to submit a job array to SLURM
# It will call the heudiconv_script.sh script for each subject and generate a unique task ID.
# The heudiconv_script will use the task ID to get the subject ID and the path to the raw data from the passed subject and dicom lists.
# ------------------------------------------------------------
    
bash_command = (
    f"sbatch "
    f"--array=0-{n_subjects - 1} "
    f"--job-name=heudiconv "
    f"--output={JOB_OUTPUT_PATH}/heudiconv_job_%A_%a.out "
    f"--error={JOB_OUTPUT_PATH}/heudiconv_job_%A_%a.err "
    f"{HEUDICONV_SCRIPT} '{SUBJECT_ID_LIST}' '{DICOM_PATH_LIST}' '{HEURISTIC_FILE}' '{OUTPUT_PATH}'"
)
subprocess.run(bash_command, shell=True, check=True)

# ------------------------------------------------------------
# End of script
# ------------------------------------------------------------