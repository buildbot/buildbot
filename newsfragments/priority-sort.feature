Build requests are now sorted according to their buildrequest. Request time is now used as a secondary sort key.
Builders are sorted according to the highest priority among all of its unclaimed build requests, with the age of the oldest unclaimed request as the secondary key.
Since all requests are created with priority 0 by default, this does not change default behaviour.
Higher priorities means run before.
