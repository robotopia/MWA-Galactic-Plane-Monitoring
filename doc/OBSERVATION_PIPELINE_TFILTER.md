# Observation Pipeline: tfiler
## tfilter
Run filtering on the transient HDF5 files. Upload the results to the ADACS Nimbus instance.
```
filtercmds=('space_corr 8 time_corr_gauss_multi 0 time_max 0' 'space_corr 8 stdev 0' 'space_corr 8 spike 0 time_max 0' 'space_corr 8  time_corr_gauss 0 time_max 0' 'time_corr_gauss 0 time_max 0')
filternames=('tcgm' 'std' 'spike' 'dbtcg' 'tcg')
cutoffs=('--std --cutoff 7.5' '--std --cutoff 7.5' '--cutoff 7.5' '--std --cutoff 7.5' '--std --cutoff 7.5')
nfilters=${#filternames[@]}
```
Data required for all filters. This is to get the light curve peak values later
```
if [[ ! -e ${obsnum}_max.fits ]]
then
    DoFilter.py ${obsnum}_transient.hdf5 ${obsnum}_max.fits time_max 0
fi
```
This is to get the known source residuals later
```
if [[ ! -e ${obsnum}_stdev.fits ]]
then
    DoFilter.py ${obsnum}_transient.hdf5 ${obsnum}_stdev.fits stdev 0
fi
```
This is to get help filter aliases later
```
if [[ ! -e ${obsnum}_mean.fits ]]
then
    DoFilter.py ${obsnum}_transient.hdf5 ${obsnum}_mean.fits mean 0
fi

if [[ ! -e ${obsnum}_known.fits ]]
then
```
This gives us a way to test what the ionospheric distortions typically look like, later ("mean" is just used as a template)
```
GetKnownSources.py ${obsnum}_mean.fits ${obsnum}_tmp.fits ${GPMBASE}/models/GGSM.fits
```
This gets the value of the primary beam at the locations of known sources
```GetValsAtCoords.py --vals-from beam --vals-name beam --in_fname ${obsnum}_tmp.fits --out_fname ${obsnum}_tmp.fits
```
This gets the stdevs at locations of known sources (nks_ prepended during xmatch)
```
GetValsAtCoords.py --vals-from ${obsnum}_stdev.fits --vals-name std --in_fname ${obsnum}_tmp.fits --out_fname ${obsnum}_tmp.fits
```
This gets the means at locations of known sources (nks_ prepended during xmatch)
```
GetValsAtCoords.py --vals-from ${obsnum}_mean.fits --vals-name mean --in_fname ${obsnum}_tmp.fits --out_fname ${obsnum}_known.fits
    rm ${obsnum}_tmp.fits
fi
```
Filter loop
```
for (( i=0; i<$nfilters; i++ ))
do
    filtcmd=${filtercmds[$i]}
    filtname=${filternames[$i]}
    cutoff=${cutoffs[$i]}

    if [[ ! -e ${obsnum}_${filtname}.fits ]]
    then
        DoFilter.py ${obsnum}_transient.hdf5 ${obsnum}_${filtname}.fits ${filtcmd}
    fi
```
Candidate detection
```
if [[ ! -e results/${obsnum}_${filtname}_cands_wstats_selected.fits ]]
    then
```
Found that a cutoff of 7.5 was best compromise between sensitivity and detection rate
```
DoIslanding.py --in ${obsnum}_${filtname}.fits --out ${obsnum}_tmp.fits ${cutoff} --peak-name can_det_stat --filter-name ${filtname}
```
This gets the value of the primary beam at the locations of the detected candidates
```
GetValsAtCoords.py --vals-from beam --vals-name can_beam --in_fname ${obsnum}_tmp.fits --out_fname ${obsnum}_tmp.fits
```
This gets the peaks of the light curves at the locations of the detected candidates
```
GetValsAtCoords.py --vals-from ${obsnum}_max.fits --vals-name can_peak_flux --in_fname ${obsnum}_tmp.fits --out_fname ${obsnum}_tmp.fits
```
This gives us a way to check for aliases
```
GetValsAtCoords.py --vals-from ${obsnum}_mean.fits --vals-name can_mean --in_fname ${obsnum}_tmp.fits --out_fname ${obsnum}_tmp.fits
```
This gets the standard deviation through the cube at the locations of the detected candidates
```
GetValsAtCoords.py --vals-from ${obsnum}_stdev.fits --vals-name can_std --in_fname ${obsnum}_tmp.fits --out_fname ${obsnum}_${filtname}_cands.fits
```
Nearest Known Source characterisation
This gets the detection statistics at the locations of known sources (nks_ prepended during xmatch)
```
GetValsAtCoords.py --vals-from ${obsnum}_${filtname}.fits --vals-name det_stat --in_fname ${obsnum}_known.fits --out_fname ${obsnum}_${filtname}_knownsrcs.fits
```
Cross-matching
This puts the cross-match information in the original table
```
DoCrossMatching.py --in-fname ${obsnum}_${filtname}_cands.fits --match-fname ${obsnum}_${filtname}_knownsrcs.fits
```
Add some useful statistics
```
AddStats.py --cands ${obsnum}_${filtname}_cands.fits --known ${obsnum}_${filtname}_knownsrcs.fits --out_fname ${obsnum}_${filtname}_cands_wstats.fits
```
Cutting sources based on statistics
```
SelectSources.py --in_fname ${obsnum}_${filtname}_cands_wstats.fits --out_fname ${obsnum}_${filtname}_cands_wstats_selected.fits --match_fname ${GPMBASE}/models/GGSM.fits
```
 Plotting: Make plots
 ```
DiagnosticPlots.py --candidates ${obsnum}_${filtname}_cands_wstats_selected.fits --observation ${obsnum}_transient.hdf5 --filter ${obsnum}_${filtname}.fits --known ${obsnum}_${filtname}_knownsrcs.fits
        if [[ ! -d results ]]
        then
            mkdir results/
        fi
```
