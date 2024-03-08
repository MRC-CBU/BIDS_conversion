# Converting CBU MEG/EEG data to BIDS format
## Introduction
This document describes the steps to convert raw MEG/EEG data from the CBU MEG scanner to BIDS format. The BIDS format is a standard for organizing and describing neuroimaging and behavioural data. It is designed to make data sharing and analysis easier. The BIDS format is described in detail at [bids.neuroimaging.io](https://bids.neuroimaging.io/). The extension for MEG data is described at the [bids-specification](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/magnetoencephalography.html). 

The conversion process detailed below is done using the `mne-bids` Python package. The `mne-bids` package provides tools for converting raw MEG/EEG data to BIDS format. The `mne-bids` package is described in detail at [mne-bids](https://mne.tools/mne-bids/stable/index.html).

If you have any questions about this tutorial, please contact [Máté Aller](https://www.mrc-cbu.cam.ac.uk/people/mate.aller/). 

## Installation
- This tutorial assumes that you are running the conversion process on the CBU linux cluster.
- Simply download the scripts in this repository to your local folder.
- Dependencies: 
  - Python 3.7 or later
  - MNE-Python 1.15 or later
  - MNE-BIDS 0.12 or later
  - dcm2niix
- All the required packages are installed on the CBU cluster under the `mne1.6.1_0` conda environment in `/imaging/local/software/mne_python/`. You can activate this environment by typing the following command in a terminal:
  ```console
  conda activate /imaging/local/software/mne_python/mne1.6.1_0
  ```

## The main steps
After downloading the scripts in this repository, you will need to do the following to convert your raw MEG data to BIDS format:
1. Update the `config.py` file with the appropriate project specific path information. 
2. Update the `subject_info.json` file with the appropriate information for each subject. 
3. Update the `event_info.json` file with information on the event values (triggers) and their labels saved with your raw MEG data. 
4. run `meg_bids_data_conversion.py`

You can find detailed instructions on each of these steps below. 

## Where are your data stored?
### Raw MEG data
The raw data from the CBU MEG scanner are stored at `/megdata/cbu/[project_code]/[meg_id]/[yymmdd]/`, where `project_code` is the unique identifier of your MEG project, the `meg_id` is the participant's unique identifier and `yymmdd` is the date of the scan. You can see all your participant scan directories by typing a command like this in a terminal (replace `speech_misperception` with your project code): 
```console
ls -d /megdata/cbu/[project_code]/*/*
```

### Empty room recordings
As a standard practice, empty room recordings are saved along with the corresponding raw data in the BIDS repository. The best practice is to ask your operateor to save your own empty room recording at the beginning of each recording session, so that your empty room file is stored along with the raw files for each session. 

Alternatively, you can use the empty room recordings made by the MEG operators at the beginning of the day of your MEG recording sessions. For each MEG recording day, you can find these empty room recordings in `/megdata/cbu/camtest/no_name/[yymmdd]/` where  `yymmdd` is the date of the scan. 

### Structural MRI
Please refer to [this wiki page](https://imaging.mrc-cbu.cam.ac.uk/imaging/dicom-bids#Where_are_your_raw_data) on how to find the MRI scans belonging to your MEG participant. You will need what's referred to as `subject code` and `project code` in the wiki page to be able to locate a particular participant. These could be structural scans which you collected or you could reuse already existing structural scans of your participants if they had been scanned at the CBU before. In the latter case, ask the [MRI administrator](mailto:mri.admin@mrc-cbu.cam.ac.uk) to locate these scans for you. 

## Detailed instructions
### 1. Update the `config.py` file with the appropriate project specific path information. 
 - Update the `project_root` variable so that it points to the root folder of your project
 - By default, the following folder structure is assumed:
     ```
     project_root
     ├── data
     │   ├── rawdata
     │   ├── sourcedata
     ```
 - Please update the `data_root`, `bids_raw_root` and `sourcedata_root` variables if you wish to set up a different folder structure. `sourcedata_root` is the folder where the temporary MEG and MRI data will be saved during the conversion process and will be deleted after the conversion is complete. You can change this behaviour by setting the `delete_source` variable to `False`. 
 - Please update the `event_info_path` and `subject_info_path` variables if you wish to save the `event_info.json` and `subject_info.json` files in a different location.
 - Plese update the `meg_system` variable depending on which MEG system was used to collect the data. This should be a string. The default value is `"triux"` for the new system. Alternatively it can be `"vectorview"` for the old system.
 - Please update the `event_channels` variable if you wish to specify the channels that contain the event triggers. This should be a list of strings. By default this is set to `["STI101"]`, which takes into account all the trigger channels in the MEG data (`STI001 - STI016`). Alternatively, you can specify certain trigger channels by their names, e.g. `["STI001", "STI002"]`. In this case, the event values will be extracted from the specified channels only. Please refer to [this](https://imaging.mrc-cbu.cam.ac.uk/meg/IdentifyingEventsWithTriggers) and [this wiki page](https://imaging.mrc-cbu.cam.ac.uk/meg/Triggers) for more information on how triggers are encoded by the CBU MEG system and the common issues and pitfalls regarding reading events from `STI` channels.
 - Please update the `auditory_event_values` and `visual_event_values` lists if you wish to adjust the event times to account for the audio and visual latencies. `auditory_event_values` and `visual_event_values` are the event values (triggers) for auditory and visual events, respectively. These are used to adjust the event times to account for the audio and visual latencies. It is recommended to look up the event values from the event_info.json file, but they can also be hard coded in `config.py`. These should be lists of integers. If either is an empty list, the corresponding event times will not be adjusted. 
### 2. Update the `subject_info.json` file with the appropriate information for each subject.
  - The `subject_info.json` file contains information about each participant. This information is used in the the BIDS conversion process. 
  - Each top level JSON object (or dictionary) in `subject_info.json` should have a key of numbers represented as a string (usually the serial order in which the data were collected) and should have the following sub dictionaries in their value:
      - `bids_id`: The BIDS identifier for the participant, corresponding to the ['sub' BIDS entity](https://bids-specification.readthedocs.io/en/stable/appendices/entities.html#sub). This should be a string. If the value is `null`, the participant will be skipped during the conversion process.
      - `meg_id`: The unique identifier for the participant in the MEG data repository.
      - `meg_date`: The date of the MEG recording session in the format `yymmdd`.
      - `meg_raw_dir`: The path to the directory containing the raw MEG data for the participant.
      - `meg_emptyroom_dir`: The path to the directory containing the empty room recording for the participant. Could be the same as `meg_raw_dir` or different. 
      - `meg_raw_files`: list of dictionaries containing information about the raw MEG files for the participant. Each dictionary should have the following key-value pairs: 
          - `run`: The run number for the raw MEG file corresponding to the ['run' BIDS entity](https://bids-specification.readthedocs.io/en/stable/appendices/entities.html#run). This should be a string.
          - `task`: The name of the task performed during the run, corresponding to the ['task' BIDS entity](https://bids-specification.readthedocs.io/en/stable/appendices/entities.html#task). This should be a string.
          - `file`: The name of the raw MEG file. This should be a string with file extension included. 
      - `meg_bad_channels`: list of bad channels for the participant as noted by the MEG operator during the recording session. This should be a list of strings in the format of `MEG#### or EEG###`, where `#` represents channel numbers. If there were no bad channels, this should be an empty list, `[]`.
      - `mri_id`: The unique identifier for the participant's MRI scan. This should be a string.
      - `mri_date`: The date of the MRI scan in the format `yymmdd`.
      - `mri_nii_file`: The name of the NIfTI file for the participant's MRI scan after conversion from DICOM format. This should be a string with file extension included.
      - `mri_dcm_dir`: The path to the directory containing the DICOM files for the participant's MRI scan. This should be a string. 
  - Simply copy over the example JSON object in `subject_info.json` as many times as you have subjects in your dataset and update the values for each key as appropriate. 
  - **Note**: currently it is assumed that the MEG data were collected in a single session. If you have multiple MEG recording sessions for a participant, you will need to add the ['ses' BIDS identity](https://bids-specification.readthedocs.io/en/stable/appendices/entities.html#ses) to the `meg_raw_files` dictionary and have separate `meg_date` for each session. You'll also need to modify the code in `meg_bids_data_conversion.py` to handle these changes. 
### 3. Update the `event_info.json` file
  - The `event_info.json` file contains information about the event values (triggers) and their labels saved with the raw MEG data. This information is used in the the BIDS conversion process. 
  - Each key-value pair in the JSON object is a mapping of the event label to its value (the trigger recorded in the MEG file). The key should be the label as a string and the value should be the event value (trigger) as an integer.
  - Refer to this [mne-python tutorial](https://mne.tools/stable/auto_tutorials/raw/20_event_arrays.html#mapping-event-ids-to-trial-descriptors) on how to best map event IDs to trial descriptors. 
### 4. Run `meg_bids_data_conversion.py`
  - The `meg_bids_data_conversion.py` script is the main script that does the conversion of the raw MEG data to BIDS format. 
  - The script can be run from the command line as follows (make sure to activate the conda environment containing the required packages before running the script, see the installation section for how to do this):
      ```console
      cd /path/to/your/folder/containing/the/scripts
      python meg_bids_data_conversion.py
      ```
  - The script takes the following command line arguments:
      - `--keep_existing_folders`: If specified, it indicates to keep the existing BIDS folders before conversion. By default they are purged to avoid any conflicts which is recommended, but be careful not to delete important files.   
      - `--adjust_event_times`: If specified, it indicates to adjust the event times to account for the audio and visual latencies. Current (as of 02/2023) auditory and visual latency values are given in `config.py`. If you use this functionality make sure to set the `visual_event_values` and `auditory_event_values` lists in `config.py` to the desired values based on what is defined in `event_info.json`, see [point 1](#1-update-the-configpy-file-with-the-appropriate-project-specific-path-information) above. By default event times are not adjusted. 
      - `--process_structural`: If specified, it indicates to process the structural MRI data. By default structural MRI data are not processed.  
      - `--keep_source_data`: If specified, it indicates to keep the temporary MEG and MRI data saved during the conversion process. By default the source data are deleted after the conversion is complete. 
  - Example usage with fixing EEG locations, adjusting event times and processing structural MRI data
      ```console
      python meg_bids_data_conversion.py --adjust_event_times --process_structural 
      ```
  - The script will convert the raw MEG data for all subjects specified in your `subject_info.json` file to BIDS format. The BIDS data will be saved in the `bids_raw_root` folder specified in the `config.py` file. 
  - The script also fixes EEG channel locations if the data were collected using the old Vectorview system. With the old Vectorview system, for EEG channels > 60, the EEG channel locations obtained from Polhemus digitiser were not copied properly to Neuromag acquisition software. Therefore you must apply mne_check_eeg_locations to your data. Do this as early as possible in the processing  pipeline. There is no harm in applying this function (e.g. if the eeg locations are correct), read more about this [here](http://imaging.mrc-cbu.cam.ac.uk/meg/AnalyzingData/MNE_FixingFIFF). This step is not necessary for the new Triux system.
  - Make sure to keep `meg_bids_data_conversion.py`, `config.py`, `subject_info.json` and `event_info.json` in the same directory.
  

## Further steps
### Add dataset description to your BIDS repository
You can add a [dataset description file](https://bids-specification.readthedocs.io/en/latest/modality-agnostic-files.html#dataset-description) to your BIDS repository. [`mne_bids.make_dataset_description()`](https://mne.tools/mne-bids/stable/generated/mne_bids.make_dataset_description.html#mne_bids.make_dataset_description) provides a convenient way of generating this file. You can see how it is done at the end of this [mne-bids tutorial](https://mne.tools/mne-bids/stable/auto_examples/convert_mne_sample.html#)

### Anonymize your BIDS repository for sharing
As is, the BIDS repository generated by the conversion process is sufficient for you to work on, but it will contain information which in theory could be used along with other pieces of information obtained elsewhere to uniquely identify a participant. For example, the date of the recording is used in the BIDS dataset to link the meg raw data with the corresponding emptyroom recording is one such piece of information. 

If you wish to share your data outside the CBU, you will need to anonymize the BIDS repository. Please read this [mne-bids tutorial](https://mne.tools/mne-bids/stable/auto_examples/anonymize_dataset.html) to learn more about anonymizing a BIDS repository. The package provides a convenient fucntion, [`mne_bids.anonymize_dataset()`](https://mne.tools/mne-bids/stable/generated/mne_bids.anonymize_dataset.html#mne_bids.anonymize_dataset) to do the heavy lifting for you. Keep in mind to double check your anonymized dataset if there are any such pieces of information left in the dataset. Ultimately it is your responsibility make sure that the dataset you're sharing is GDPR compliant. Please email the [methods group](mailto:methods@mrc-cbu.cam.ac.uk) if you have any questions about this.
  
### Derivative analyses
The BIDS standard specifies the 'derivatives' folder where you can save the results of your subsequent analyses. You can read more about this [here](https://bids-specification.readthedocs.io/en/stable/derivatives/introduction.html). Generally, the rules of file naming and folder structure are more relaxed in the derivatives folder, but it is still a good idea to follow the BIDS standard as closely as possible. 
A suggested folder structure for the derivatives would be:
```
project_root
├── data
│   ├── rawdata
│   ├── sourcedata
│   ├── derivatives
│   │   ├── analysis_1
│   │   │   ├── sub-01
│   │   │   ├── etc...
│   │   ├── analysis_2
│   │   │   ├── etc...
```
For setting up folder structure and managing paths when accessing/saving files in your analyses we recommend using the [`BIDSPath`](https://mne.tools/mne-bids/stable/generated/mne_bids.BIDSPath.html#mne_bids.BIDSPath) class provided by the [`mne-bids`](https://mne.tools/mne-bids/stable/index.html) package. You can read more about using `BIDSPath` object in [this tutorial](https://mne.tools/mne-bids/stable/auto_examples/bidspath.html) and see [`meg_bids_data_conversion.py`](https://github.com/MRC-CBU/BIDS_conversion/blob/main/MEG/meg_bids_data_conversion.py) for examples of how to use it. **Pro tip:** set `check=False` when creating a `BIDSPath` object to avoid imposing strict BIDS compliance on file naming in your derivatives folder.