#!/bin/bash

# ============================================================
#
# Converting CBU DICOM files into BIDS format using Heudiconv
#
# Usage: 
#   1) Configure the variables below 
#   2) Run the script with SLURM: sbatch dicom_to_bids_multiple_subjects.sh
#
# ============================================================

# ------------------------------------------------------------
# SLURM job configuration
#
# !Edit the SBATCH variables as needed!
# !The job output and error directories must exist before running the script!
# ------------------------------------------------------------

#SBATCH --job-name=heudiconv_%a
#SBATCH --output=/imaging/correia/da05/wiki/BIDS_conversion/MRI/work/heudiconv_job_logs/heudiconv_job_%A_%a.out
#SBATCH --error=/imaging/correia/da05/wiki/BIDS_conversion/MRI/work/heudiconv_job_logs/heudiconv_job_%A_%a.err
#SBATCH --array=1-3 # Adjust the array range to match which subjects you want to process

# ------------------------------------------------------------
# SLURM will handle the parallelization across the specified array range.
# SLURM will create separate tasks for each array index.
# The SLURM_ARRAY_TASK_ID will be used later in the script to select a subject from subjects list.

# ------------------------------------------------------------
#
# !FILL IN THE VARIABLES BELOW!
#
# ------------------------------------------------------------

# Your project's root directory
PROJECT_PATH='/imaging/correia/da05/wiki/BIDS_conversion/MRI'

# Location of the output data
OUTPUT_PATH="${PROJECT_PATH}/data/"

# Location of the heudiconv heuristic file
HEURISTIC_FILE="${PROJECT_PATH}/code/bids_heuristic.py"

# Root location of dicom files
DICOM_ROOT='/mridata/cbu'

# Your MRI project code, to locate your data
PROJECT_CODE='MR09029'

# List of subject IDs and their corresponding CBU codes as they appear in the DICOM_ROOT folder
declare -A SUBJECT_LIST
SUBJECT_LIST["02"]="CBU090938" # sub-id how to appear in BIDS and CBU code as in raw dicom folder
SUBJECT_LIST["03"]="CBU090964"
SUBJECT_LIST["04"]="CBU090928"

# ------------------------------------------------------------


# ------------------------------------------------------------
# You don't have to change anything below this line!
#
# It is assumed that your raw data is located in DICOM_ROOT/{cbu_code}_{PROJECT_CODE}
# If you want to change this, edit the DICOM_PATH variable below and possibly the SUBJECT_LIST above
# ------------------------------------------------------------

# ------------------------------------------------------------
# Get the current subject data
# ------------------------------------------------------------

# A list of all the subject IDs
subject_ids=( "${!SUBJECT_LIST[@]}" )

# Get the subject's ID for the current job
subject_id=${subject_ids[$((SLURM_ARRAY_TASK_ID - 1))]}  # Subtract 1 because bash arrays are 0-indexed

# Get the subject's CBU code 
cbu_code=${SUBJECT_LIST[$subject_id]}

# Get the path to the raw data for the current job
DICOM_PATH="${DICOM_ROOT}/${cbu_code}_${PROJECT_CODE}"

# ------------------------------------------------------------
# Start the processing of the current subject
# ------------------------------------------------------------

# Add some information to the job output
echo "Processing subject ${subject_id} (${cbu_code})..."

# Check if the heuristic file exists. If not, add to the error output log (that's what >&2 does) and exit the script.
if [ ! -f "$HEURISTIC_FILE" ]; then
    echo "Heuristic file not found: ${HEURISTIC_FILE}. Exiting..." >&2
    exit 1
fi

# Check if the raw data path exists. If not, exit the script.
if [ ! -d "$DICOM_PATH" ]; then
    echo "Raw path: ${DICOM_PATH}" >&2
    echo "Raw data path for ${cbu_code} not found. Exiting..." >&2
    exit 1
fi

# Activate the heudiconv environment and run heudiconv
conda activate heudiconv # This assumes you have a conda environment called heudiconv available (check with 'conda env list'). If not, create one with the heudiconv and dcm2niix packages installed.

heudiconv \
    --files "${DICOM_PATH}"/*/*/*.dcm \
    --outdir "$OUTPUT_PATH" \
    --heuristic "${HEURISTIC_FILE}" \
    --subjects "${subject_id}" \
    --converter dcm2niix \
    --bids \
    --overwrite

# deactivate the heudiconv environment
conda deactivate

# ------------------------------------------------------------
# End of processing for the current subject
# ------------------------------------------------------------
echo "Finished processing subject ${subject_id} (${cbu_code})."

# ============================================================
# HeudiConv parameters:
# --files: Files or directories containing files to process
# --outdir: Output directory
# --heuristic: Name of a known heuristic or path to the Python script containing heuristic
# --subjects: Subject ID
# --converter : dicom to nii converter (dcm2niix or none)
# --bids: Flag for output into BIDS structure
# --overwrite: Flag to overwrite existing files
# 
# For a full list of parameters, see: https://heudiconv.readthedocs.io/en/latest/usage.html 
#
# ============================================================