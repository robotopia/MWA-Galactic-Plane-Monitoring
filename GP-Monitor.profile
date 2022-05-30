#! /bin/bash -l

echo "Loading the glactic plane monitoring pipeline"

if [[ -z $GXBASE ]]
then 
    echo "The GXBASE variable is not available, implying the GLEAM-X pipeline is not available. Exiting. "
    return 1
fi

# Who is running the pipeline, used below for base install
GPMUSER=$(whoami)
export GPMUSER  

# The location of where the GP-Monitoring pipeline is installed
export GPMBASE="/astro/mwasci/${GPMUSER}/MWA-Galactic-Plane-Monitoring/"  

# The location where slurm log files will be saved for GPM tasks
export GPMLOG="${GPMBASE}/logs"

# The locaiton where generated scripts submitted to slurm will be placed for GPM tasks
export GPMSCRIPT="${GPMSCRIPT}/scripts"

# Making sure the path for tasks are available 
export PATH="${PATH}:${GPMBASE}/bin"

# Setting up the path to ensure the base GPM directory available for python scripts
export SINGULARITY_BINDPATH="${SINGULARITY_BINDPATH},${GPMBASE}"

# Manual setup of the python path, meant to be used _within_ the container context
# as at the moment the GPM python code is not a proper module nor built into the 
# container
export PYTHONPATH="$PYTHONPATH:${GPMBASE}:${GPMBASE}/externals/TransientSearch/"

# Loads a file that contains secrets used throughout the pipeline. These include
# - GPMDBHOST
# - GPMDBPORT
# - GPMDBUSER
# - GPMDBPASS
# This GPMSECRETS file is expected to export each of the variables above. 
# This file SHOULD NOT be git tracked! 
GPMSECRETS=
if [[ -f "$GPMSECRETS" ]]
then
    source "$GPMSECRETS"
else
    echo "GPMSECRETS is not found or not set correctly. I think it should be. "
    exit 1
fi

# Creates directories as needed below for the mandatory paths if they do not exist
if [[ ! -d "${GPMLOG}" ]]
then
    mkdir -p "${GPMLOG}"
fi

if [[ ! -d "${GPMSCRIPT}" ]]
then
    mkdir -p "${GPMSCRIPT}"
fi
