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
gpm_track.py import_obs --obs_id [OBS_ID]
```

### Assign a calibration obs to an observation

```
gpm_track.py obs_calibrator --obs_id [OBS_ID] --cal_id [CAL_ID]
```

### Signal that a calibration can/cannot be transferred to a particular observation

```
gpm_track.py update_apply_cal --obs_id [OBS_ID] --cal_id [CAL_ID] --field usable --value [0 or 1]
```

(`--value 0` for "cannot be transferred", `--value 1` for "can be transferred")

To add a note about why,

```
gpm_track.py update_apply_cal --obs_id [OBS_ID] --cal_id [CAL_ID] --field notes --value "[Some notes here]"
```

### Check the processing history of a particular observation

This only reports processing steps that have been run by you (i.e. `$GPMUSER`):
```
gpm_track.py obs_processing --obs_id [OBS_ID]
```

### Get a summary of the processing of a particular Epoch

This only reports processing steps that have been run by you (i.e. `$GPMUSER`):
```
gpm_track.py epoch_processing --epoch [EPOCH]
```

An example of a valid epoch name is `Epoch0123`.
