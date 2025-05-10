Programmatic Configuration Generation
-------------------------------------

Bearing in mind that ``master.cfg`` is a Python file, large configurations can be shortened
considerably by judicious use of Python loops. For example, the following will generate a builder
for each of a range of supported versions of Python:

.. code-block:: python

    pythons = ['python2.4', 'python2.5', 'python2.6', 'python2.7',
               'python3.2', 'python3.3']
    pytest_workers = ["worker%s" % n for n in range(10)]
    for python in pythons:
        f = util.BuildFactory()
        f.addStep(steps.SVN(...))
        f.addStep(steps.ShellCommand(command=[python, 'test.py']))
        c['builders'].append(util.BuilderConfig(
                name="test-%s" % python,
                factory=f,
                workernames=pytest_workers))

Next step would be the loading of ``pythons`` list from a .yaml/.ini file.
