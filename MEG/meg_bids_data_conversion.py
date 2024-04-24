# -*- coding: utf-8 -*-
"""
Description: MNE-BIDS data conversion script for MEG data collected at the CBU MEG lab.

Acknowledgements: This script is based on the MNE-BIDS tutorial available at
https://mne.tools/mne-bids/stable/auto_examples/convert_mne_sample.html

Author: Mate Aller
email:  mate.aller@mrc-cbu.cam.ac.uk

"""
import json, mne, os, shutil, importlib
import os.path as op
import numpy as np
import subprocess as sp
from mne_bids import (BIDSPath, mark_channels, write_raw_bids, 
                      write_meg_calibration, write_meg_crosstalk, write_anat)
from argparse import ArgumentParser


def _check_config():
    """Check the configuration file for required variables."""
    required_vars = [
        'project_root', 'data_root', 'bids_raw_root', 'sourcedata_root', 
        'event_info_path', 'subject_info_path', 'event_channels', 
        'auditory_event_names', 'visual_event_names', 'auditory_event_values', 
        'visual_event_values', 'audio_latency_sec', 'visual_latency_sec', 
        'cal_file_path_triux', 'ct_file_path_triux', 'cal_file_path_vectorview', 
        'ct_file_path_vectorview'
    ]
    for var in required_vars:
        assert hasattr(cfg, var), f"{var} is missing from the config.py file"
    
    # Checking specific config variables
    # ----------------------------------
    # Check if project folder exists
    assert op.exists(cfg.project_root), "Project folder not found. Please check the project_root variable in config.py"
    
    # Check the MEG system
    assert cfg.meg_system in ['triux', 'vectorview'], "meg_system must be either 'triux' or 'vectorview'"

    # Check that the event_channels variable
    assert isinstance(cfg.event_channels, list), "event_channels must be a list of strings. "
    
    assert cfg.event_channels, "event_channels cannot be an empty list"
    
    if 'STI101' in cfg.event_channels:
        assert len(cfg.event_channels) == 1, "If you are using STI101 as the event channel, it should be the only channel in the event_channels list."
    
    assert isinstance(cfg.adjust_event_times, bool), "adjust_event_times must be a boolean"

    assert isinstance(cfg.process_structural, bool), "process_structural must be a boolean"

    return


def _check_subject_info(subject_info):
    required_keys = ['bids_id', 'meg_id', 'meg_raw_dir', 'meg_emptyroom_dir',
                     'meg_raw_files', 'meg_bad_channels', 'mri_id', 'mri_date', 
                     'mri_nii_file', 'mri_dcm_dir']
    print('Checking subject info file...')
    for sub_id, info in subject_info.items():
        assert all(key in info for key in required_keys), (
            f"Subject {sub_id} is missing one or more of the required keys: {required_keys}"
        )
        for key in ['bids_id', 'meg_id', 'meg_date']:
            assert type(info[key]) == str and info[key], (
                f"Subject {sub_id} {key} must be specified as a non-empty string"
            )
        assert op.exists(info['meg_raw_dir']), (
            f"Subject {sub_id} MEG raw data directory not found"
        )
        if info['meg_emptyroom_dir'] is not None:
            assert op.exists(info['meg_emptyroom_dir']), (
                f"Subject {sub_id} MEG emptyroom data directory not found"
            )
        assert type(info['meg_raw_files']) == list and info['meg_raw_files'], (
            f"Subject {sub_id} meg_raw_files must be a non-empty list"
        )
        assert type(info['meg_bad_channels']) == list, (
            f"Subject {sub_id} meg_bad_channels must be a list"
        )
        if cfg.process_structural:
            assert info['mri_nii_file'].endswith('.nii.gz'), (
                f"Subject {sub_id} mri_nii_file must be in .nii.gz format"
            )
            assert info['mri_dcm_dir'], (
                f"Subject {sub_id} MRI dicom directory not specified"
            )
            assert op.exists(info['mri_dcm_dir']), (
                f"Subject {sub_id} MRI dicom directory not found"
            )

    print('Subject info file is OK.')
    return


def _get_events_from_stim_channels(
    raw, 
    stim_channels = ['STI001', 'STI002', 'STI003', 'STI004', 
                     'STI005', 'STI006', 'STI007', 'STI008']
):
    """Get events from STI001-STI008 channels.
        Inputs:
            raw: mne.io.Raw object
                The raw MEG data
            stim_channels: list of str
                The names of the binary STI channels. 
                Default is ['STI001', 'STI002', 'STI003', 'STI004',
                            'STI005', 'STI006', 'STI007', 'STI008']
        Outputs:
            events: numpy array of shape (n_events, 3)
        Description:
            This function is necessary because the STI101 channel contains responses in addition to the
            trigger values. The responses are cumulative and can mask the trigger values. Therefore,
            it is necessary to get the trigger values from the binary STI channels dedicated to 
            the stimulus triggers (STI001-STI008) and combine them to get the decimal trigger values.
    """
    stim_data = raw.get_data(picks=stim_channels)
    # Combine binary STI channels to get decimal trigger values 
    # Values in STI channels should be 0 or 5
    # For each channel, substitute the nonzero values to the values encoded by that channel
    # see https://imaging.mrc-cbu.cam.ac.uk/meg/IdentifyingEventsWithTriggers
    for i in range(len(stim_channels)):
        stim_data[i, np.where(stim_data[i, :] > 0)] = 2**i
    sti101_new = np.sum(stim_data, axis=0, keepdims=True)
    
    # Create dummy info and raw object to use find_events
    info = mne.create_info(['STI101New'], raw.info['sfreq'], ['stim'])
    raw_temp = mne.io.RawArray(sti101_new, info, first_samp=raw.first_samp)
    events = mne.find_events(raw_temp, stim_channel='STI101New', min_duration=0.002)
    
    return events


def process_subject(
    subject_info,
    event_info,
):
    """Convert MEG data to BIDS format.
        Inputs:
            subject_info: dict
                Dictionary containing information about the subjects in the experiment.
                See README.md for more information.
            event_info: dict
                Dictionary containing information about the events in the experiment.
                See README.md for more information.
        Description:
            This function converts the MEG data to BIDS format. It reads the raw MEG data
            and writes the data to the BIDS dataset.
            Optionally, it can also: 
            - check and fix EEG locations in the raw data
            - adjust the event times to account for the audio and visual latencies
            - process the structural MRI data and add to the BIDS dataset
            These options can be set in the config.py file.
    """

    # Define the fine-calibration and cross-talk files required for Maxfilter
    cal_file_path = cfg.cal_file_path_triux if cfg.meg_system == 'triux' else cfg.cal_file_path_vectorview
    ct_file_path = cfg.ct_file_path_triux if cfg.meg_system == 'triux' else cfg.ct_file_path_vectorview
       
    # Unpacking the subject information
    subj_id_bids = subject_info['bids_id']
    meg_raw_dir = subject_info['meg_raw_dir']
    meg_emptyroom_dir = subject_info['meg_emptyroom_dir']
    meg_raw_files = subject_info['meg_raw_files']
    meg_bad_channels = subject_info['meg_bad_channels']
    mri_file_name = subject_info['mri_nii_file']
    sourcedata_dir = op.join(cfg.sourcedata_root, f'sub-{subj_id_bids}')
    os.makedirs(sourcedata_dir, exist_ok=True)

    print(f"MEG id is: {subject_info['meg_id']}")

    # This tutorial explains which filename details are necessary 
    # (https://mne.tools/mne-bids/stable/auto_examples/bidspath.html) 
    bids_path = BIDSPath(
        subject=subj_id_bids,
        datatype='meg', 
        run=None, 
        extension = '.fif', 
        root=cfg.bids_raw_root)

    # add the fine-calibration file and cross talk files to each subject folder.
    # these are required when processing the elekta/neuromag/MEGIN data using MaxFilter
    write_meg_calibration(cal_file_path, bids_path)
    write_meg_crosstalk(ct_file_path, bids_path)

    # read emptyroom file first and remove from the raw file list
    er_id = [i for i, file in enumerate(meg_raw_files) if file['run'] == 'emptyroom']
    if not er_id:
        print(f"No emptyroom file found for sub-{subj_id_bids}. Proceeding without emptyroom file.")
        process_emptyroom = False
        raw_er = None
    elif len(er_id) > 1:
        raise ValueError(f"Multiple emptyroom files found for sub-{subj_id_bids}. Please check the subject_info.json file.")
    else:
        er_file_info = meg_raw_files.pop(er_id[0])
        raw_er = mne.io.read_raw_fif(op.join(meg_emptyroom_dir, er_file_info['file']))
        # specify power line frequency as required by BIDS
        raw_er.info['line_freq'] = cfg.line_freq
        process_emptyroom = True
    
    for meg_file_info in meg_raw_files:

        # First check and fix eeg locations if necessary
        if cfg.meg_system == 'triux':
            # With the Triux system, the EEG locations are correct and do not need to be fixed
            print("The MEG system is Triux. No need to fix EEG locations.")
            raw_path = op.join(meg_raw_dir, meg_file_info['file'])
            raw = mne.io.read_raw_fif(raw_path)
        else:
            # With the VectorView system, the EEG locations may need to be fixed
            print("The MEG system is VectorView.")
            # First check if the raw file has EEG channels
            raw_path = op.join(meg_raw_dir, meg_file_info['file'])
            raw = mne.io.read_raw_fif(raw_path)
            if 'eeg' in raw:
                # Copy file to temporary location so that EEG locations can be checked and fixed
                raw_path = op.join(sourcedata_dir, meg_file_info['file'])
                shutil.copyfile(op.join(meg_raw_dir, meg_file_info['file']), raw_path)
                # Check EEG Locations and fix as necessary
                # When EEG channels > 60 as at CBU, the EEG channel location obtained from Polhemus 
                # digitiser is not copied properly to Neuromag acquisition software. Therefore must 
                # apply mne_check_eeg_locations to data. Do this as early as possible in the processing
                #  pipeline. There is no harm in applying this function (e.g. if the eeg locations are correct). 
                # http://imaging.mrc-cbu.cam.ac.uk/meg/AnalyzingData/MNE_FixingFIFF. Function defined in config.
                print("Checking and fixing EEG locations.")
                command = cfg.check_eeg_cmd % raw_path
                sp.run(command.split(' '), check = True)
                # Reload the raw file as the file on disk may have been modified by cfg.check_eeg_cmd function
                raw = mne.io.read_raw_fif(raw_path)
            else: 
                print("No EEG channels found in the raw data. Skipping EEG location check.")
        print(f"file in is: {raw_path} \n")
        print(f"run_id is: {meg_file_info['run']} \n")

        # specify power line frequency as required by BIDS
        raw.info['line_freq'] = cfg.line_freq 

        # Get events from stim channels
        if 'STI101' in cfg.event_channels:
            # Use the STI101 channel to get the events
            events = mne.find_events(raw, stim_channel='STI101', min_duration=0.002)
        else: 
            # Alternatively use only the specified stimulus channels. In this case these
            # binary channels will be summed and converted to decimal values from wich the 
            # events will be read.
            events = _get_events_from_stim_channels(raw, cfg.event_channels)
        
        # Get the event value counts
        unique, counts = np.unique(events[:, 2], return_counts=True)
        print('Trigger value counts are: \n')
        print(dict(zip(unique, counts)))

        if cfg.adjust_event_times:
            # Adjusting the event times to account for the audio and visual latencies
            # You may or may not need to do this depending on your experiment. 
            # Define the visual and auditory event values as well as auditory and 
            # visual latencies in config.py
            print("Adjusting event times to account for the auditory and visual latencies.")
            
            # Shift the spoken word events by the audio latency
            if cfg.auditory_event_names:
                events[np.isin(events[:, 2], cfg.auditory_event_values), 0] = (
                    events[np.isin(events[:, 2], cfg.auditory_event_values), 0] + 
                    int(cfg.audio_latency_sec * raw.info['sfreq']))
            else: 
                print(("No auditory event values found in the event_info.json file. "
                       "Skipping auditory event time adjustment."))
            
            # Shift the visual word events by the visual latency
            if cfg.visual_event_names:
                events[np.isin(events[:, 2], cfg.visual_event_values), 0] = (
                    events[np.isin(events[:, 2], cfg.visual_event_values), 0] + 
                    int(cfg.visual_latency_sec * raw.info['sfreq']))
            else:
                print(("No visual event values found in the event_info.json file. "
                       "Skipping visual event time adjustment."))

        bids_path_current_file = (bids_path.copy()
                                           .update(run=meg_file_info['run'], 
                                                   task=meg_file_info['task']))

        write_raw_bids(
            raw, 
            bids_path_current_file, 
            events=events, 
            event_id=event_info, 
            empty_room=raw_er if process_emptyroom else None,
            overwrite=True, 
            allow_preload =True, 
            format = 'FIF')

        # Mark bad channels
        if meg_bad_channels:
            mark_channels(bids_path=bids_path_current_file, 
                          ch_names=meg_bad_channels, 
                          status='bad', 
                          verbose=False)
        # end of loop through raw files

    # Add structural MRI data to the BIDS dataset
    # ------------------------------------------
    if cfg.process_structural: 
        # First convert the original dicom mri file to temporary nifiti file using dcm2niix
        mri_path_dcm = subject_info['mri_dcm_dir']
        temp = subject_info['mri_nii_file']
        mri_filename_nii = temp.replace('.nii.gz', '') # remove extension as dcm2niix will add it
        command =  f'dcm2niix -o {sourcedata_dir} -f {mri_filename_nii} -m y -z y {mri_path_dcm}'
        # Run as a system command
        sp.run(command.split(' '), check = True)

        # Now write the nifti file to the BIDS dataset
        # Create the BIDSPath object for the T1w image
        t1w_bids_path = BIDSPath(
            subject=subj_id_bids,
            datatype='anat',
            root=cfg.bids_raw_root,
            suffix='T1w')
        # Use the write_anat function to write the T1w image to the BIDS dataset
        t1w_bids_path = write_anat(
            image=op.join(sourcedata_dir, mri_file_name),
            bids_path=t1w_bids_path,
            landmarks=None, # Note, in this case sidecar file will not be saved
            verbose=True)
            
    return


if __name__ == "__main__":
    # Parse command line arguments
    argparser = ArgumentParser(description='Convert MEG data to BIDS format')
    argparser.add_argument('--keep_existing_folders',
                           action='store_true', 
                           help='''Keep the existing output folders before running the conversion. 
                                   By default, they are purged, which is recommended to avoid
                                   conflicts, but be careful not to delete important data!
                                ''')
    argparser.add_argument('--keep_source_data',
                           action='store_true',
                           help='''Keep the temporary sourcedata folder after the conversion. 
                                   By default the sourcedata folder is purged after the conversion.
                                ''')
    argparser.add_argument('--config',
                           default='config',
                           help='''Absolute import path to the configuration file.
                                   Default is 'config'. 
                                   Should be in the form of 'module_name' or 'package.module_name'.
                                   For more details see: https://docs.python.org/3/library/importlib.html#importlib.import_module
                                ''')
    args = argparser.parse_args()
    keep_existing_folders = args.keep_existing_folders
    keep_source_data = args.keep_source_data
    config_import_path = args.config

    cfg = importlib.import_module(config_import_path)
    
    # Check the configuration file
    _check_config()

    if not keep_existing_folders:
        # If output directory exist clear it to make sure doesn't contain leftover files 
        # from previous test and example runs. But be careful not to delete important data!
        if op.exists(cfg.bids_raw_root):
            shutil.rmtree(cfg.bids_raw_root)
        if op.exists(cfg.sourcedata_root):
            shutil.rmtree(cfg.sourcedata_root)

    # Load subject info
    with open(cfg.subject_info_path, 'r') as f:
        subject_info = json.load(f)
    
    # Check the subject info
    _check_subject_info(subject_info)

    # Load event info
    with open(cfg.event_info_path, 'r') as f:
        event_info = json.load(f)

    for ss in subject_info.keys():
        # Loop through the subjects
        print("subject is: {} \n".format(ss))      

        # Skip subject if no BIDS id is provided
        subject_info_current = subject_info[ss]
        if subject_info_current['bids_id'] is None:
            continue
        
        # Process the subject
        process_subject(subject_info_current, 
                        event_info)
        
        print("finished subject and moving on")

        # end of loop through subjects

    # Purge the temporary sourcedata folder after the conversion
    if (not keep_source_data) and op.exists(cfg.sourcedata_root):
        shutil.rmtree(cfg.sourcedata_root)