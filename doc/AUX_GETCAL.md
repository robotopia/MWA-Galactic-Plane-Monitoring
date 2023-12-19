# aux_getcal
 Common singularity command to run the python code
```
SINGCMD="singularity exec ${GPMCONTAINER} "
```
Get the associated calibration observation
```
calid=$(${SINGCMD} "${GPMBASE}/gpm_track.py" obs_calibrator --obs_id "$obsid")
if [[ -z "$calid" ]]
then
    echo "No calibrator found for obsid $obsid"
    exit 1
fi
```
Move to the data directory of the calibrator
```
epoch=$(${SINGCMD} "${GPMBASE}/gpm_track.py" obs_epoch --obs_id $calid)
caldir="${GPMSCRATCH}/${epoch}/${calid}"
mkdir -p "$caldir"
cd "${caldir}"
```
Find the calibration file's name from the dabtabase
```
cal_acacia_path=$(${SINGCMD} "${GPMBASE}/gpm_track.py" acacia_path --obs_id $calid --value "calibration solution")
if [[ -z "$cal_acacia_path" ]]
then
    echo "Calibration solution filename has not been entered into the GPM database for calid $calid"
    exit 1
fi

calfile=$(basename "$cal_acacia_path")
```
If it doesn't already exist locally, try to download it from acacia
```
if [[ ! -f "$calfile" ]]
then
    echo "No local copy of calibration solution found. Attempting to download calibration solution from Acacia ($cal_acacia_path)..."
    mc cp "$cal_acacia_path" "$calfile"
fi
```
If it STILL doesn't exist, insist to the user that it should
```
if [[ ! -f "$calfile" ]]
then
    echo "Could not find calibration solution \"$calfile\" either locally ($caldir) or on Acacia ($calfile)"
    echo "Please make it available."
    exit 1
fi
```
Need to confirm the python script works
```
result=$(${SINGCMD} "${GPMBASE}/check_solutions.py" -t 0.5 -s 4 "${calfile}")
if echo "${result}" | grep -q fail
then
    mv "${calfile}" "${calfile%.bin}_failed.bin"
    echo "Calibration solutions file failed checks. Exiting. "
    exit 1
fi
```
Return (by echoing) the full path to the calibration file
```
echo $caldir/$calfile
```
