# Load d3 script using RequireJS if available
# appending script tag otherwise
angular.module('buildbot.waterfall_view').factory 'd3Service',
    [ '$document', '$q', '$rootScope', class
        constructor: ($document, $q, $rootScope) ->
            d = $q.defer()

            # Resolve function
            resolve = (e) ->
                $rootScope.$apply ->
                    d.resolve(e)

            if define? and angular.isFunction(define) and define.amd
                # Load d3 script and
                # resolve the promise
                # when it has been loaded
                # TODO both dev and prod mode includes RequireJS library, but d3 can be find in different js files
                require ['//d3js.org/d3.v3.min.js'], (d3) ->
                    resolve(d3)
            else
                # Create script tag and
                # resolve the promise
                # when it has been loaded
                tag = $document[0].createElement('script')
                tag.type = 'text/javascript'
                tag.async = true
                tag.src = '//d3js.org/d3.v3.min.js'
                tag.onreadystatechange = ->
                    if @readyState == 'complete'
                        resolve(window.d3)
                tag.onload = -> resolve(window.d3)

                body = $document[0].getElementsByTagName('body')[0]
                body.appendChild(tag)

            return get: -> d.promise
    ]