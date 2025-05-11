
A Somewhat Whimsical Example (or "It's now customized, how do I deploy it?")
----------------------------------------------------------------------------

Let's say that we've got some snazzy new unit-test framework called Framboozle. It's the hottest
thing since sliced bread. It slices, it dices, it runs unit tests like there's no tomorrow. Plus if
your unit tests fail, you can use its name for a Web 2.1 startup company, make millions of dollars,
and hire engineers to fix the bugs for you, while you spend your afternoons lazily hang-gliding
along a scenic pacific beach, blissfully unconcerned about the state of your tests.
[#framboozle_reg]_

To run a Framboozle-enabled test suite, you just run the 'framboozler' command from the top of your
source code tree. The 'framboozler' command emits a bunch of stuff to stdout, but the most
interesting bit is that it emits the line "FNURRRGH!" every time it finishes running a test case
You'd like to have a test-case counting LogObserver that watches for these lines and counts them,
because counting them will help the buildbot more accurately calculate how long the build will
take, and this will let you know exactly how long you can sneak out of the office for your
hang-gliding lessons without anyone noticing that you're gone.

This will involve writing a new :class:`BuildStep` (probably named "Framboozle") which inherits
from :bb:step:`ShellCommand`. The :class:`BuildStep` class definition itself will look something
like this:

.. code-block:: python

    from buildbot.plugins import steps, util

    class FNURRRGHCounter(util.LogLineObserver):
        numTests = 0
        def outLineReceived(self, line):
            if "FNURRRGH!" in line:
                self.numTests += 1
                self.step.setProgress('tests', self.numTests)

    class Framboozle(steps.ShellCommand):
        command = ["framboozler"]

        def __init__(self, **kwargs):
            super().__init__(**kwargs)   # always upcall!
            counter = FNURRRGHCounter()
            self.addLogObserver('stdio', counter)
            self.progressMetrics += ('tests',)

So that's the code that we want to wind up using.
How do we actually deploy it?

You have a number of different options:

.. contents::
   :local:

Inclusion in the :file:`master.cfg` file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The simplest technique is to simply put the step class definitions in your :file:`master.cfg` file,
somewhere before the :class:`BuildFactory` definition where you actually use it in a clause like:

.. code-block:: python

    f = BuildFactory()
    f.addStep(SVN(repourl="stuff"))
    f.addStep(Framboozle())

Remember that :file:`master.cfg` is secretly just a Python program with one job: populating the
:data:`BuildmasterConfig` dictionary. And Python programs are allowed to define as many classes as
they like. So you can define classes and use them in the same file, just as long as the class is
defined before some other code tries to use it.

This is easy, and it keeps the point of definition very close to the point of use, and whoever
replaces you after that unfortunate hang-gliding accident will appreciate being able to easily
figure out what the heck this stupid "Framboozle" step is doing anyways. The downside is that every
time you reload the config file, the Framboozle class will get redefined, which means that the
buildmaster will think that you've reconfigured all the Builders that use it, even though nothing
changed. Bleh.

Python file somewhere on the system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Instead, we can put this code in a separate file, and import it into the master.cfg file just like
we would the normal buildsteps like :bb:step:`ShellCommand` and :bb:step:`SVN`.

Create a directory named :file:`~/lib/python`, put the step class definitions in
:file:`~/lib/python/framboozle.py`, and run your buildmaster using:

.. code-block:: bash

    PYTHONPATH=~/lib/python buildbot start MASTERDIR

or use the :file:`Makefile.buildbot` to control the way ``buildbot start`` works.
Or add something like this to something like your :file:`~/.bashrc` or :file:`~/.bash_profile` or :file:`~/.cshrc`:

.. code-block:: bash

    export PYTHONPATH=~/lib/python

Once we've done this, our :file:`master.cfg` can look like:

.. code-block:: python

    from framboozle import Framboozle
    f = BuildFactory()
    f.addStep(SVN(repourl="stuff"))
    f.addStep(Framboozle())

or:

.. code-block:: python

    import framboozle
    f = BuildFactory()
    f.addStep(SVN(repourl="stuff"))
    f.addStep(framboozle.Framboozle())

(check out the Python docs for details about how ``import`` and ``from A import B`` work).

What we've done here is to tell Python that every time it handles an "import" statement for some
named module, it should look in our :file:`~/lib/python/` for that module before it looks anywhere
else. After our directories, it will try in a bunch of standard directories too (including the one
where buildbot is installed). By setting the :envvar:`PYTHONPATH` environment variable, you can add
directories to the front of this search list.

Python knows that once it "import"s a file, it doesn't need to re-import it again. This means that
reconfiguring the buildmaster (with ``buildbot reconfig``, for example) won't make it think the
Framboozle class has changed every time, so the Builders that use it will not be spuriously
restarted. On the other hand, you either have to start your buildmaster in a slightly weird way, or
you have to modify your environment to set the :envvar:`PYTHONPATH` variable.


Install this code into a standard Python library directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Find out what your Python's standard include path is by asking it:

.. code-block:: none

    80:warner@luther% python
    Python 2.4.4c0 (#2, Oct  2 2006, 00:57:46)
    [GCC 4.1.2 20060928 (prerelease) (Debian 4.1.1-15)] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> import sys
    >>> import pprint
    >>> pprint.pprint(sys.path)
    ['',
     '/usr/lib/python24.zip',
     '/usr/lib/python2.4',
     '/usr/lib/python2.4/plat-linux2',
     '/usr/lib/python2.4/lib-tk',
     '/usr/lib/python2.4/lib-dynload',
     '/usr/local/lib/python2.4/site-packages',
     '/usr/lib/python2.4/site-packages',
     '/usr/lib/python2.4/site-packages/Numeric',
     '/var/lib/python-support/python2.4',
     '/usr/lib/site-python']

In this case, putting the code into :file:`/usr/local/lib/python2.4/site-packages/framboozle.py`
would work just fine. We can use the same :file:`master.cfg` ``import framboozle`` statement as in
Option 2. By putting it in a standard include directory (instead of the decidedly non-standard
:file:`~/lib/python`), we don't even have to set :envvar:`PYTHONPATH` to anything special. The
downside is that you probably have to be root to write to one of those standard include
directories.

.. _Plugin-Module:

Distribute a Buildbot Plug-In
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First of all, you must prepare a Python package (if you do not know what that is, please check
:doc:`../../developer/plugins-publish`, where you can find a couple of pointers to tutorials).

When you have a package, you will have a special file called :file:`setup.py`.
This file needs to be updated to include a pointer to your new step:

.. code-block:: python

    setup(
        ...
        entry_points = {
            ...,
            'buildbot.steps': [
                'Framboozle = framboozle:Framboozle'
            ]
        },
        ...
    )

Where:

* ``buildbot.steps`` is the kind of plugin you offer (more information about possible kinds you can
  find in :doc:`../../developer/plugins-publish`)
* ``framboozle:Framboozle`` consists of two parts: ``framboozle`` is the name of the Python module
  where to look for ``Framboozle`` class, which implements the plugin
* ``Framboozle`` is the name of the plugin.

  This will allow users of your plugin to use it just like any other Buildbot plugins:

  .. code-block:: python

    from buildbot.plugins import steps

    ... steps.Framboozle ...

Now you can upload it to PyPI_ where other people can download it from and use in their build
systems. Once again, the information about how to prepare and upload a package to PyPI_ can be
found in tutorials listed in :doc:`../../developer/plugins-publish`.

.. _PyPI: http://pypi.python.org/

Submit the code for inclusion in the Buildbot distribution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Make a fork of buildbot on http://github.com/buildbot/buildbot or post a patch in a bug at
http://trac.buildbot.net/. In either case, post a note about your patch to the mailing list, so
others can provide feedback and, eventually, commit it.

When it's committed to the master, the usage is the same as in the previous approach:

.. code-block:: python

    from buildbot.plugins import steps, util

    ...
    f = util.BuildFactory()
    f.addStep(steps.SVN(repourl="stuff"))
    f.addStep(steps.Framboozle())
    ...

And then you don't even have to install :file:`framboozle.py` anywhere on your system, since it
will ship with Buildbot. You don't have to be root, you don't have to set :envvar:`PYTHONPATH`. But
you do have to make a good case for Framboozle being worth going into the main distribution, you'll
probably have to provide docs and some unit test cases, you'll need to figure out what kind of beer
the author likes (IPA's and Stouts for Dustin), and then you'll have to wait until the next
release. But in some environments, all this is easier than getting root on your buildmaster box, so
the tradeoffs may actually be worth it.

Summary
~~~~~~~

Putting the code in master.cfg (1) makes it available to that buildmaster instance. Putting it in a
file in a personal library directory (2) makes it available for any buildmasters you might be
running. Putting it in a file in a system-wide shared library directory (3) makes it available for
any buildmasters that anyone on that system might be running. Getting it into the buildbot's
upstream repository (4) makes it available for any buildmasters that anyone in the world might be
running. It's all a matter of how widely you want to deploy that new class.

.. [#framboozle_reg]

   framboozle.com is still available.
   Remember, I get 10% :).
