# Transfer calibration solutions

The script `transfer_delays.py` is intended to be used in those cases where there has been a "delay-like" change (e.g. caused by a change of temperature which in turn causes the cable lengths to change) between a calibration observation and a target observation.
Sometimes, there may have been another calibration observation taken closer in time to the target observation, but for whatever reason did not yield a good calibration solution.
If, however, the solution is good *enough* to see that it is similar to the first calibration solution modulo some delay-like change, then this script will generate a new solution using the original "good" solution as a starting point, and adding a phase offset so that it matches as closely as possible to the "bad" solution.
