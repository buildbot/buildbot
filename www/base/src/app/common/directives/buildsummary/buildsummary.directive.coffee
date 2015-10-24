class Buildsummary extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {}
            bindToController: {buildid: '=', condensed: '=', prefix: "@"}
            templateUrl: 'views/buildsummary.html'
            compile: RecursionHelper.compile
            controller: '_buildsummaryController'
            controllerAs: 'buildsummary'
        }

class _buildsummary extends Controller('common')
    constructor: ($scope, dataService, resultsService, $urlMatcherFactory, $location, $interval, RESULTS) ->
        self = @
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        baseurl = $location.absUrl().split("#")[0]
        buildrequestURLMatcher = $urlMatcherFactory.compile(
            "#{baseurl}#buildrequests/{buildrequestid:[0-9]+}")
        buildURLMatcher = $urlMatcherFactory.compile(
            "#{baseurl}#builders/{builderid:[0-9]+}/builds/{buildid:[0-9]+}")

        $interval =>
            @now = moment().unix()
        , 1000

        NONE = 0
        ONLY_NOT_SUCCESS = 1
        EVERYTHING = 2
        details = EVERYTHING
        if @condensed
            details = NONE
        @toggleDetails = ->
            details = (details + 1) % 3

        @isStepDisplayed = (step) ->
            if details == EVERYTHING
                !step.hidden
            else if details == ONLY_NOT_SUCCESS
                not step.results? or step.results != RESULTS.SUCCESS
            else if details == NONE
                false

        @getBuildRequestIDFromURL = (url) ->
            return parseInt(buildrequestURLMatcher.exec(url).buildrequestid, 10)

        @isBuildRequestURL = (url) ->
            return buildrequestURLMatcher.exec(url) != null

        @isBuildURL = (url) ->
            return buildURLMatcher.exec(url) != null

        data = dataService.open($scope)
        $scope.$watch (=> @buildid), (buildid) ->
            if not buildid? then return
            data.getBuilds(buildid).then (builds) ->
                self.build = build = builds[0]
                data.getBuilders(build.builderid).then (builders) ->
                    self.builder = builder = builders[0]

                build.getSteps().then (steps) ->
                    self.steps = steps
                    steps.forEach (step) ->
                        $scope.$watch (-> step.complete), ->
                            step.fulldisplay = step.complete == 0 || step.results > 0
                            if step.complete
                                step.duration = step.complete_at - step.started_at
                        step.loadLogs()
