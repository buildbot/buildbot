# Load d3 script via jquery
# We load those 50kB+ only when needed by plugins
# actually, this is loaded when someone is requiring DI of this service
angular.module('buildbot.common').factory 'd3Service',
    ($document, $q, config, $rootScope) ->
        d = $q.defer()

        # Resolve function
        $.getScript config.url + 'd3.min.js', ->
            $rootScope.$apply ->
                d.resolve(window.d3)

        return get: -> d.promise
