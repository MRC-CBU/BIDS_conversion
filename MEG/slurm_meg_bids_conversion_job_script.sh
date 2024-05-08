#!/bin/tcsh
#SBATCH --nodes 1-1
#SBATCH --ntasks 1
#SBATCH --cpus-per-task 1
#SBATCH --time 1:0:00

# setup conda environment
conda activate /imaging/local/software/mne_python/mne1.6.1_0

# navigate to the project root (you need to update this path
# to your project root)
cd /path/to/your/project/root

# run the meg bids conversion pipeline
# you can add any additional arguments after the command 
# in the form of --arg_name arg_value
python meg_bids_data_conversion.py