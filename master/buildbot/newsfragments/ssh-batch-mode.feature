SSH connections are now run with ``-o BatchMode=yes`` to prevent interactive
prompts which may tie up a step until it times out. From the SSH docs:

  If set to yes, user interaction such as password prompts and host key
  confirmation requests will be disabled. This option is useful in scripts and
  other batch jobs where no user is present to interact with ssh.

This will allow a step to immediately fail and the error can now be inspected.
Steps which make their own SSH connections are encouraged to also use
``-o BatchMode=yes`` in order to not have surprising behaviors if the host
configuration is different.
