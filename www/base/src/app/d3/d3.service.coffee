# Load d3 script via jquery
# We load those 50kB+ only when needed by plugins
# actually, this is loaded when someone is requiring DI of this service
class D3 extends Service
    constructor: ($document, $q, config, $rootScope) ->
        d = $q.defer()

        # Resolve function
        $.getScript 'd3.min.js', ->
            $rootScope.$apply ->
                d.resolve(window.d3)

        return get: -> d.promise
