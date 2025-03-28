# Automatic processing

To keep up with the observations as they roll in, the following steps need to be taken.
The cadence of these steps can change according to needs, but a typical pipeline might run this daily, for example.

These steps are implemented in `bin/gpm_automatic_processing.sh`.
It takes one optional argument: how many hours before the present to consider processing observations (`NHOURS`).
(The default is 24, meaning 24 hours = 1 day.)

## Algorithm steps

1. Find the new observations that have taken since the last time this script was run, and import them into the database. (NB: This is not affected by `NHOURS`.)
  - Get the most recent obsid from the database
  - Get any observations that have occurred since then
  - Import them into the database
2. Get the observations to be processed within the last `NHOURS` hours.

