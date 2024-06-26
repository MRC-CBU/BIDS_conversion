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
    # Checking required variables
    # ---------------------------
    required_vars = [
        'project_root', 'data_root', 'bids_raw_root', 'sourcedata_root', 
        'event_info_path', 'subject_info_path', 'meg_system', 'event_channels', 
        'adjust_event_times', 'audio_latency_sec', 'visual_latency_sec', 
        'cal_file_path_triux', 'ct_file_path_triux', 'cal_file_path_vectorview', 
        'ct_file_path_vectorview'
    ]
    for var in required_vars:
        assert hasattr(cfg, var), f"{var} is missing from the config.py file"
    # Auditory and visual event names and values are required only if 
    # adjust_event_times is True
    if cfg.adjust_event_times:
        required_vars_adjust_event_times = [
            'auditory_event_names',
            'visual_event_names',
            'auditory_event_values',
            'visual_event_values']
        for var in required_vars_adjust_event_times:
            if cfg.adjust_event_times:
                assert hasattr(cfg, var), f"{var} is missing from the config.py file"
    # Checking specific config variables
    # ----------------------------------
    # Check if project folder exists
    assert op.exists(cfg.project_root), (
        "Project folder not found. Please check the project_root variable in config.py"
    )
    # Check the MEG system
    assert cfg.meg_system in ['triux', 'vectorview'], (
        "meg_system must be either 'triux' or 'vectorview'"
    )
    assert isinstance(cfg.adjust_event_times, bool), "adjust_event_times must be a boolean"

    return


def _check_subject_info(subject_info):
    required_keys = ['bids_id', 'meg_id', 'meg_raw_dir', 'meg_emptyroom_dir',
                     'meg_raw_files', 'meg_bad_channels', 'mri_id', 'mri_date', 
                     'mri_dcm_dir']
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
        if info['mri_dcm_dir'] is not None:
            assert op.exists(info['mri_dcm_dir']), (
                f"Subject {sub_id} MRI dicom directory not found"
            )

    print('Subject info file is OK.')
    return


def _check_event_channels(event_channels, raw):
    """Check the event_channels variable in the config.py file.
    """
    if isinstance(event_channels, dict):
        assert len(event_channels) == 2 and all([key in event_channels.keys() for key in ['stim', 'resp']]), (
            "event_channels dictionary must contain precisely a 'stim' and 'resp' key only."
        )
        assert all([isinstance(event_channels[key], list) for key in event_channels.keys()]), (
            "Values in the event_channels dictionary must be lists of stirngs."
        )
        if any([ch not in raw.ch_names for ch in event_channels['stim']]): 
            print("One or more specified stimulus channels not found in the raw data.\n", 
                "Changing the event_channels variable to use STI101 channel only.")
            assert 'STI101' in raw.ch_names, (
                "STI101 channel not found in the raw data. Please provide a valid stimulus channel."
            )
            return ['STI101']
        
        if any([ch not in raw.ch_names for ch in event_channels['resp']]): 
            print("One or more specified resp channels not found in the raw data.\n", 
                "Changing the event_channels variable to use STI101 channel only.")
            assert 'STI101' in raw.ch_names, (
                "STI101 channel not found in the raw data. Please provide a valid stimulus channel."
            )
            return ['STI101']

        assert all(['STI101' not in event_channels[key] for key in event_channels.keys()]), (
            "STI101 combines all STI channels so it should only be used by itself in a list."
        )
        # Check if no channel is repeated in the stim and resp lists
        assert len(set(event_channels['stim']).intersection(event_channels['resp'])) == 0, (
            "The same channel cannot be used in both the stim and resp lists."
        )
    elif isinstance(event_channels, list):
        if any([ch not in raw.ch_names for ch in event_channels]):
            print("One or more specified channels not found in the raw data.\n", 
                "Changing the event_channels variable to use STI101 channel only.")
            assert 'STI101' in raw.ch_names, (
                "STI101 channel not found in the raw data. Please provide a valid stimulus channel."
            )
            return ['STI101']

        if 'STI101' in event_channels:
            assert len(event_channels) == 1, (
                ("If you are using STI101 as the event channel, "
                 "it should be the only channel in the event_channels list."
                )
            )
    else: 
        raise ValueError(
            ("event_channels must be a list of strings or a dictionary "
             "of the form {'stim': stim_channel_list, 'resp': resp_channel_list}"
            )
        )
    return event_channels


def _sti_to_decimal(sti_data, event_channels):
    """Convert binary STI data to decimal values.
    Combine binary STI channels to get decimal trigger values 
    Values in STI channels should be 0 or 5
    For each channel, substitute the nonzero values to the values encoded by that channel
    see https://imaging.mrc-cbu.cam.ac.uk/meg/IdentifyingEventsWithTriggers
    """
    # Create a look-up table for the STI channels as each channel has a specific decimal value
    sti_channels = [f'STI{i:03d}' for i in range(1, 17)]
    sti_decimal_lut = {ch: 2**i for i, ch in enumerate(sti_channels)}
    # Convert the binary data to decimal values
    for i, ch in enumerate(event_channels):
        sti_data[i, np.where(sti_data[i, :] > 0)] = sti_decimal_lut[ch]
    
    return sti_data


def _get_events_from_sti_channels(
    raw, 
    event_channels = ['STI001', 'STI002', 'STI003', 'STI004', 
                     'STI005', 'STI006', 'STI007', 'STI008']
):
    """Get events from STI001-STI008 channels.
        Inputs:
            raw: mne.io.Raw object
                The raw MEG data
            event_channels: list of str or dict of form {'stim': stim_channel_list, 'resp': resp_channel_list}
                The names of the binary STI channels. 
                If a list is provided, the channel values are converted to decimal values and summed.
                If a dictionary is provided, the values in the 'stim' channels are converted to decimal amd summed 
                    and the values in the 'resp' channels are converted to decimal but not summed.
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

    # perform checks
    event_channels = _check_event_channels(event_channels, raw)
    
    # Sort the stim channels and make sure that they start with STI001 and end with STI008
    if isinstance(event_channels, dict):
        event_channels['stim'] = sorted(event_channels['stim'])
        event_channels['resp'] = sorted(event_channels['resp'])
    else:
        event_channels = sorted(event_channels)
    # Read the events from the STI channels
    if isinstance(event_channels, list):
        if 'STI101' in event_channels:
            # Use the STI101 channel to get the events
            events = mne.find_events(raw, stim_channel='STI101', min_duration=0.002)
        else: 
            # Alternatively use only the specified stimulus channels. In this case these
            # binary channels will be summed and converted to decimal values from wich the 
            # events will be read.
            # Get the data from the stim channels, make sure channels are sorted
            stim_data = raw.get_data(picks=event_channels)
            stim_data = _sti_to_decimal(stim_data, event_channels)
            sti101_new = np.sum(stim_data, axis=0, keepdims=True)
            # Create dummy info and raw object to use find_events
            info = mne.create_info(['STI101New'], raw.info['sfreq'], ['stim'])
            raw_temp = mne.io.RawArray(sti101_new, info, first_samp=raw.first_samp)
            events = mne.find_events(raw_temp, stim_channel='STI101New', min_duration=0.002)
    else:
        # Use the specified stim and resp channels to get the events
        stim_data = raw.get_data(picks=event_channels['stim'])
        resp_data = raw.get_data(picks=event_channels['resp'])
        # Convert stim data to decimal values and sum them
        stim_data = _sti_to_decimal(stim_data, event_channels['stim'])
        sti101_new = np.sum(stim_data, axis=0, keepdims=True)
        # Convert resp data to decimal values but do not sum them
        resp_data = _sti_to_decimal(resp_data, event_channels['resp'])
        # Combine the decimal stim and resp data to get the events
        event_data = np.concatenate([sti101_new, resp_data], axis=0)
        # Create dummy info and raw object to use find_events
        ch_names = ['STI101New'] + event_channels['resp']
        info = mne.create_info(ch_names, raw.info['sfreq'], 'stim')
        raw_temp = mne.io.RawArray(event_data, info, first_samp=raw.first_samp)
        events = mne.find_events(raw_temp, stim_channel=ch_names, min_duration=0.002)
    
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
        events = _get_events_from_sti_channels(raw, cfg.event_channels)
        
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
    if subject_info['mri_dcm_dir'] is None: 
        print("No MRI dicom directory provided. Skipping structural MRI conversion.")
    else:
        print("Converting structural MRI data to BIDS format.")
        # First convert the original dicom mri file to temporary nifiti file using dcm2niix
        mri_path_dcm = subject_info['mri_dcm_dir']
        mri_file_name = f'sub-{subj_id_bids}_T1w.nii.gz'
        mri_filename_noext = mri_file_name.replace('.nii.gz', '') # remove extension as dcm2niix will add it
        command =  f'dcm2niix -o {sourcedata_dir} -f {mri_filename_noext} -m y -z y {mri_path_dcm}'
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
        
        print("Finished subject and moving on")

        # end of loop through subjects

    # Purge the temporary sourcedata folder after the conversion
    if (not keep_source_data) and op.exists(cfg.sourcedata_root):
        shutil.rmtree(cfg.sourcedata_root)

    print("Finished converting data from all subjects to BIDS format.")