Release Notes for Buildbot |version|
====================================

..
    Any change that adds a feature or fixes a bug should have an entry here.
    Most simply need an additional bulleted list item, but more significant
    changes can be given a subsection of their own.

The following are the release notes for Buildbot 0.9.1
Buildbot 0.9.1 was released on the ...

Master
------

Features
~~~~~~~~


Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Changes for Developers
~~~~~~~~~~~~~~~~~~~~~~


Slave
-----

Features
~~~~~~~~

* Schedulers: the ``codebases`` parameter can now be specified in a simple list-of-strings form.

Fixes
~~~~~

Deprecations, Removals, and Non-Compatible Changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Providing Latent AWS EC2 credentails by the .ec2/aws_id file is deprecated:
  Instead, use the standard .aws/credentials file.

Details
-------

For a more detailed description of the changes made in this version, see the git log itself:

.. code-block:: bash

   git log v0.8.10..master

Older Versions
--------------

Release notes for older versions of Buildbot are available in the :src:`master/docs/relnotes/` directory of the source tree.
Newer versions are also available here:

.. toctree::
    :maxdepth: 1

    0.9.0b1
    0.8.10
    0.8.9
    0.8.8
    0.8.7
    0.8.6
