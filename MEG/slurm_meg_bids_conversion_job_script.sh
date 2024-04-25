#!/bin/tcsh
#SBATCH --nodes 1-1
#SBATCH --ntasks 1
#SBATCH --cpus-per-task 1
#SBATCH --time 1:0:00

# setup conda environment
conda activate /imaging/local/software/mne_python/mne1.6.1_0

# navigate to the project root
cd /path/to/your/project/root

# run the meg bids conversion pipeline
python meg_bids_conversion.py