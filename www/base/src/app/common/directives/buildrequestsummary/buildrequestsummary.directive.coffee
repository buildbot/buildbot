class Buildrequestsummary extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {buildrequestid: '=?'}
            templateUrl: 'views/buildrequestsummary.html'
            compile: RecursionHelper.compile
            controller: '_buildrequestsummaryController'
        }


class _buildrequestsummary extends Controller('common')
    constructor: ($scope, dataService, findBuilds, resultsService) ->
        _.mixin($scope, resultsService)
        $scope.$watch "buildrequest.claimed", (n, o) ->
            if n  # if it is unclaimed, then claimed, we need to try again
                findBuilds $scope,
                    $scope.buildrequest.buildrequestid

        data = dataService.open().closeOnDestroy($scope)
        data.getBuildrequests($scope.buildrequestid).onNew = (buildrequest) ->
            $scope.buildrequest = buildrequest
            data.getBuildsets(buildrequest.buildsetid).onNew = (buildset) ->
                $scope.buildset = buildset
            data.getBuilders(buildrequest.builderid).onNew = (builder) ->
                $scope.builder = builder
