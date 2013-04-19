angular.module('app').factory 'buildbotService',
['$log', '$resource',
    ($log, $resource) ->
        # populateScope populate $scope[scope_key] with an api_query use
        # sse_query and EventSource to update automatically the table

        # @todo the implementation is very naive for now.  Need to sort out
        # server side paging/sorting (do we really need serverside sorting?)

        populateScope = ($scope,  scope_key, api_query, sse_query) ->
                $scope[scope_key] = $resource("api/v2/"+api_query).query()
                source = new EventSource("sse/"+sse_query)
                source.addEventListener "event", (e) ->
                  $scope[scope_key].push msg
                  $scope.$apply()
        {populateScope}
]
