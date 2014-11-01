.. _first-run-label:

=========
First Run
=========

Goal
----

This tutorial will take you from zero to running your first buildbot master and slave as quickly as possible, without changing the default configuration.

This tutorial is all about instant gratification and the five minute experience: in five minutes we want to convince you that this project Works, and that you should seriously consider spending some more time learning the system.
In this tutorial no configuration or code changes are done.

This tutorial assumes that you are running on Unix, but might be adaptable easily to Windows.

Thank to virtualenv_, installing buildbot in a standalone environment is very easy. For those more familiar with Docker_, there also exists a :ref:`docker version of these instructions <first-run-docker-label>`. Be warned that Docker can be tricky to get working correctly.

You should be able to cut and paste each shell block from this tutorial directly into a terminal.

.. _Docker: https://docker.com

.. _getting-code-label:

Getting ready
-------------

There are many ways to get the code on your machine. We will use here the most easiest one: via ``pip`` in a virtualenv_. It has the advantage of not polluting your operating system, as everything will be contained in the virtualenv.

To make this work, you will need the following installed:

* Python_ and the development packages for it
* virtualenv_

.. _Python: https://www.python.org/
.. _virtualenv: https://pypi.python.org/pypi/virtualenv

Preferably, use your distribution package manager to install these.

You will also need a working Internet connection, as virtualenv and
pip will need to download other projects from the Internet.

.. note::

    Buildbot does not require root access.  Run the commands in this tutorial
    as a normal, unprivileged user.

Let's dive in by typing at the terminal::

  cd
  mkdir tmp
  cd tmp
  virtualenv --no-site-packages buildbot
  cd buildbot

Creating a master
-----------------

Now that we are ready, we need to install buildbot : from the same directory (``tmp/buildbot``), run the following command::

  ./bin/pip install buildbot

Now that buildbot is installed, it's time to create the master::

  ./bin/buildbot create-master master
 
Buildbot needs a configuration file to teach him what to do, we will use the sample one unchanged::
 
  mv master/master.cfg.sample master/master.cfg

Finally start the master::

  ./bin/buildbot start master

You will now see some log information from the master in this terminal. It should ends with lines like this::

    2014-11-01 15:52:55+0100 [-] BuildMaster is running
    The buildmaster appears to have (re)started correctly.

From now on, feel free to visit the web status page running on the port 8010: http://localhost:8010/

Our master now needs (at least) a slave to execute its commands, heads on to the next section !

Creating a slave
----------------

The buildslave will be executing the commands sent by the master. In this tutorial, we are using the pyflakes project as an example. As a consequence of this, your slave will need access to the git_ command in order to checkout some code. Be sure that it is installed, or the builds will fail.

To save some time, we will use the same sandbox we created before. It would however be completely ok to do this in a separate sandbox, or even on another computer - as long as the *slave* computer is able to connect to the *master* one::

  cd
  cd tmp/buildbot

Install the ``buildslave`` command::

   ./bin/pip install buildbot-slave

Now, create the slave::

  ./bin/buildslave create-slave slave localhost example-slave pass

.. note:: If you decided to create this from another computer, you should of course replace ``localhost`` with the name of the computer where your master is running.

The username (``example-slave``), and password (``pass``) should be the same as the ones in
:file:`master/master.cfg`; verify this is the case by looking at the section for ``c['slaves']``::

  cat master/master.cfg

And finally, start the slave::

  ./bin/buildslave start slave

Check the slave's output, it should end with lines like the following::

  2014-11-01 15:56:51+0100 [-] Connecting to localhost:9989
  2014-11-01 15:56:51+0100 [Broker,client] message from master: attached
  The buildslave appears to have (re)started correctly.

Meanwhile, from the other terminal, in the master log (:file:``twisted.log`` in the master directory), you should see lines like this::

  2014-11-01 15:56:51+0100 [Broker,1,127.0.0.1] slave 'example-slave' attaching from IPv4Address(TCP, '127.0.0.1', 54015)
  2014-11-01 15:56:51+0100 [Broker,1,127.0.0.1] Got slaveinfo from 'example-slave'
  2014-11-01 15:56:51+0100 [-] bot attached

You should now be able to go to http://localhost:8010, where you will see a web page similar to:

.. image:: _images/index.png
   :alt: index page

Click on the `Waterfall Display link <http://localhost:8010/waterfall>`_ and you get this:

.. image:: _images/waterfall-empty.png
   :alt: empty waterfall.

Your master is now waiting for the pyflakes maintainer to push some new code in order to run the testsuite on it. Feel free to contact him, would the testsuite fail !

That's the end of the first tutorial.
A bit underwhelming, you say?
Well, that was the point!
We just wanted to get you to dip your toes in the water.
It's easy to take your first steps, but this is about as far as we can go without touching the configuration.

You've got a taste now, but you're probably curious for more.
Let's step it up a little in the second tutorial by changing the configuration and doing an actual build.
Continue on to :ref:`quick-tour-label`.

.. _git: http://git-scm.com/
