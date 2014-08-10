class Buildrequestsummary extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {buildrequestid: '='}
            templateUrl: 'views/buildrequestsummary.html'
            compile: RecursionHelper.compile
            controller: '_buildrequestsummaryController'
        }

class _buildrequestsummary extends Controller('common')
    constructor: ($scope, buildbotService, findBuilds) ->
        $scope.$watch "buildrequest.claimed", (n, o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                    $scope.buildrequest.buildrequestid

        buildbotService.one('buildrequests', $scope.buildrequestid).bind($scope)
