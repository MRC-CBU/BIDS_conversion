import os.path as op

# ***********************************************************************
# Project specific information, please update these to fit your project *
# ***********************************************************************

# Project specific paths (you will need to update the project root at the 
# very least)
project_root = op.join('/path', 'to', 'your', 'project', 'root')
data_root = op.join(project_root, 'data')
bids_raw_root = op.join(data_root, 'rawdata')
sourcedata_root = op.join(data_root, 'sourcedata')

# Path to the event info json file. This file contains information about 
# the events in the experiment. See README.md for more information.
event_info_path = op.join(project_root, 'event_info.json')

# Path to the subject info json file. This file contains information about 
# the subjects in the experiment. See README.md for more information.
subject_info_path = op.join(project_root, 'subject_info.json')


# *********************************************************************
# MEG setup specific information, you should not need to change these *
# *********************************************************************

# Audio and viusal latencies as per CBU MEG system specifications at the 
# time of recording: https://imaging.mrc-cbu.cam.ac.uk/meg/StimulusDetails
audio_latency_sec = 0.028
visual_latency_sec = 0.034

# Define the path to the fine-calibration and cross-talk files required for
# Maxfilter. These files are specific to the MEG system used to record the
# data. The paths below are for the CBU MEG systems. If you are using a
# different MEG system, you will need to update these paths.
# The current (as of 2020) Triux neo system
cal_file_path_triux = op.join('/neuro_triux', 'databases', 'sss', 'sss_cal.dat')
ct_file_path_triux = op.join('/neuro_triux', 'databases', 'ctc', 'ct_sparse.fif')
# The old VectorView system
cal_file_path_vectorview = op.join('/neuro_vectorview', 'databases', 'sss', 'sss_cal.dat')
ct_file_path_vectorview = op.join('/neuro_vectorview', 'databases', 'ctc', 'ct_sparse.fif')

# When EEG channels > 60 as at CBU, the EEG channel location obtained from Polhemus 
# digitiser is not copied properly to Neuromag acquisition software. Therefore must 
# apply mne_check_eeg_locations to data. Do this as early as possible in the processing
#  pipeline. There is no harm in applying this function (e.g. if the eeg locations 
# are correct). http://imaging.mrc-cbu.cam.ac.uk/meg/AnalyzingData/MNE_FixingFIFF.
check_eeg_cmd = ('/imaging/local/software/mne/mne_2.7.3/x86_64/'
                 'MNE-2.7.3-3268-Linux-x86_64/bin/mne_check_eeg_locations'
                 ' --file %s --fix')

# Power line frequency
line_freq = 50  # Hz