# Documentation

- [Setting up](#setting-up)
  - [Cloning this repository](#cloning-this-repository)
  - [Loading the GPM profile](#loading-the-GPM-profile)
  - [Obtaining the Singularity container](#obtaining-the-singularity-container)
  - [Setting up an SSH key pair (optional\*)](#setting-up-an-ssh-key-pair-optional)
  - [Loading the GPM profile](#loading-the-gpm-profile)
  - [Database secrets file](#database-secrets-file)
- [Interacting with the database](#interacting-with-the-database)
  - [Add an observation's metadata to the database](#add-an-observations-metadata-to-the-database)
  - [Assign a calibration obs to an observation](#assign-a-calibration-obs-to-an-observation)
  - [Signal that a calibration can/cannot be transferred to a particular observation](#signal-that-a-calibration-cancannot-be-transferred-to-a-particular-observation)
  - [Check the processing history of a particular observation](#check-the-processing-history-of-a-particular-observation)
  - [Get a summary of the processing of a particular Epoch](#get-a-summary-of-the-processing-of-a-particular-epoch)

## Setting up

### Cloning this repository

```
git clone git@github.com:robotopia/MWA-Galactic-Plane-Monitoring.git
```

### Obtaining the Singularity container

To build the container from source, see [Containers](../containers).

If you have access to Acacia and have the required priviliges, a copy of the container can be obtained from `mwasci/gpmon2/containers/`, e.g.
```
mc cp mwasci/gpmon2/containers/gpm_tools-v0.2.img $GPMBASE/containers/gpm_tools-v0.2.img
```
The container can be placed anywhere, as long as the `GPMCONTAINER` environment variable points to it (see [Loading the GPM profile](#loading-the-gpm-profile)).

### Setting up an SSH key pair (optional\*)
\*I think

The [GPM profile](#loading-the-gpm-profile) includes the environment parameter `GPMSSH`, which should point to a local private SSH key.
If you need to create a new public/private key pair, or if you would like to have an SSH key that is used solely by this software, you can do it in the usual way by running the command
```
ssh-keygen
```
and following the prompts.
Place the keys in a directory that makes sense for your system.

### Loading the GPM profile

Make a copy of the file `GP-Monitor.profile` and edit it according to the computing environment that is being used to run the pipeline.
Do not git-track the copied file.

For example,

```
cp GP-Monitor.profile GP-Monitor-garrawarla.profile
# [edit GP-Monitor-garrawarla.profile]
```

Then, `source` it to "load the profile":

```
source GP-Monitor-garrawarla.profile
```

**NB:** The first time you load the profile, it will download a few files that are needed for certain parts of the data processing.
The files are quite large, so make sure you run the command from a file system that has adequate storage.
For example, on Pawsey systems, do not run it from your home directory, which sits on a login node with minimal storage.

### Database secrets file

Users of the GPM software will be granted access to the GPM processing database via the set of "secret" environment variables:
```
GPMDBHOST
GPMDBPORT
GPMDBUSER
GPMDBPASS
```

Keep these environment variables in a file of your choosing and make it (somewhat) secure by setting the permission flags to
```
chmod 600 /path/to/secrets/file
```

The `GPMSECRETS` environment variable (see [Interacting with the database](#interacting-with-the-database)) should be set to the path to this file.

## Interacting with the database

Once the [profile has been loaded](#load-the-gpm-profile), the environment variable `GPMCONTAINER` contains the path to a singularity container in which various operations, jobs, and scripts can be run, including the database scripts described in this section.
To run a command inside the container, preface the command with
```
singularity exec $GPMCONTAINER ...
```
In addition, be aware that the database scripts themselves will not (by default) be in your path, so you will typically need to give the path to their location as well.
For example, even though the documentation below describes commands such as
```
gpm_track.py import_obs --obs_id 1346053400
```
in reality, the command you will run will be
```
singularity exec $GPMCONTAINER $GPMBASE/gpm_track.py obs_processing --obs_id 1346053400
```

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
