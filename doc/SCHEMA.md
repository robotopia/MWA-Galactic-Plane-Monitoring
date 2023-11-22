# Schema for the GPM processing database

## Overview diagram

```mermaid
---
title: Schema
---
erDiagram
    OBSERVATION }o--o{ OBSERVATION : "cal_obs_id: Currently assigned calibration obs"
    ACACIA_FILE }|--|{ OBSERVATION : "obs_id"
    APPLY_CAL }|--|{ OBSERVATION : "obs_id: Target obs"
    APPLY_CAL }|--|{ OBSERVATION : "cal_obs_id: Calibration obs"

    OBSERVATION {
        int obs_id(PK)
        string projectid
        float lst_deg
        string starttime
        int duration_sec
        string obsname
        string creator
        float azimuth_pointing
        float elevation_pointing
        float ra_pointing
        float dec_pointing
        int cenchan
        float freq_res
        float int_time
        string delays
        bool calibration
        int cal_obs_id
        string calibrators
        string peelsrcs
        string flags
        bool selfcal
        int ion_phs_med
        int ion_phs_peak
        int ion_phs_std
        bool archived
        int nfiles
        string status
    }
    ACACIA_FILE {
        int id(PK)
        int obs_id(observation)
        string type
        string path
    }
    ANTENNA_FLAG {
        int id(PK)
        int start_obs_id
        int end_obs_id
        int antenna
        string notes
    }
    APPLY_CAL {
        int id(PK)
        int obs_id(observation)
        int cal_obs_id(observation)
        bool usable
        string notes
    }
```

## Tables

| Table | Type | Description |
| :---- | :--- | :---------- |
| `acacia_file`  | Base | The locations of data products that have been uploaded to Acacia |
| `antennaflag`  | Base | Tiles that have been flagged as unusable over a specified time period |
| `apply_cal`    | Base | Calibration solutions that can/can't be applied to specific observations |
| `assigned_cal` | View | Same as `apply_cal`, but shows the epoch instead of the id |
| `calapparent`  | Base | [Deprecated] |
| `epoch`        | View | For each observation, which "epoch" it belongs to. |
| `mosaic`       | Base | Generated mosaics (not currently used) |
| `observation`  | Base | The metadata for MWA observations |
| `processing`   | Base | Processing jobs run on the supercomputer |
| `sources`      | Base | Source models for calibration (currently not used) |
