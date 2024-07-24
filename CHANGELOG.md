# Change Log

## v0.6 - 2024-07-23

### Added

- `gpm_restore.sh` script for pulling already-processed observations (e.g. from Acacia)
- An "epoch completion" Django view, for getting a summary of the processing for all available epochs
- A database table for connecting supercomputer users (as tracked in the `processing` table) with Django authenticated users
- Separate epoch overview Django views for the two processing pipeline chains (`GPM2024_transient` and `StokesV`)
- `divide.py`, which was never git-tracked, but always should have been (required for `calc_leakage.py`)

### Changed

- In the user profile, combined "version" and "gitversion" into a single version number, which is now the string that is sent to the database when logging jobs
- In the database, replaced the `acacia_file` view for the more generic `backup` view.
- Updates to documentation, especially definitions of database views

### Fixed

- The algorithm used in `postimage` for Stokes V source finding (which depends on certain calculations based on the Stokes I images)
  - The recombination of `postimageI` and `postimageV` into a single `postimage` step
- Plot outputs of `calc_leakage` no longer clobber each other

## v0.5 - 2024-07-09

### Added

- Form on Django "epoch overview" view to set the calibration observation for a whole epoch

### Changed

- Shorter `--begin` wait time before `transient` job starting

### Fixed

- Misnamed reference to SLURM array job id environment variable, which was causing the `fail` directive to (ironically) fail
- Hard-coded number in `transient` script, which caused it to output the wrong number of timesteps in the HDF5 data cubes.

## v0.4 - 2024-07-03

### Added

- Automatic detection of default singularity module when loading profile
- Git-tag based versioning to be made available in scripts
- `gpm_automatic_processing.sh`, which so far only checks the MWA services for any new observations that have been taken since the most recent observation in the database
- `-d` (dependency) option to `gpm_pipe.sh`
- An `obs_acacia.sh` script for archiving imaged observations to Acacia
- A draft script (not yet working) for making an all-sky image
- `GPMMAXARRAYJOBS` environment variable in profile, for throttling SLURM queue usage
- New Django application to sit on top of database
  - An "epoch overview" view for visualising the completion of processing jobs

### Changed

- Reverted to looking for available calibration solution on disk (instead of trying to automatically pull it from Acacia, for example)
- Removed the `-c` option from `obs_apply_cal.sh`
- Removed `-p` options from all scripts (the epoch is now always automatically determined from the database)
- When submitting multi-obs jobs, database updates are now also done in bulk (instead of one taskid at a time)
- Changed `obs_image.sh` so that its sbatch script contains a full set of SLURM directives
- Removed deprecated `obs_manta.sh`

### Fixed

- Corrected clean settings (`msigma` now set to 5, `tsigma` now set to 3), and other potential errors in `wsclean` calls

## v0.3 - 2024-01-11
 
### Changed

- Upgraded `wsclean` version in container to v3.4
- Added documentation describing the overall pipeline
- Replaced the `mantaray` client with `giant-squid`
- Download workflow now consistent with [recommended guidelines](https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/65405030/MWA+ASVO+Use+with+HPC+Systems).

### Fixed

- Sky model is now *always* cropped

## v0.2 - 2023-08-04

### Added

- `gpm_track.py` functionality for labelling obs-cal pairs as usable or not
 
### Changed

- Made this pipeline independent from the GLEAM-X pipeline
- Removed local "auxilliary" (Python) scripts from container, and added paths to them where necessary
- Replaced `gpmonim` with `gpm_obsbycal.sh`.
- Added documentation about previous calibration efforts

## v0.1 - 2022-08-17
 
### Added
   
- Initial working monitoring code, designed to process MWA data as soon as they
  become available
- Detailed sky model of Cygnus A
- 5-minute cadence search plots
- Leakage screen fitter
