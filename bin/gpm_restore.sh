#!/bin/bash

usage()
{
echo "gpm_restore obsnum
  Restores the given observation(s) from its backup location (Acacia) to disk.
  It both downloads and extracts the backed-up tar file.
  This script does not run anything on the SLURM queue.

  KNOWN ISSUES:
    - This script assumes the tar file does not contain the obsid
      in the file paths. This is only true for backups made in 2024.
      Consequently, restoring a 2022 data set using this script will
      place the data in
         .../[epoch]/[obsid]/[obsid]
      instead of the correct place,
         .../[epoch]/[obsid]

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

echo "$acacia_paths" | while read obsid epoch acacia_path
do
  SCRATCH_PATH=$GPMSCRATCH/$epoch/$obsid
  echo "-----------------------------"
  echo "Downloading $obsid to $SCRATCH_PATH"
  mkdir -p $SCRATCH_PATH
  cd $SCRATCH_PATH
  rclone cat $acacia_path | tar xvzf -
done
