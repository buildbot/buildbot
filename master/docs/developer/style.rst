Buildbot Coding Style
=====================

Symbol Names
------------

Buildbot follows `PEP8 <http://www.python.org/dev/peps/pep-0008/>`_ regarding the formatting of symbol names.
Because Buildbot uses Twisted so heavily, and Twisted uses interCaps, this is not very consistently applied throughout the codebase.

The single exception to PEP8 is in naming of functions and methods.
That is, you should spell methods and functions with the first character in lower-case, and the first letter of subsequent words capitalized, e.g., ``compareToOther`` or ``getChangesGreaterThan``.

Symbols used as parameters to functions used in configuration files should use underscores.

In summary, then:

====================== ============
Symbol Type            Format
====================== ============
Methods                interCaps
Functions              interCaps
Function Arguments     under_scores
API method Arguments   interCaps
Classes                InitialCaps
Variables              under_scores
Constants              ALL_CAPS
====================== ============

Twisted Idioms
--------------

Programming with Twisted Python can be daunting.  But sticking to a few
well-defined patterns can help avoid surprises.

Prefer to Return Deferreds
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're writing a method that doesn't currently block, but could conceivably
block sometime in the future, return a Deferred and document that it does so.
Just about anything might block - even getters and setters!

Helpful Twisted Classes
~~~~~~~~~~~~~~~~~~~~~~~

Twisted has some useful, but little-known classes.
Brief descriptions follow, but you should consult the API documentation or source code
for the full details.

:class:`twisted.internet.task.LoopingCall`
    Calls an asynchronous function repeatedly at set intervals.
    Note that this will stop looping if the function fails.
    In general, you will want to wrap the function to capture and log errors.

:class:`twisted.application.internet.TimerService`
    Similar to ``t.i.t.LoopingCall``, but implemented as a service that will automatically start and stop the function calls when the service starts and stops.
    See the warning about failing functions for ``t.i.t.LoopingCall``.

Sequences of Operations
~~~~~~~~~~~~~~~~~~~~~~~

Especially in Buildbot, we're often faced with executing a sequence of
operations, many of which may block.

In all cases where this occurs, there is a danger of pre-emption, so exercise
the same caution you would if writing a threaded application.

For simple cases, you can use nested callback functions. For more complex cases, inlineCallbacks is appropriate.
In all cases, please prefer maintainability and readability over performance.

Nested Callbacks
................

First, an admonition: do not create extra class methods that represent the continuations of the first::

    def myMethod(self):
        d = ...
        d.addCallback(self._myMethod_2) # BAD!
    def _myMethod_2(self, res):         # BAD!
        ...

Invariably, this extra method gets separated from its parent as the code
evolves, and the result is completely unreadable. Instead, include all of the
code for a particular function or method within the same indented block, using
nested functions::

    def getRevInfo(revname):
        results = {}
        d = defer.succeed(None)
        def rev_parse(_): # note use of '_' to quietly indicate an ignored parameter
            return utils.getProcessOutput(git, [ 'rev-parse', revname ])
        d.addCallback(rev_parse)
        def parse_rev_parse(res):
            results['rev'] = res.strip()
            return utils.getProcessOutput(git, [ 'log', '-1', '--format=%s%n%b', results['rev'] ])
        d.addCallback(parse_rev_parse)
        def parse_log(res):
            results['comments'] = res.strip()
        d.addCallback(parse_log)
        def set_results(_):
            return results
        d.addCallback(set_results)
        return d

it is usually best to make the first operation occur within a callback, as the
deferred machinery will then handle any exceptions as a failure in the outer
Deferred.  As a shortcut, ``d.addCallback`` works as a decorator::

    d = defer.succeed(None)
    @d.addCallback
    def rev_parse(_): # note use of '_' to quietly indicate an ignored parameter
        return utils.getProcessOutput(git, [ 'rev-parse', revname ])

Be careful with local variables. For example, if ``parse_rev_parse``, above,
merely assigned ``rev = res.strip()``, then that variable would be local to
``parse_rev_parse`` and not available in ``set_results``. Mutable variables
(dicts and lists) at the outer function level are appropriate for this purpose.

.. note:: do not try to build a loop in this style by chaining multiple
    Deferreds!  Unbounded chaining can result in stack overflows, at least on older
    versions of Twisted. Use ``inlineCallbacks`` instead.

In most of the cases if you need more than two callbacks in a method, it is more readable and maintainable to use inlineCallbacks.

inlineCallbacks
...............

:class:`twisted.internet.defer.inlineCallbacks` is a great help to writing code
that makes a lot of asynchronous calls, particularly if those calls are made in
loop or conditionals.  Refer to the Twisted documentation for the details, but
the style within Buildbot is as follows::

    from twisted.internet import defer

    @defer.inlineCallbacks
    def mymethod(self, x, y):
        xval = yield getSomething(x)

        for z in (yield getZValues()):
            y += z

        if xval > 10:
            defer.returnValue(xval + y)
            return

        self.someOtherMethod()

The key points to notice here:

* Always import ``defer`` as a module, not the names within it.
* Use the decorator form of ``inlineCallbacks``.
* In most cases, the result of a ``yield`` expression should be assigned to a
  variable.  It can be used in a larger expression, but remember that Python
  requires that you enclose the expression in its own set of parentheses.
* Python does not permit returning a value from a generator, so statements like
  ``return xval + y`` are invalid.  Instead, yield the result of
  ``defer.returnValue``.  Although this function does cause an immediate
  function exit, for clarity follow it with a bare ``return``, as in
  the example, unless it is the last statement in a function.

The great advantage of ``inlineCallbacks`` is that it allows you to use all
of the usual Pythonic control structures in their natural form. In particular,
it is easy to represent a loop, or even nested loops, in this style without
losing any readability.

Note that code using ``deferredGenerator`` is no longer acceptable in Buildbot.

Locking
.......

Remember that asynchronous programming does not free you from the need to worry
about concurrency issues.  Particularly if you are executing a sequence of
operations, each time you wait for a Deferred, arbitrary other actions can take
place.

In general, you should try to perform actions atomically, but for the rare
situations that require synchronization, the following might be useful:

* :py:class:`twisted.internet.defer.DeferredLock`
* :py:func:`buildbot.util.misc.deferredLocked`
* :py:func:`buildbot.util.misc.SerializedInvocation`

Joining Sequences
~~~~~~~~~~~~~~~~~

It's often the case that you'll want to perform multiple operations in
parallel, and re-join the results at the end. For this purpose, you'll want to
use a `DeferredList <http://twistedmatrix.com/documents/current/api/twisted.internet.defer.DeferredList.html>`_
::

    def getRevInfo(revname):
        results = {}
        finished = dict(rev_parse=False, log=False)

        rev_parse_d = utils.getProcessOutput(git, [ 'rev-parse', revname ])
        def parse_rev_parse(res):
            return res.strip()
        rev_parse_d.addCallback(parse_rev_parse)

        log_d = utils.getProcessOutput(git, [ 'log', '-1', '--format=%s%n%b', results['rev'] ])
        def parse_log(res):
            return res.strip()
        log_d.addCallback(parse_log)

        d = defer.DeferredList([rev_parse_d, log_d], consumeErrors=1, fireOnFirstErrback=1)
        def handle_results(results):
            return dict(rev=results[0][1], log=results[1][1])
        d.addCallback(handle_results)
        return d

Here the deferred list will wait for both ``rev_parse_d`` and ``log_d`` to
fire, or for one of them to fail. You may attach callbacks and errbacks to a
``DeferredList`` just as for a deferred.


CoffeeScript Coding Style
=========================

Buildbot development team is primarily python experts and not front-end experts. We however spent lot of time looking for front end best practices. We are very likely to accept suggestions to this coding-style and best-practices guide.

Here is a summary of what is the expected coding style for buildbot contributions, as long some common gotcha's for python backgrounded developers.

CoffeeScript looks like python
------------------------------

Buildbot follows Python pep8 coding style as much as possible, except for naming convention (where twisted's interCaps are preferred). The same rules has to be applied for coffeeScript, whenever it makes sense.

Buildbot python naming convention is used for CoffeeScript:

================== ============
Symbol Type        Format
================== ============
Methods            interCaps
Functions          interCaps
Function Arguments interCaps
Classes            InitialCaps
Controllers        interCaps
Services           interCaps
Filters            interCaps
Constants          ALL_CAPS
================== ============

Coffeelint should be happy
--------------------------

Buildbot ships with a Gruntfile containing coffeelint configuration which is expected to pass for buildbot coffeescript code.

CoffeeScript syntax sugar
-------------------------

CoffeeScript does not have inlineCallbacks, but have some syntax sugar for helping readability of nested callbacks. However, those syntax sugars sometimes leads to surprises. Make sure you check the generated javascript in case of weird behavior.

* Use implicit parenthesis for multi line function calls or object construction:

.. code-block:: coffeescript

    d.then (res) ->
       $scope.val = res

    d.then((res) ->  # BAD
       $scope.val = res
    )  # BAD

.. code-block:: coffeescript

    # push a dictionary into a list
    l.push
        k1: v1
        k2: v2

    # push a dictionary into a list
    l.push(  # BAD
        k1: v1
        k2: v2
    )  # BAD

    # push a dictionary into a list
    l.push({  # BAD
        k1: v1
        k2: v2
    })  # BAD

* Use explicit parenthesis for single line function calls

.. code-block:: coffeescript

    myFunc(service.getA(b))  # correct

    myFunc service.getA b
    # BAD: not enough visually-distinct from:
    myFunc service.getA, b
    # which means
    myFunc(service.getA, b)

* always use return for multiline functions

  Coffeescript "everything is an expression", and default return value is the result of the last expression
  is considered too error prone for python and js developers which are used to "return None" by default
  in buildbot code, every multiline function must end with an explicit return statement

.. code-block:: coffeescript

    myFunc = ->
        if (a)
            b()
        # BAD: implicitly returns the return value of b()

    myFunc = ->
        if (a)
            b()
        return null  # correct

    myFunc = ->
        if (a)
            return b()  # correct
        return null  # correct

* never use return for single line functions

    single line functions is equivalent to python lambda functions and thus must not use return

.. code-block:: coffeescript

    # if p resolves with a non-null list, will return the list with all element incremented
    p = p.then( (res) -> _.each(res, (a) -> a + 1))

CoffeeScript does not include batteries
---------------------------------------

There is a very limited standard library in JS, and none in CS. However defacto general purpose libraries have emerged.

* JQuery considered harmful to access the dom directly.

    Buildbot ships with JQuery, because it is supposed to be more optimized than AngularJS's own jqlite, and because some 3rd party directives are requiring it.
    However it must not be used in buildbot services or controllers, and should be avoided in directives.
    Buildbot UI should follow angularJS best practices and only modify DOM via templates.

* lodash is a clone of underscore js, and provides good utilities for standard types manipulation (array and objects), underscore-string is also available for string manipulation function (e.g. startsWith, endsWith )

* Avoid to use lodash decoration form

    Those are considered tricky to use.

.. code-block:: coffeescript

    _.each(res, (a) -> a + 1)) # good
    _(res).each((a) -> a + 1)) # to be avoided

* requirejs is used as technical solution for plugin loading. It should not be used appart from this.

* momentjs is used for manipulating dates and displaying them to the user in a human readable form (e.g "one month ago")

$q "A+ promises" VS twisted's deferred
--------------------------------------

AngularJS $q module implements A+ promises. At first sight, this looks like twisted deferreds.

.. warning:: d.addCallbacks(successCb, errorCb) is not equivalent with p.then(successCb, errorCb)!

* Once a Twisted deferred has been "called", its result is changed with the return value of each callback in the callback queue.

* Once a $q promise has been "resolved", its result is immutable.
  p.then() itself returns another promise which can be used to alter result of another promise

::

    d = someFunction()
    @d.addCallback
    def addOneToResult(res):
        return res + 1
    return d # we return the same deferred as the one returned by someFunction()

Translate in coffeeScript to:

.. code-block:: coffeescript

    p = someFunction()
    p = p.then (res) ->
        return res + 1
    return d # we return the another promise as the one returned by someFunction()

* With $q, only the promise creator can resolve it.

.. code-block:: coffeescript

    someFunction = ->
        d = $q.defer()
        $timeout ->
                d.resolve("foo")
            , 100
        return d.promise
    p = someFunction()
    p.resolve() # cannot work, we can only can "then" method of a promise