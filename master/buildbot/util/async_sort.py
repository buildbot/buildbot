# Copyright Buildbot Team Members
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


from twisted.internet import defer


@defer.inlineCallbacks
def async_sort(l, key, max_parallel=10):
    """perform an asynchronous sort with parallel run of the key algorithm"""

    sem = defer.DeferredSemaphore(max_parallel)
    try:
        keys = yield defer.gatherResults([sem.run(key, i) for i in l])
    except defer.FirstError as e:
        raise e.subFailure.value

    # Index the keys by the id of the original item in list
    keys = {id(l[i]): v for i, v in enumerate(keys)}

    # now we can sort the list in place
    l.sort(key=lambda x: keys[id(x)])
