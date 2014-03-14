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
['$scope', 'buildbotService', 'resultsTexts', 'config', 'resultsService'
    ($scope, buildbotService, resultsTexts, config, resultsService) ->

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
            url = url.split("/")
            return parseInt(url[url.length - 1], 10)

        $scope.isBuildRequestURL = (url) ->
            baseurl =  "#{config.url}#buildrequests/"
            if not _.startsWith(url, baseurl)
                return false
            remain = url.substr(baseurl.length)
            return not isNaN(parseInt(remain, 10))


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
