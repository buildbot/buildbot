.. _fiveminutes:

===================================================
Buildbot in 5 minutes - a user-contributed tutorial
===================================================

(Ok, maybe 10.)

Buildbot is really an excellent piece of software, however it can be a bit confusing for a newcomer (like me when I first started looking at it).
Typically, at first sight it looks like a bunch of complicated concepts that make no sense and whose relationships with each other are unclear.
After some time and some reread, it all slowly starts to be more and more meaningful, until you finally say "oh!" and things start to make sense.
Once you get there, you realize that the documentation is great, but only if you already know what it's about.

This is what happened to me, at least.
Here I'm going to (try to) explain things in a way that would have helped me more as a newcomer.
The approach I'm taking is more or less the reverse of that used by the documentation, that is, I'm going to start from the components that do the actual work (the builders) and go up the chain from there up to change sources.
I hope purists will forgive this unorthodoxy.
Here I'm trying to clarify the concepts only, and will not go into the details of each object or property; the documentation explains those quite well.

Installation
------------

I won't cover the installation; both Buildbot master and worker are available as packages for the major distributions, and in any case the instructions in the official documentation are fine.
This document will refer to Buildbot 0.8.5 which was current at the time of writing, but hopefully the concepts are not too different in other versions.
All the code shown is of course python code, and has to be included in the master.cfg master configuration file.

We won't cover the basic things such as how to define the workers, project names, or other administrative information that is contained in that file; for that, again the official documentation is fine.

Builders: the workhorses
------------------------

Since Buildbot is a tool whose goal is the automation of software builds, it makes sense to me to start from where we tell Buildbot how to build our software: the `builder` (or builders, since there can be more than one).

Simply put, a builder is an element that is in charge of performing some action or sequence of actions, normally something related to building software (for example, checking out the source, or ``make all``), but it can also run arbitrary commands.

A builder is configured with a list of workers that it can use to carry out its task.
The other fundamental piece of information that a builder needs is, of course, the list of things it has to do (which will normally run on the chosen worker).
In Buildbot, this list of things is represented as a ``BuildFactory`` object, which is essentially a sequence of steps, each one defining a certain operation or command.

Enough talk, let's see an example.
For this example, we are going to assume that our super software project can be built using a simple ``make all``, and there is another target ``make packages`` that creates rpm, deb and tgz packages of the binaries.
In the real world things are usually more complex (for example there may be a ``configure`` step, or multiple targets), but the concepts are the same; it will just be a matter of adding more steps to a builder, or creating multiple builders, although sometimes the resulting builders can be quite complex.

So to perform a manual build of our project we would type this from the command line (assuming we are at the root of the local copy of the repository):

.. code-block:: bash

    $ make clean    # clean remnants of previous builds
    ...
    $ svn update
    ...
    $ make all
    ...
    $ make packages
    ...
    # optional but included in the example: copy packages to some central machine
    $ scp packages/*.rpm packages/*.deb packages/*.tgz someuser@somehost:/repository
    ...

Here we're assuming the repository is SVN, but again the concepts are the same with git, mercurial or any other VCS.

Now, to automate this, we create a builder where each step is one of the commands we typed above.
A step can be a shell command object, or a dedicated object that checks out the source code (there are various types for different repositories, see the docs for more info), or yet something else::

    from buildbot.plugins import steps, util

    # first, let's create the individual step objects

    # step 1: make clean; this fails if the worker has no local copy, but
    # is harmless and will only happen the first time
    makeclean = steps.ShellCommand(name="make clean",
                                   command=["make", "clean"],
                                   description="make clean")

    # step 2: svn update (here updates trunk, see the docs for more
    # on how to update a branch, or make it more generic).
    checkout = steps.SVN(baseURL='svn://myrepo/projects/coolproject/trunk',
                         mode="update",
                         username="foo",
                         password="bar",
                         haltOnFailure=True)

    # step 3: make all
    makeall = steps.ShellCommand(name="make all",
                                 command=["make", "all"],
                                 haltOnFailure=True,
                                 description="make all")

    # step 4: make packages
    makepackages = steps.ShellCommand(name="make packages",
                                      command=["make", "packages"],
                                      haltOnFailure=True,
                                      description="make packages")

    # step 5: upload packages to central server. This needs passwordless ssh
    # from the worker to the server (set it up in advance as part of worker setup)
    uploadpackages = steps.ShellCommand(name="upload packages",
                                        description="upload packages",
                                        command="scp packages/*.rpm packages/*.deb packages/*.tgz someuser@somehost:/repository",
                                        haltOnFailure=True)

    # create the build factory and add the steps to it
    f_simplebuild = util.BuildFactory()
    f_simplebuild.addStep(makeclean)
    f_simplebuild.addStep(checkout)
    f_simplebuild.addStep(makeall)
    f_simplebuild.addStep(makepackages)
    f_simplebuild.addStep(uploadpackages)

    # finally, declare the list of builders. In this case, we only have one builder
    c['builders'] = [
        util.BuilderConfig(name="simplebuild", workernames=['worker1', 'worker2', 'worker3'], factory=f_simplebuild)
    ]

So our builder is called ``simplebuild`` and can run on either of ``worker1``, ``worker2`` and ``worker3``.
If our repository has other branches besides trunk, we could create another one or more builders to build them; in the example, only the checkout step would be different, in that it would need to check out the specific branch.
Depending on how exactly those branches have to be built, the shell commands may be recycled, or new ones would have to be created if they are different in the branch.
You get the idea.
The important thing is that all the builders be named differently and all be added to the ``c['builders']`` value (as can be seen above, it is a list of ``BuilderConfig`` objects).

Of course the type and number of steps will vary depending on the goal; for example, to just check that a commit doesn't break the build, we could include just up to the ``make all`` step.
Or we could have a builder that performs a more thorough test by also doing ``make test`` or other targets.
You get the idea.
Note that at each step except the very first we use ``haltOnFailure=True`` because it would not make sense to execute a step if the previous one failed (ok, it wouldn't be needed for the last step, but it's harmless and protects us if one day we add another step after it).

Schedulers
----------

Now this is all nice and dandy, but who tells the builder (or builders) to run, and when?
This is the job of the `scheduler`, which is a fancy name for an element that waits for some event to happen, and when it does, based on that information decides whether and when to run a builder (and which one or ones).
There can be more than one scheduler.
I'm being purposely vague here because the possibilities are almost endless and highly dependent on the actual setup, build purposes, source repository layout and other elements.

So a scheduler needs to be configured with two main pieces of information: on one hand, which events to react to, and on the other hand, which builder or builders to trigger when those events are detected.
(It's more complex than that, but if you understand this, you can get the rest of the details from the docs).

A simple type of scheduler may be a periodic scheduler: when a configurable amount of time has passed, run a certain builder (or builders).
In our example, that's how we would trigger a build every hour::

    from buildbot.plugins import schedulers

    # define the periodic scheduler
    hourlyscheduler = schedulers.Periodic(name="hourly",
                                          builderNames=["simplebuild"],
                                          periodicBuildTimer=3600)

    # define the available schedulers
    c['schedulers'] = [hourlyscheduler]

That's it.
Every hour this ``hourly`` scheduler will run the ``simplebuild`` builder.
If we have more than one builder that we want to run every hour, we can just add them to the ``builderNames`` list when defining the scheduler and they will all be run.
Or since multiple scheduler are allowed, other schedulers can be defined and added to ``c['schedulers']`` in the same way.

Other types of schedulers exist; in particular, there are schedulers that can be more dynamic than the periodic one.
The typical dynamic scheduler is one that learns about changes in a source repository (generally because some developer checks in some change), and triggers one or more builders in response to those changes.
Let's assume for now that the scheduler "magically" learns about changes in the repository (more about this later); here's how we would define it::

    from buildbot.plugins import schedulers

    # define the dynamic scheduler
    trunkchanged = schedulers.SingleBranchScheduler(name="trunkchanged",
                                                    change_filter=util.ChangeFilter(branch=None),
                                                    treeStableTimer=300,
                                                    builderNames=["simplebuild"])

    # define the available schedulers
    c['schedulers'] = [trunkchanged]

This scheduler receives changes happening to the repository, and among all of them, pays attention to those happening in "trunk" (that's what ``branch=None`` means).
In other words, it filters the changes to react only to those it's interested in.
When such changes are detected, and the tree has been quiet for 5 minutes (300 seconds), it runs the ``simplebuild`` builder.
The ``treeStableTimer`` helps in those situations where commits tend to happen in bursts, which would otherwise result in multiple build requests queuing up.

What if we want to act on two branches (say, trunk and 7.2)?
First we create two builders, one for each branch (see the builders paragraph above), then we create two dynamic schedulers::

    from buildbot.plugins import schedulers

    # define the dynamic scheduler for trunk
    trunkchanged = schedulers.SingleBranchScheduler(name="trunkchanged",
                                                    change_filter=util.ChangeFilter(branch=None),
                                                    treeStableTimer=300,
                                                    builderNames=["simplebuild-trunk"])

    # define the dynamic scheduler for the 7.2 branch
    branch72changed = schedulers.SingleBranchScheduler(name="branch72changed",
                                                       change_filter=util.ChangeFilter(branch='branches/7.2'),
                                                       treeStableTimer=300,
                                                       builderNames=["simplebuild-72"])

    # define the available schedulers
    c['schedulers'] = [trunkchanged, branch72changed]

The syntax of the change filter is VCS-dependent (above is for SVN), but again once the idea is clear, the documentation has all the details.
Another feature of the scheduler is that is can be told which changes, within those it's paying attention to, are important and which are not.
For example, there may be a documentation directory in the branch the scheduler is watching, but changes under that directory should not trigger a build of the binary.
This finer filtering is implemented by means of the ``fileIsImportant`` argument to the scheduler (full details in the docs and - alas - in the sources).

Change sources
--------------

Earlier we said that a dynamic scheduler "magically" learns about changes; the final piece of the puzzle are `change sources`, which are precisely the elements in Buildbot whose task is to detect changes in the repository and communicate them to the schedulers.
Note that periodic schedulers don't need a change source, since they only depend on elapsed time; dynamic schedulers, on the other hand, do need a change source.

A change source is generally configured with information about a source repository (which is where changes happen); a change source can watch changes at different levels in the hierarchy of the repository, so for example it is possible to watch the whole repository or a subset of it, or just a single branch.
This determines the extent of the information that is passed down to the schedulers.

There are many ways a change source can learn about changes; it can periodically poll the repository for changes, or the VCS can be configured (for example through hook scripts triggered by commits) to push changes into the change source.
While these two methods are probably the most common, they are not the only possibilities; it is possible for example to have a change source detect changes by parsing some email sent to a mailing list when a commit happens, and yet other methods exist.
The manual again has the details.

To complete our example, here's a change source that polls a SVN repository every 2 minutes::

    from buildbot.plugins import changes, util

    svnpoller = changes.SVNPoller(repourl="svn://myrepo/projects/coolproject",
                                  svnuser="foo",
                                  svnpasswd="bar",
                                  pollinterval=120,
                                  split_file=util.svn.split_file_branches)

    c['change_source'] = svnpoller

This poller watches the whole "coolproject" section of the repository, so it will detect changes in all the branches.
We could have said::

    repourl = "svn://myrepo/projects/coolproject/trunk"

or::

    repourl = "svn://myrepo/projects/coolproject/branches/7.2"

to watch only a specific branch.

To watch another project, you need to create another change source -- and you need to filter changes by project.
For instance, when you add a change source watching project 'superproject' to the above example, you need to change::

    trunkchanged = schedulers.SingleBranchScheduler(name="trunkchanged",
                                                    change_filter=filter.ChangeFilter(branch=None),
                                                    # ...
                                                    )

to e.g.::

    trunkchanged = schedulers.SingleBranchScheduler(name="trunkchanged",
                                                    change_filter=filter.ChangeFilter(project="coolproject", branch=None),
                                                    # ...
                                                    )

else coolproject will be built when there's a change in superproject.

Since we're watching more than one branch, we need a method to tell in which branch the change occurred when we detect one.
This is what the ``split_file`` argument does, it takes a callable that Buildbot will call to do the job.
The split_file_branches function, which comes with Buildbot, is designed for exactly this purpose so that's what the example above uses.

And of course this is all SVN-specific, but there are pollers for all the popular VCSs.

But note: if you have many projects, branches, and builders it probably pays to not hardcode all the schedulers and builders in the configuration, but generate them dynamically starting from list of all projects, branches, targets etc. and using loops to generate all possible combinations (or only the needed ones, depending on the specific setup), as explained in the documentation chapter about :doc:`../manual/customization`.

Status targets
--------------

Now that the basics are in place, let's go back to the builders, which is where the real work happens.
`Status targets` are simply the means Buildbot uses to inform the world about what's happening, that is, how builders are doing.
There are many status targets: a web interface, a mail notifier, an IRC notifier, and others.
They are described fairly well in the manual.

One thing I've found useful is the ability to pass a domain name as the lookup argument to a ``mailNotifier``, which allows you to take an unqualified username as it appears in the SVN change and create a valid email address by appending the given domain name to it::

    from buildbot.plugins import status

    # if jsmith commits a change, mail for the build is sent to jsmith@example.org
    notifier = status.MailNotifier(fromaddr="buildbot@example.org",
                                   sendToInterestedUsers=True,
                                   lookup="example.org")
    c['status'].append(notifier)

The mail notifier can be customized at will by means of the ``messageFormatter`` argument, which is a function that Buildbot calls to format the body of the email, and to which it makes available lots of information about the build.
Here all the details.

Conclusion
----------

Please note that this article has just scratched the surface; given the complexity of the task of build automation, the possibilities are almost endless.
So there's much, much more to say about Buildbot. However, hopefully this is a preparation step before reading the official manual. Had I found an explanation as the one above when I was approaching Buildbot, I'd have had to read the manual just once, rather than multiple times. Hope this can help someone else.

(Thanks to Davide Brini for permission to include this tutorial, derived from one he originally posted at http://backreference.org .)
