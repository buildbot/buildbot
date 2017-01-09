class Buildsummary extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            replace: true
            restrict: 'E'
            scope: {}
            bindToController: {buildid: '=?', build: '=?', condensed: '=?', parentbuild: '=?', parentrelationship: '=?'}
            templateUrl: 'views/buildsummary.html'
            compile: RecursionHelper.compile
            controller: '_buildsummaryController'
            controllerAs: 'buildsummary'
        }

class _buildsummary extends Controller('common')
    constructor: ($scope, dataService, resultsService, buildersService, $urlMatcherFactory, $location, $interval, RESULTS) ->
        self = this
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        baseurl = $location.absUrl().split("#")[0]
        buildrequestURLMatcher = $urlMatcherFactory.compile(
            "#{baseurl}#buildrequests/{buildrequestid:[0-9]+}")
        buildURLMatcher = $urlMatcherFactory.compile(
            "#{baseurl}#builders/{builderid:[0-9]+}/builds/{buildid:[0-9]+}")
        # to get an update of the current builds every seconds, we need to update self.now
        # but we want to stop counting when the scope destroys!
        stop = $interval =>
            @now = moment().unix()
        , 1000
        $scope.$on("$destroy", -> $interval.cancel(stop))

        NONE = 0
        ONLY_NOT_SUCCESS = 1
        EVERYTHING = 2
        details = EVERYTHING
        if @condensed
            details = NONE
        @toggleDetails = ->
            details = (details + 1) % 3

        @levelOfDetails = ->
            switch details
                when NONE
                    "None"
                when ONLY_NOT_SUCCESS
                    "Problems"
                when EVERYTHING
                    "All"

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

        @getBuildProperty = (property) ->
            hasProperty = self.properties && self.properties.hasOwnProperty(property)
            return  if hasProperty then self.properties[property][0] else null

        @toggleFullDisplay = ->
            @fulldisplay = !@fulldisplay
            if @fullDisplay
                details = EVERYTHING
            for step in @steps
                step.fulldisplay = @fulldisplay

        data = dataService.open().closeOnDestroy($scope)
        $scope.$watch (=> @buildid), (buildid) ->
            if not buildid? then return
            data.getBuilds(buildid).onNew = (build) ->
                self.build = build

        $scope.$watch (=> @build), (build) ->
            if not build? then return
            if @builder then return
            self.builder = buildersService.getBuilder(build.builderid)

            build.getProperties().onNew = (properties) ->
                self.properties = properties
                self.reason = self.getBuildProperty('reason')

            $scope.$watch (-> details), (details) ->
                if details != NONE and not self.steps?
                    self.steps = build.getSteps()

                    self.steps.onNew = (step) ->
                        step.logs = step.getLogs()
                        # onUpdate is only called onUpdate, not onNew
                        # but we need to update our additional needed attributes
                        self.steps.onUpdate(step)

                    self.steps.onUpdate = (step) ->
                        step.fulldisplay = step.complete == false || step.results > 0
                        if step.complete
                            step.duration = step.complete_at - step.started_at
        $scope.$watch (=> @parentbuild), (build,o) ->
            if not build? then return
            self.parentbuilder = buildersService.getBuilder(build.builderid)
