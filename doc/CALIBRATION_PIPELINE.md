# Calibration Pipeline

## autoflag

The flags are obtained from the `gp_monitor` database,
```
flags=$(${GPMBASE}/gpm_track.py --obs_id ${obsnum} obs_flagantennae)
```

Then, they are applied to the measurement set:
```
flagantennae ${obsnum}.ms $flags
```

## autocal 

### Variables

In the table below, variable names in square brackets are for hard-coded values that are never assigned to an explicit variable.

| Variable | Description | Value |
| :------- | :---------- | :---- |
| fraction | Acceptable fraction of flagged baselines | 0.25 |
| sthresh | Segment threshold (currently not used) | 0.4 |
| chan | Receiver channel number | (Depends on observation, but always 157 for GPM) |
| minuv | Minimum baseline  for calibration (in wavelengths) | 75 (=250m at 88 MHz) |
| minuvm | Minimum of UV range for calibration based on GLEAM-based sky model (in metres) | 568 * `minuv` / `chan` = about 271.3 |
| maxumv | Maximum of UV range for calibration based on GLEAM-based sky model (in metres). In wavelengths, maximum 128T baseline at 200MHz was 1667 lambda long
 (300/1.28 * 1667 = 390000). | 390000 / (${chan} + 11) |
| catfile | The input catalogue sky model | `GGSM_updated.fits` |
| calibrator | The name of the calibrator source | (Depends on observation) |
| calmodel | The cropped sky model | `${obsnum}_local_gleam_model.txt` |
| refant | The reference antenna to use when plotting calibration solutions | 0 (for ObsIDs 1300000000 to 1342950000)<br>8 (for ObsIDs > 1342950000)<br>127 (for all other ObsIDs) |
| ts | Number of timesteps to use for ionospheric triage | 10 |
| [top-bright] | The maximum number of brightest sources to keep in the cropped sky model | 250 |
| [radius] | The maximum angular separation from the pointing centre to keep in the cropped sky model (in degrees) | 30 |

### Crop the catalogue

```
    crop_catalogue.py --ra="${RA}" --dec="${Dec}" --radius=30 --top-bright=250 --metafits="${metafits}" \
                        --catalogue="${catfile}" --fluxcol=S_200 --plot "${obsnum}_local_gleam_model.png" \
                        --output "${obsnum}_cropped_catalogue.fits"
    vo2model.py --catalogue="${obsnum}_cropped_catalogue.fits" --point --output="${calmodel}" \
                --racol=RAJ2000 --decol=DEJ2000 --acol=a --bcol=b --pacol=pa --fluxcol=S_200 --alphacol=alpha
```

### Reset phase centre, if needed

Make sure the phase centre is where it should be:
```
current=$(chgcentre "${obsnum}.ms")

if [[ $current == *"shift"* ]]
then
    echo "Detected that this measurement set has undergone a denormal shift; this must be undone before calibration."
    coords=$($GPMBASE/gpm/bin/calc_optimum_pointing.py --metafits "${metafits}")
    echo "Optimally shifting co-ordinates of measurement set to $coords, without zenith shiftback."
    chgcentre \
            "${obsnum}.ms" \
            ${coords}
else
    echo "Detected that this measurement set has not yet had its phase centre changed. Not shifting."
fi
```

### Ionospheric triage

```
solutions="${solutions/${obsnum}_${obsnum}_/${obsnum}_}"
calibrate \
            -t ${ts} \
            -j ${cores} \
            -absmem ${GPMMEMORY} \
            -m "${calmodel}" \
            -minuv ${minuvm} \
            -applybeam -mwa-path "${MWAPATH}" \
            "${obsnum}.ms" \
            "${solutions}"
aocal_plot.py --refant="${refant}" --amp_max=2 "${solutions}"
aocal_diff.py --metafits="${metafits}" --names "${solutions}" --refant="${refant}"
iono_update.py --ionocsv "${obsnum}_ionodiff.csv"
```

We will not automate the *checking* of the output; the next step (deriving real solutions) is carried out regardless.

### Obtain calibration solutions

Set the name of the output file(s):

```
solutions="${obsnum}_${calmodel%%.txt}_solutions_initial.bin"
solutions="${solutions/${obsnum}_${obsnum}_/${obsnum}_}"
```

#### Perform the calibration itself

```
calibrate \
        -j ${cores} \
        -absmem ${GPMMEMORY} \
        -m "${calmodel}" \
        -minuv $minuvm \
        -applybeam -mwa-path "${MWAPATH}" \
        "${obsnum}".ms \
        "${solutions}"
```

#### Apply the "XY polarisation" phase shift

Create a version divided through by the reference antenna, so that all observations have the same relative XY phase, allowing polarisation calibration solutions to be transferred. This also sets the cross-terms to zero by default
```
aocal_phaseref.py "${solutions}" "${solutions%.bin}_ref.bin" "${refant}" --xy -2.806338586067941065e+01 --dxy -4.426533296449057023e-07  --ms "${obsnum}.ms"
```

Plot calibration solutions
```
aocal_plot.py --refant="${refant}" --amp_max=2 "${solutions%.bin}_ref.bin"
```

Test to see if the calibration solution meets minimum quality control. At the moment this is a simple check based on the number of flagged solutions. 
```
result=$(check_assign_solutions.py -t "${fraction}" check "${solutions%.bin}_ref.bin")
if echo "${result}" | grep -q fail
then
    mv "${solutions%.bin}_ref.bin" "${solutions%.bin}_ref_failed.bin"
    test_fail 1
fi
```

