class Buildsummary extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {buildid: '=', condensed: '='}
            templateUrl: 'views/buildsummary.html'
            compile: RecursionHelper.compile
            controller: '_buildsummaryController'
        }

class _buildsummary extends Controller('common')
    constructor: ($scope, buildbotService, config, resultsService, $urlMatcherFactory) ->

        buildrequestURLMatcher = $urlMatcherFactory.compile(
            "#{config.url}#buildrequests/{buildrequestid:[0-9]+}")
        buildURLMatcher = $urlMatcherFactory.compile(
            "#{config.url}#builders/{builderid:[0-9]+}/builds/{buildid:[0-9]+}")

        NONE = 0
        ONLY_NOT_SUCCESS = 1
        EVERYTHING = 2
        details = EVERYTHING
        if $scope.condensed
            details = NONE

        $scope.$watch (-> moment().unix()), ->
            $scope.now = moment().unix()

        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        $scope.toggleDetails = ->
            details = (details + 1 ) % 3

        $scope.isStepDisplayed = (step) ->
            if details == EVERYTHING
                return !step.hidden
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


        $scope.$watch 'buildid', (buildid) ->
            $scope.buldid = buildid

            buildbotService.one('builds', $scope.buildid)
            .bind($scope).then (build) ->
                buildbotService.one('builders', build.builderid).bind($scope)
                build.all('steps').bind $scope,
                    onchild: (step) ->
                        $scope.$watch (-> step.complete), ->
                            step.fulldisplay = step.complete == 0 || step.results > 0
                            if step.complete
                                step.duration = step.complete_at - step.started_at
                        logs = buildbotService.one("steps", step.stepid).all("logs")
                        logs.bind $scope,
                            dest: step
