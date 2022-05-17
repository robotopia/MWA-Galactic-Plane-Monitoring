#!/usr/bin/env python

# Determine the epoch number for our Galactic Monitoring campaign

import datetime

# Epoch numberering starts 1st May 2022
epoch0 = datetime.datetime.strptime("2022-05-01 00:00:00","%Y-%m-%d %H:%M:%S")
now = datetime.datetime.utcnow()
diff = now - epoch0
# Y2k is 2032
print(f"{int(diff.days/7):03d}")
