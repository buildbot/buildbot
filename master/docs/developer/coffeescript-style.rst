CoffeeScript Coding Style
=========================

The Buildbot development team is primarily Python experts and not front-end experts.
Whlie we did spend lot of time looking for front end best practices, we are happy to accept suggestions to this coding-style and best-practices guide.

Here is a summary of what is the expected coding style for buildbot contributions, as well as some common gotcha's for developers with a Python background.

CoffeeScript looks like Python
------------------------------

Buildbot follows Python pep8 coding style as much as possible, except for naming convention (where twisted's interCaps are preferred).
The same rules apply for CoffeeScript, whenever they makes sense:

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

Buildbot ships with a Gruntfile containing a coffeelint configuration which is expected to pass for buildbot CoffeeScript code.

CoffeeScript syntax sugar
-------------------------

CoffeeScript does not have inlineCallbacks, but have some syntax sugar for helping readability of nested callbacks.
However, those syntax sugars sometimes leads to surprises.
Make sure you check the generated javascript in case of weird behavior.

Follow the following suggestions:

* Use implicit parentheses for multi line function calls or object construction:

.. code-block:: coffeescript

    # GOOD
    d.then (res) ->
       $scope.val = res

    # BAD
    d.then((res) ->
       $scope.val = res
    )

.. code-block:: coffeescript

    # push a dictionary into a list
    # GOOD
    l.push
        k1: v1
        k2: v2

    # BAD
    l.push(
        k1: v1
        k2: v2
    )

    # BAD
    l.push({
        k1: v1
        k2: v2
    })

* Use explicit parentheses for single line function calls

.. code-block:: coffeescript

    # GOOD
    myFunc(service.getA(b))

    # BAD
    myFunc service.getA b
    # (not enough visually-distinct from:)
    myFunc service.getA, b
    # which means
    myFunc(service.getA, b)

* always use ``return`` for multiline functions

  In CoffeeScript, "everything is an expression", and the default return value is the result of the last expression.
  This is considered too error prone for Python and JS developers who are used to "return None" by default.
  In buildbot code, every multiline function must end with an explicit ``return`` statement.

.. code-block:: coffeescript

    # BAD: implicitly returns the return value of b()
    myFunc = ->
        if (a)
            b()

    # GOOD
    myFunc = ->
        if (a)
            b()
        return null

    # GOOD
    myFunc = ->
        if (a)
            return b()
        return null

* never use return for single line functions

    Single line functions is equivalent to Python ``lambda`` functions and thus must not use ``return``.

.. code-block:: coffeescript

    # GOOD
    # if p resolves with a non-null list, will return the list with all element incremented
    p = p.then( (res) -> _.each(res, (a) -> a + 1))

CoffeeScript does not include batteries
---------------------------------------

There is a very limited standard library in JS, and none in CoffeeScript.
However, de-facto general purpose libraries have emerged.

* JQuery considered harmful to access the DOM directly.

    Buildbot ships with JQuery, because it is supposed to be more optimized than AngularJS's own jqlite, and because some 3rd party directives are requiring it.
    However, it must not be used in Buildbot services or controllers, and should be avoided in directives.
    The Buildbot UI should follow AngularJS best practices and only modify DOM via templates.

* Lodash is a clone of Underscore.js, and provides good utilities for standard types manipulation (array and objects).
  Underscore-string is also available for string manipulation function (e.g. startsWith, endsWith )

  Avoid using lodash decoration form.
  Those are considered tricky to use.

.. code-block:: coffeescript

    # GOOD
    _.each(res, (a) -> a + 1))

    # BAD
    _(res).each((a) -> a + 1))

* Require.js is used as technical solution for plugin loading.
  It should not be used apart from this.

* Moment.js is used for manipulating dates and displaying them to the user in a human readable form (e.g "one month ago").
  It can be used anywhere it is useful.

$q "A+ promises" VS twisted's deferred
--------------------------------------

The AngularJS ``$q`` module implements A+ promises.
At first sight, this looks like Twisted Deferreds.

.. warning:: d.addCallbacks(successCb, errorCb) is not equivalent to p.then(successCb, errorCb)!

* Once a Twisted deferred has been "called", its result is changed with the return value of each callback in the callback queue.

* Once a $q promise has been "resolved", its result is immutable.
  p.then() itself returns another promise which can be used to alter result of another promise.

::

    d = someFunction()
    @d.addCallback
    def addOneToResult(res):
        return res + 1
    return d # we return the same deferred as the one returned by someFunction()

Translate in coffeeScript to:

.. code-block:: coffeescript

    p = someFunction()
    p = p.then (res) ->  ## note assignment
        return res + 1
    return p  # we return the another promise as the one returned by someFunction()

* With ``$q``, only the promise creator can resolve it.

.. code-block:: coffeescript

    someFunction = ->
        d = $q.defer()
        $timeout ->
                d.resolve("foo")
            , 100
        return d.promise
    p = someFunction()
    p.resolve() # cannot work, we can only call the "then" method of a promise

