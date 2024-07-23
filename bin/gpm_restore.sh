#!/bin/bash

usage()
{
echo "gpm_restore obsnum
  Restores the given observation(s) from its backup location (Acacia) to disk.
  It both downloads and extracts the backed-up tar file.
  This script does not run anything on the SLURM queue.

  obsnum : the obsid to be restored, or a text file of obsids." 1>&2;
exit 1;
}

# Consume the first argument
obsnum=$1
shift

if [[ $obsnum == "-h" ]]
then
  usage
fi

if [[ -z $obsnum ]]
then
  usage
fi

# Load the rclone module
RCLONE_MODULE=$(module -t --default -r avail "^rclone$" 2>&1 | grep -v ':' | head -1)
module load $RCLONE_MODULE

# Set up being able to run the 
SINGCMD="singularity exec ${GPMCONTAINER}"

acacia_paths=$($SINGCMD $GPMBASE/gpm_track.py acacia_path --obs_file $obsnum)

echo "$acacia_paths" | while read obsid epoch tar_contains_folder acacia_path
do
  if [[ "$tar_contains_folder" == "0" ]]
  then
    SCRATCH_PATH=$GPMSCRATCH/$epoch/$obsid
  else
    SCRATCH_PATH=$GPMSCRATCH/$epoch
  fi
  echo "-----------------------------"
  echo "Downloading $obsid to $GPMSCRATCH/$epoch/$obsid"
  mkdir -p $SCRATCH_PATH
  cd $SCRATCH_PATH
  rclone cat $acacia_path | tar xvzf -
done
