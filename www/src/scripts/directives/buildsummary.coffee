angular.module('app').directive 'buildsummary',
['$log', 'RecursionHelper',
    ($log, RecursionHelper) ->
        replace: true
        restrict: 'E'
        scope: {buildid:'=', condensed:'='}
        templateUrl: 'views/directives/buildsummary.html'
        compile: RecursionHelper.compile
        controller: 'buildsummaryController'
]

angular.module('app').controller 'buildsummaryController',
['$scope', 'buildbotService', 'resultsTexts', 'config', 'resultsService', '$urlMatcherFactory'
    ($scope, buildbotService, resultsTexts, config, resultsService, $urlMatcherFactory) ->

        buildrequestURLMatcher = $urlMatcherFactory.compile(
            "#{config.url}#buildrequests/{buildrequestid:[0-9]+}")
        buildURLMatcher = $urlMatcherFactory.compile(
            "#{config.url}#builders/{builderid}/builds/{buildid:[0-9]+}")

        NONE = 0
        ONLY_NOT_SUCCESS = 1
        EVERYTHING = 2
        details = EVERYTHING
        if $scope.condensed
            details = NONE

        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        $scope.toggleDetails = ->
            details = (details + 1 ) % 3

        $scope.isStepDisplayed = (step) ->
            if details == EVERYTHING
                return true
            else if details == ONLY_NOT_SUCCESS
                return not step.results? or step.results != 0
            else if details == NONE
                return false

        $scope.getBuildRequestIDFromURL = (url) ->
            return parseInt(buildrequestURLMatcher.exec(url).buildrequestid, 10)

        $scope.isBuildRequestURL = (url) ->
            return buildrequestURLMatcher.exec(url) != null

        $scope.isBuildURL = (url) ->
            return buildURLMatcher.exec(url) != null


        buildbotService.one('builds', $scope.buildid)
        .bind($scope).then (build) ->
            buildbotService.one('builders', build.builderid).bind($scope)
            build.all('steps').bind $scope,
                onchild: (step) ->
                    $scope.$watch (-> step.complete), ->
                        step.fulldisplay = step.complete == 0 || step.results > 0
                    logs = buildbotService.one("steps", step.stepid).all("logs")
                    logs.bind $scope,
                        dest: step,
]
