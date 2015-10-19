class D3 extends Service('bbData')
    constructor: ($q) ->
        d = $q.defer()

        # Resolve function
        d.resolve(window.d3)

        return get: -> d.promise
