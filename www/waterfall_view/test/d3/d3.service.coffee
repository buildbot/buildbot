class D3 extends Service('common')
    constructor: ($q) ->
        d = $q.defer()

        # Resolve function
        d.resolve(window.d3)

        return get: -> d.promise