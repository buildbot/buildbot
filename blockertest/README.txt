Testing Blocker
===============

Until I can figure out a way to automate this, testing Blocker is a
manual procedure.  Players involved:
  - one master daemon (running on the current host)
  - two slave daemons (also running on the current host)
  - a web browser
  - the 'startpair' script
  - the tester (that'd be you)

The master daemon listens on ports 9922, 9980, 9988, and 9989, so make
sure you don't have another BuildBot master daemon running locally.

All of the test cases use a pair of builders running on the two
slaves.  The slaves are called slaveA and slaveB; the first test case
uses builder1A and builder1B.  No prizes for guessing which slave each
builder runs on.

Generally, the tests work by having a Blocker step in the "B" build
wait for something in the corresponding "A" build.

Oh yeah, the test infrastructure and the test cases themselves are
terribly Unix-centric.  That's nothing to with Blocker; it should work
anywhere that Python, Twisted, and Buildbot work.  I'll worry about
making the tests portable when I make them automatic.

Here's how it works:

  - create a virtualenv with BuildBot master and slave both installed:
      virtualenv --no-site-packages /usr/local/buildbot
      source /usr/local/buildbot/bin/activate
      (cd master && python setup.py develop)
      (cd slave && python setup.py develop)

    (If you choose to put the virtual env in a different directory,
    make sure to override VIRTUALENV on the make command line in
    the following steps.)

  - run "make setup" to create the master and slave directories:
    master, slaveA, and slaveB

  - run "make start" to launch all three daemons

  - run "./startpair 1" to run the test case 1: this starts two builds
    running concurrently under builder1A (slaveA) and builder1B (slaveB)

  - hit http://localhost:9980/waterfall in your browser, and inspect the
    outcome of the two builds (builder1A and builder1B) to ensure that it
    meets the expected outcome for test case 1 (see below)

  - repeat for all other test cases

  - run "make stop" to stop all three daemons

  - run "make clean" to blow away the master and slave directories

If things get messy, you can use "make hard-restart" to remove all build
history and restart the daemons from scratch.


Test Cases
==========

Test 1: dead simple
-------------------

builder1B is blocked by the "sleep" step in builder1A.

EXPECTED OUTCOME:
  - both builders: success
  - step 'blockB' succeeds with status text "upstream success after 3.0 sec"
    (note: all times are approximate; depending on your hardware, this
    might be as low as 2.5 sec due to overhead in BuildBot)


Test 2: same, with more steps
-----------------------------

The same basic idea, but run some commands around the blocking step in
builder2A and the blocked step in builder2B.

EXPECTED OUTCOME:
  - both builders: success
  - step 'block' has status text "upstream success after 3.0 sec"
    (again, this might be as low as 2.5 sec)
  - steps builder2A.date and builder2B.date both print the same time
    (possibly differing by tens of milliseconds)


TEST 3: ping-pong blockers
--------------------------

B blocks on a "setup" step in A, then A and B concurrently run "build"
steps for a bit, then A blocks on B.

EXPECTED OUTCOME:
  - both builders: success
  - 'blockB' success with status text "upstream success after 3.0 sec"
    (because 'setupA' takes 3 sec to run)
  - 'blockA' success with status text "upstream success after 3.0 sec"
    (because 'buildB' takes 3 sec longer than 'buildA')
  - 'finishA' and 'finishB' print the same time (again, to within a few
    tens of milliseconds)


TEST 4: Blocker that doesn't block
----------------------------------

B blocks on A, but the blocking step is already done by the time the
Blocker starts, so it succeeds immediately.

EXPECTED OUTCOME:
  - both builders: success
  - 'blockB' success (no wait) with status text "upstream success after ~0.0 sec"
  - 'finishA' prints a date ~2 sec earlier than 'finishB'


TEST 5: config error (bad builder)
----------------------------------

A Blocker in B refers to a non-existent builder.

EXPECTED OUTCOME:
  - 'blockB' fails with an exception:
    BadStepError: no builder named 'foo'


TEST 6: config error (bad build step)
-------------------------------------

A Blocker in B refers to a non-existent build step in builder A.

EXPECTED OUTCOME:
  - 'blockB' fails with an exception:
    BadStepError: builder 'builder6A' has no step named 'foo'


TEST 7: upstream failure
------------------------

A Blocker in B depends on a step in A that fails.

EXPECTED OUTCOME:
  - both builders: failure
  - 'blockB' fails with status text "upstream failure after 1.0 sec"


TEST 8: multiple upstream steps
-------------------------------

A Blocker can depend on multiple steps from multiple different builds,
including earlier steps in its own build.  (This can be useful when
using a Blocker as a guard against continuing a failed build.)

EXPECTED OUTCOME:
  - both builders: success
  - 'blockB' success with status test "upstream success after 1.0 sec"


TEST 9: multiple upstream steps with failure
--------------------------------------------

Same as test 8, except here the "prep" step fails.

EXPECTED OUTCOME:
  - both builders: failure
  - 'blockB' failure with status test "upstream failure after 1.0 sec"


TEST 10: blocker with timeout
-----------------------------

Build takes 3 sec, so Blocker fails after 1 sec timeout.

EXPECTED OUTCOME:
  - build A: success
  - block B': failure with status text "timed out (1.0 sec)"
