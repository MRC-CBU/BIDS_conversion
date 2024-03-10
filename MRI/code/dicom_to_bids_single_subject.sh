#!/bin/bash

# ============================================================
#
# This script converts a single subject's DICOM files to BIDS
# 
# Usage: 
#    Configure the variables below and run the script: ./dicom_to_bids_single_subject.sh
#
# ============================================================

# ------------------------------------------------------------
# Define your variables
# ------------------------------------------------------------

# Path to the raw DICOM files
DICOM_PATH='/mridata/cbu/CBU090942_MR09029'

# Location of the output data
OUTPUT_PATH='/imaging/correia/da05/wiki/BIDS_conversion/MRI/data/'

# Location of the heudiconv heuristic file
HEURISTIC_FILE='/imaging/correia/da05/wiki/BIDS_conversion/MRI/code/bids_heuristic.py'

# Subject ID
SUBJECT_ID='01'

# ------------------------------------------------------------
# Activate the heudiconv environment
# ------------------------------------------------------------
# This assumes you have a conda environment called heudiconv available (check with 'conda env list'). 
# If not, create one with the heudiconv and dcm2niix packages installed.
conda activate heudiconv

# ------------------------------------------------------------
# Run the heudiconv
# ------------------------------------------------------------
heudiconv \
    --files "${DICOM_PATH}"/*/*/*.dcm \
    --outdir "${OUTPUT_PATH}" \
    --heuristic "${HEURISTIC_FILE}" \
    --subjects "${SUBJECT_ID}" \
    --converter dcm2niix \
    --bids \
    --overwrite
# ------------------------------------------------------------

# Deactivate the heudiconv environment
conda deactivate