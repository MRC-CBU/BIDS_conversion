# -*- coding: utf-8 -*-
"""
Description: MNE-BIDS data conversion script for SpeechMisperceptionMEEG data

Author: Mate Aller

"""
import json, mne, os, shutil
import os.path as op
import numpy as np
import subprocess as sp
from mne_bids import (BIDSPath, mark_channels, write_raw_bids, 
                      write_meg_calibration, write_meg_crosstalk, write_anat)
from argparse import ArgumentParser

import config as cfg


def _get_events_from_stim_channels(raw):
    """Get events from STI001-STI008 channels.
        Inputs:
            raw: mne.io.Raw object
        Outputs:
            events: numpy array of shape (n_events, 3)
        Description:
            This function is necessary because the STI101 channel contains responses in addition to the
            trigger values. The responses are cumulative and can mask the trigger values. Therefore,
            it is necessary to get the trigger values from the binary STI channels dedicated to 
            the stimulus triggers (STI001-STI008) and combine them to get the decimal trigger values.
    """
    binary_stim_channels = ['STI001', 'STI002', 'STI003', 'STI004', 'STI005', 'STI006', 'STI007', 'STI008']
    stim_data = raw.get_data(picks=binary_stim_channels)
    # Combine binary STI channels to get decimal trigger values 
    # Values in STI channels should be 0 or 5
    # For each channel, substitute the nonzero values to the values encoded by that channel
    # see https://imaging.mrc-cbu.cam.ac.uk/meg/IdentifyingEventsWithTriggers
    for i in range(len(binary_stim_channels)):
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
    meg_system='triux',
    fix_eeg_locations=True,
    adjust_event_times=True,
    process_structural=True
):
    """Convert MEG data to BIDS format.
        Inputs:
            subject_info: dict
                Dictionary containing information about the subjects in the experiment.
                See README.md for more information.
            event_info: dict
                Dictionary containing information about the events in the experiment.
                See README.md for more information.
            meg_system: str
                The MEG system used to record the data. Must be either 'triux' or 'vectorview'.
                Default is 'triux'.
            adjust_event_times: bool
                If True, the event times will be adjusted to account for the audio and visual latencies.
                Default is True.
            process_structural: bool
                If True, the structural MRI data will be processed and added to the BIDS dataset.
                Default is True.
        Description:
            This function converts the MEG data to BIDS format. It reads the raw MEG data
            and the structuraly MRI data, and writes the data to the BIDS dataset."""
    
    # Check that the meg_system is valid
    assert meg_system in ['triux', 'vectorview'], "meg_system must be either 'triux' or 'vectorview'"

    # Define the fine-calibration and cross-talk files required for Maxfilter
    cal_file_path = cfg.cal_file_path_triux if meg_system == 'triux' else cfg.cal_file_path_vectorview
    ct_file_path = cfg.ct_file_path_triux if meg_system == 'triux' else cfg.ct_file_path_vectorview
       
    # Unpacking the subject information
    subj_id_bids = subject_info['bids_id']
    meg_raw_dir = subject_info['meg_raw_dir']
    meg_emptyroom_dir = subject_info['meg_emptyroom_dir']
    meg_raw_files = subject_info['meg_raw_files']
    meg_bad_channels = subject_info['meg_bad_channels']
    mri_file = subject_info['mri_nii_file']
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
    er_file_info = meg_raw_files.pop(er_id[0])
    raw_er = mne.io.read_raw_fif(op.join(meg_emptyroom_dir, er_file_info['file']))
    # specify power line frequency as required by BIDS
    raw_er.info['line_freq'] = cfg.line_freq
    
    for meg_file_info in meg_raw_files:

        # First check and fix eeg locations if necessary
        if fix_eeg_locations: 
            # Copy file to temporary location so that EEG locations can be checked and fixed
            raw_path = op.join(sourcedata_dir, meg_file_info['file'])
            shutil.copyfile(op.join(meg_raw_dir, meg_file_info['file']), raw_path)
            
            # Check EEG Locations and fix as necessary
            # When EEG channels > 60 as at CBU, the EEG channel location obtained from Polhemus 
            # digitiser is not copied properly to Neuromag acquisition software. Therefore must 
            # apply mne_check_eeg_locations to data. Do this as early as possible in the processing
            #  pipeline. There is no harm in applying this function (e.g. if the eeg locations are correct). 
            # http://imaging.mrc-cbu.cam.ac.uk/meg/AnalyzingData/MNE_FixingFIFF. Function defined in config.
            command = cfg.check_eeg_cmd % raw_path
            sp.run(command.split(' '), check = True)
        else:
            raw_path = op.join(meg_raw_dir, meg_file_info['file'])
        
        # read raw file
        raw = mne.io.read_raw_fif(raw_path)
        print(f"file in is: {raw_path} \n")
        print(f"run_id is: {meg_file_info['run']} \n")

        # specify power line frequency as required by BIDS
        raw.info['line_freq'] = cfg.line_freq 

        # Get events from stim channels only (STI001 - STI008). This prevents the response channels
        # from being added to stimulus triggers and causing problems with the event values.
        events = _get_events_from_stim_channels(raw)
        
        # Get the event value counts
        unique, counts = np.unique(events[:, 2], return_counts=True)
        print('Trigger value counts are: \n')
        print(dict(zip(unique, counts)))

        if adjust_event_times:
            # Adjusting the event times to account for the audio and visual latencies
            # You may or may not need to do this depending on your experiment
            # Get the event ids for the written and spoken word events
            audio_event_keys = [key for key in event_info.keys() if key.startswith('spoken')]
            visual_event_keys = [key for key in event_info.keys() if key.startswith('written')]
            audio_event_infos = [event_info[key] for key in audio_event_keys]
            visual_event_infos = [event_info[key] for key in visual_event_keys]
            # Shift the spoken word events by the audio latency
            events[np.isin(events[:, 2], audio_event_infos), 0] = (
                events[np.isin(events[:, 2], audio_event_infos), 0] + 
                int(cfg.audio_latency_sec * raw.info['sfreq']))
            # Shift the visual word events by the visual latency
            events[np.isin(events[:, 2], visual_event_infos), 0] = (
                events[np.isin(events[:, 2], visual_event_infos), 0] + 
                int(cfg.visual_latency_sec * raw.info['sfreq']))

        bids_path_current_file = (bids_path.copy()
                                           .update(run=meg_file_info['run'], 
                                                   task=meg_file_info['task']))

        write_raw_bids(
            raw, 
            bids_path_current_file, 
            events=events, 
            event_id=event_info, 
            empty_room=raw_er,
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
    if process_structural: 
        # First convert the original dicom mri file to temporary nifiti file using dcm2niix
        mri_path_dcm = subject_info['mri_dcm_dir']
        temp = subject_info['mri_nii_file']
        mri_filename_nii = op.splitext(temp)[0] # remove extension as dcm2niix will add it
        command =  f'dcm2niix -o {sourcedata_dir} -f {mri_filename_nii} -m y {mri_path_dcm}'
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
            image=op.join(sourcedata_dir, mri_file),
            bids_path=t1w_bids_path,
            landmarks=None, # Note, in this case sidecar file will not be saved
            verbose=True)
            
        return


if __name__ == "__main__":
    # Parse command line arguments
    argparser = ArgumentParser(description='Convert MEG data to BIDS format')
    argparser.add_argument('--MEG_system',
                           default='triux', 
                           help='The MEG system used to record the data',
                           type=str, 
                           choices=['triux', 'vectorview'])
    argparser.add_argument('--purge_folders',
                           default=True, 
                           help='''Purge the output folders before running the conversion. 
                                   Recommended, but be careful not to delete important data!
                                ''',
                           type=bool)
    argparser.add_argument('--fix_eeg_locations',
                           default=True, 
                           help='Check and fix EEG locations in the raw data',
                           type=bool)  
    argparser.add_argument('--adjust_event_times',
                           default=True, 
                           help='Adjust the event times to account for the audio and visual latencies',
                           type=bool)
    argparser.add_argument('--process_structural',
                           default=True,
                           help='Process the structural MRI data and add to the BIDS dataset',
                           type=bool)
    
    args = argparser.parse_args()
    meg_system = args.MEG_system
    purge_folders = args.purge_folders
    fix_eeg_locations = args.fix_eeg_locations
    adjust_event_times = args.adjust_event_times
    process_structural = args.process_structural

    # Check if project folder exists
    assert op.exists(cfg.project_root), "Project folder not found. Please check the project_root variable in config.py"

    if purge_folders:
        # If output directory exist clear it to make sure doesn't contain leftover files 
        # from previous test and example runs. But be careful not to delete important data!
        if op.exists(cfg.bids_raw_root):
            shutil.rmtree(cfg.bids_raw_root)
        if op.exists(cfg.sourcedata_root):
            shutil.rmtree(cfg.sourcedata_root)

    # Load subject info
    with open(cfg.subject_info_path, 'r') as f:
        subject_info = json.load(f)

    # Load event info
    with open(cfg.event_info_path, 'r') as f:
        event_info = json.load(f)

    for ss in subject_info.keys():
        # Loop through the subjects
        print("subject is: {} \n".format(ss))      

        # Skip subject if no BIDS id is provided
        subject_info = subject_info[ss]
        if subject_info['bids_id'] is None:
            continue
        
        # Process the subject
        process_subject(subject_info, 
                        event_info, 
                        meg_system=meg_system,
                        fix_eeg_locations=fix_eeg_locations,
                        adjust_event_times=adjust_event_times,
                        process_structural=process_structural)
        
        print("finished subject and moving on")

        # end of loop through subjects

    # Purge the temporary sourcedata folder after the conversion
    if op.exists(cfg.sourcedata_root):
        shutil.rmtree(cfg.sourcedata_root)