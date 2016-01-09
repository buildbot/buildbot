# fake d3service for tests.
# d3Service is supposed to be provided by the main www/base app
# and is loading d3 asynchronously on demand
class D3 extends Service('bbData')
    constructor: ($q) ->
        d = $q.defer()

        # Resolve function
        d.resolve(window.d3)

        return get: -> d.promise
