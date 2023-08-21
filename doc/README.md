# Documentation

## Load the GPM profile

Make a copy of the file `GP-Monitor.profile` and edit it according to the
computing environment that is being used to run the pipeline. Do not git-track
the copied file.

For example,

```
cp GP-Monitor.profile GP-Monitor-garrawarla.profile
# [edit GP-Monitor-garrawarla.profile]
```

Then, `source` it to "load the profile":

```
source GP-Monitor-garrawarla.profile
```

## Database operations

### Add an observation's metadata to the database

```
singularity exec ${GXCONTAINER} gpm_track.py import_obs --obs_id [OBS_ID]
```

### Assign a calibration obs to an observation

```
singularity exec ${GXCONTAINER} gpm_track.py obs_calibrator --obs_id [OBS_ID] --cal_id [CAL_ID]
```

### Signal that a calibration can/cannot be transferred to a particular observation

```
singularity exec ${GXCONTAINER} ./gpm_track.py update_apply_cal --obs_id 1343057752 --cal_id 1343041216 --field usable --value 0
```

(`--value 0` for "cannot be transferred", `--value 1` for "can be transferred")

To add a note about why,

```
singularity exec ${GXCONTAINER} ./gpm_track.py update_apply_cal --obs_id 1343057752 --cal_id 1343041216 --field notes --value "The cable lengths have changed in the meantime"
```
