# Calibration Pipeline
## autoflag
```
flagantennae ${obsnum}.ms $flags
```

## autocal 
Interval for ionospheric triage (in time steps). Typically we have 2-minute observations which have been averaged to 4s, so in total they contain 30 time steps. To do useful ionospheric differencing we need to compare the start and the end
```
wget -O "${metafits}" http://ws.mwatelescope.org/metadata/fits?obs_id=${obsnum}
test_fail $?

calibrator=$( pyhead.py -p CALIBSRC "$metafits" | awk '{print $3}' )
RA=$( pyhead.py -p RA "$metafits" | awk '{print $3}' )
Dec=$( pyhead.py -p DEC "$metafits" | awk '{print $3}' )
chan=$( pyhead.py -p CENTCHAN "$metafits" | awk '{print $3}' )

calmodel="${obsnum}_local_gleam_model.txt"

    crop_catalogue.py --ra="${RA}" --dec="${Dec}" --radius=30 --top-bright=250 --metafits="${metafits}" \
                        --catalogue="${catfile}" --fluxcol=S_200 --plot "${obsnum}_local_gleam_model.png" \
                        --output "${obsnum}_cropped_catalogue.fits"
    vo2model.py --catalogue="${obsnum}_cropped_catalogue.fits" --point --output="${calmodel}" \
                --racol=RAJ2000 --decol=DEJ2000 --acol=a --bcol=b --pacol=pa --fluxcol=S_200 --alphacol=alpha
```
Check whether the phase centre has already changed, the calibration will fail if it has. The measurement set must be shifted back to its original position.
```
current=$(chgcentre "${obsnum}.ms")
coords=$($GPMBASE/gleam_x/bin/calc_optimum_pointing.py --metafits "${metafits}")
chgcentre \
  "${obsnum}.ms" \
  ${coords}
```
uv range for calibration based on GLEAM-based sky model. Calibrate takes a maximum uv range in metres. Calculate min uvw in metres.
```
minuvm=$(echo "568 * ${minuv} / ${chan}" | bc -l)
```
In wavelengths, maximum 128T baseline at 200MHz was 1667 lambda long. 300/1.28 * 1667 = 390000. Calculate max uvw in metres.
```
maxuvm=$(echo "390000 / (${chan} + 11)" | bc -l)
```
Ionospheric Triage
```
solutions="${obsnum}_${calmodel%%.txt}_solutions_ts${ts}.bin"
```
Remove duplicate obsnum
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
At the moment, assume that the ionosphere is OK, and derive some real solutions.
```
solutions="${obsnum}_${calmodel%%.txt}_solutions_initial.bin"
```
Remove duplicate obsnum
```
solutions="${solutions/${obsnum}_${obsnum}_/${obsnum}_}"
```
Calibrate
```
calibrate \
        -j ${cores} \
        -absmem ${GPMMEMORY} \
        -m "${calmodel}" \
        -minuv $minuvm \
        -applybeam -mwa-path "${MWAPATH}" \
        "${obsnum}".ms \
        "${solutions}"
test_fail $?
```
Create a version divided through by the reference antenna, so that all observations have the same relative XY phase, allowing polarisation calibration solutions to be transferred. This also sets the cross-terms to zero by default
```
aocal_phaseref.py "${solutions}" "${solutions%.bin}_ref.bin" "${refant}" --xy -2.806338586067941065e+01 --dxy -4.426533296449057023e-07  --ms "${obsnum}.ms"
```
Plot calibration solutions
```
aocal_plot.py --refant="${refant}" --amp_max=2 "${solutions%.bin}_ref.bin"
test_fail $?
```
Test to see if the calibration solution meets minimum quality control. At the moment this is a simple check based on the number of flagged solutions. 
```
result=$(check_assign_solutions.py -t "${fraction}" check "${solutions%.bin}_ref.bin")
mv "${solutions%.bin}_ref.bin" "${solutions%.bin}_ref_failed.bin"
    test_fail 1
```

