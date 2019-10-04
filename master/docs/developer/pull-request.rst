Submitting Pull Requests
========================

As Buildbot is used by software developers, it tends to receive a significant number of patches.
The most effective way to make sure your patch gets noticed and merged is to submit it via GitHub.
This assumes some familiarity with git, but not too much. Note that GitHub has some great `Git guides <http://github.com/guides>`_ to get you started.

Guidelines
----------

* Pull requests should be based on the latest development code, not on the most recent release.
  That is, you should check out the `master` branch and develop on top of it.

* Final pull requests should include code changes, relevant documentation changes, and relevant unit tests.
  Any patch longer than a few lines which does not have documentation or tests is unlikely to be merged as is.
  The developers will most likely ask to add documentation or tests.

* Individual commits should, to the extent possible, be single-purpose.
  Please do not lump all of the changes you made to get Buildbot working the way you like into a single commit.

* Pull requests must pass all tests that run against the GitHub pull requests.
  See :ref:`LocalTestingCheatSheet` for instructions of how to launch various tests locally.

* Python code in Buildbot uses four-space indentations, with no tabs.
  Lines should be wrapped before the 100th column.

* Pull requests must reliably pass all tests.
  Buildbot does not tolerate "flaky" tests.
  If you have trouble with tests that fail without any of your changes applied, get in touch with the developers for help.

* Pull requests that add features or change existing behavior should include a brief description in the release notes.
  See the master/buildbot/newsfragments directory and read the `README.txt <https://github.com/buildbot/buildbot/blob/master/master/buildbot/newsfragments/README.txt>`_ file therein.

* Git commit messages form the "ChangeLog" for Buildbot, and as such should be as descriptive as possible.

* Backward and forward compatibility is important to Buildbot.
  Try to minimize the effect of your patch on existing users.

Additional suggestions
~~~~~~~~~~~~~~~~~~~~~~

The Buildbot developers are quite busy, and it can take a while to review a patch.
While the following are not required, they will make things easier for you and the developers:

* Make a distinct pull request, on a distinct branch in your repository, for each unrelated change.
  Some pull request may get merged immediately, while others will require revision, and this can get very confusing in a single branch.

* Smaller, incremental commits are better than one large commit, as they can be considered on their own merits.
  It's OK for a commit to add code that is unused (except for tests, of course) until a subsequent commit is applied.

* If an individual change is complex or large, it makes sense to create an unpolished PR at first to gather feedback.
  When the Buildbot developers confirm that the presented pull request is the way to go, it can be polished as a second step.

* Git history is the primary means by which Buildbot establishes authorship.
  Be careful to credit others for their work, if you include it in your code.

How to create a pull request
----------------------------

.. note::

   See `this github guide <https://help.github.com/en/articles/fork-a-repo>`_ which offers a more generic description of this process.

* Sign up for a free account at http://github.com, if you don't already have one.

* Go to http://github.com/buildbot/buildbot and click “fork”.
  This will create your own public copy of the latest Buildbot source.

* Clone your forked repository on your local machine, so you can do your changes.
  GitHub will display a link titled "Your Clone URL".
  Click this link to see instructions for cloning your URL.
  It's something like:

.. code-block:: bash

    git clone git@github.com:myusername/buildbot.git
    cd buildbot

* Locally, create a new branch based on the `master` branch:

.. code-block:: bash

    git checkout -b myfixes origin/master

* Hack mercilessly.
  If you're a git aficionado, you can make a neat and pretty commit sequence; otherwise, just get it done.
  Don't forget to add new test cases and any necessary documentation.

* Test your changes.
  See :ref:`LocalTestingCheatSheet` for instructions of how to launch various tests locally.

* Commit.
  For this step it's best to use a GUI for Git.
  See this `list <https://git-scm.com/downloads/guis>`_ of known Git GUIs.
  If you only want to use the shell, do the following:

.. code-block:: bash

    git add $files_that_matter
    git commit

* When you're confident that everything is as it should be, push your changes back to your repository on GitHub, effectively making them public.

.. code-block:: bash

    git push origin myfixes

* Now all that's left is to let the Buildbot developers know that you have patches awaiting their attention.
  In your web browser, go to your repository (you may have to hit "reload") and choose your new branch from the "all branches" menu.

* Double-check that you're on your branch, and not on a particular commit.
  The current URL should end in the name of your patch, not in a SHA1 hash.

* Click “Pull Request”

* Double-check that the base branch is "buildbot/buildbot@master".
  If your repository is a fork of the buildbot/buildbot repository, this should already be the case.

* Fill out the details and send away!

.. _LocalTestingCheatSheet:

Local testing cheat sheet
-------------------------

This section details how to locally run the test suites that are run by Buildbot during each PR.
Not all test suites have been documented so far, only these that fail most often.
Before each of the commands detailed below, a virtualenv must be setup as described in :ref:`PythonDevQuickStart`:

.. code-block:: bash

    make virtualenv
    . .venv/bin/activate

If you see weird test results after changing branches of the repository, remove the `.venv` directory and repeat above again.
Note that `pip install -r <file>.txt` only needs to be run once at the beginning of your testing session.

Master unit tests
~~~~~~~~~~~~~~~~~

Tests in this category run the Python unit tests for the master.
These tests are represented by **bb/trial/** test names in the Buildbot CI.
To run locally, execute the following:

.. code-block:: bash

    pip install -r requirements-ci.txt
    trial -j8 buildbot  # change -j parameter to fit the number of cores you have

Worker unit tests
~~~~~~~~~~~~~~~~~

Tests in this category run the Python unit tests for the worker.
These tests are represented by **bb/trial_worker/** test names in the Buildbot CI.
To run locally, execute the following:

.. code-block:: bash

    pip install -r requirements-ciworker.txt
    trial buildbot_worker

Linter checks
~~~~~~~~~~~~~

Tests in this category run simple syntax and style checks on the Python code.
These tests are represented by **bb/pylint/** and **bb/flake8/** test names in the Buildbot CI.
To run locally, execute the following:

.. code-block:: bash

    pip install -r requirements-ci.txt
    make pylint
    make flake8

If you see spell check errors, but your words are perfectly correct, then you may need to add these words to a whitelist at common/code_spelling_ignore_words.txt.

isort
~~~~~

Tests in this category sort the imports in the Python code.
These tests are represented by **bb/isort/** test names in the Buildbot CI.
To run locally, execute the following:

.. code-block:: bash

    pip install -r requirements-ci.txt
    isort

Documentation
~~~~~~~~~~~~~

This test builds the documentation.
It is represented by **bb/docs/** test names in the Buildbot CI.
To run locally, execute the following:

.. code-block:: bash

    pip install -r requirements-ci.txt
    pip install -r requirements-cidocs.txt
    make docs

If you see spell check errors, but your words are perfectly correct, then you may need to add these words to a whitelist at master/docs/spelling_wordlist.txt.

End-to-end tests
~~~~~~~~~~~~~~~~

Tests in this category run the end-to-end tests by launching a full Buildbot instance, clicking on buttons on the web UI and testing the results.
It is represented by **bb/smokes/** test names in the Buildbot CI.
The tests are sometimes unstable: if you didn't change the front end code and see a failure then it's most likely an instability.
To run locally, install a Chrome-compatible browser and execute the following:

.. code-block:: bash

    pip install -r requirements-ci.txt
    make tarballs
    ./common/smokedist.sh whl
