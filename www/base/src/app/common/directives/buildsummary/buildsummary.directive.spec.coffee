beforeEach module 'app'

describe 'buildsummary controller', ->
    dataService = scope = $rootScope = $compile = null
    $timeout = createController = $stateParams = results = baseurl = null
    goneto  = null

    injected = ($injector) ->
        results = $injector.get('RESULTS')
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        scope.buildid = 1
        scope.condensed = 0

        $timeout = $injector.get('$timeout')
        $stateParams = $injector.get('$stateParams')
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')
        $compile = $injector.get('$compile')
        $location = $injector.get('$location')
        baseurl = $location.absUrl().split("#")[0]

        dataService = $injector.get('dataService')
        dataService.when('builds/1', [{buildid: 1, builderid: 1}])
        dataService.when('builders/1', [{builderid: 1}])
        dataService.when('builds/1/steps', [{builderid: 1, stepid: 1, number: 1}])
        dataService.when('steps/1/logs', [{stepid: 1, logid: 1}, {stepid: 1, logid: 2}])

    beforeEach(inject(injected))

    it 'should provide correct isStepDisplayed when condensed', ->
        scope.condensed = true
        element = $compile("<buildsummary buildid='buildid' condensed='condensed'></buildsummary>")(scope)
        scope.$apply()
        buildsummary = element.isolateScope().buildsummary
        expect(buildsummary.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.WARNING)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.FAILURE)).toBe(false)
        buildsummary.toggleDetails()
        expect(buildsummary.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect(buildsummary.isStepDisplayed(results:results.FAILURE)).toBe(true)
        buildsummary.toggleDetails()
        expect(buildsummary.isStepDisplayed(results:results.SUCCESS)).toBe(true)
        expect(buildsummary.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect(buildsummary.isStepDisplayed(results:results.FAILURE)).toBe(true)
        buildsummary.toggleDetails()
        expect(buildsummary.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.WARNING)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.FAILURE)).toBe(false)

    it 'should provide correct isStepDisplayed when not condensed', ->
        scope.condensed = 0
        element = $compile("<buildsummary buildid='buildid' condensed='condensed'></buildsummary>")(scope)
        scope.$apply()
        buildsummary = element.isolateScope().buildsummary
        expect(buildsummary.isStepDisplayed(results:results.SUCCESS)).toBe(true)
        expect(buildsummary.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect(buildsummary.isStepDisplayed(results:results.FAILURE)).toBe(true)
        buildsummary.toggleDetails()
        expect(buildsummary.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.WARNING)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.FAILURE)).toBe(false)
        buildsummary.toggleDetails()
        expect(buildsummary.isStepDisplayed(results:results.SUCCESS)).toBe(false)
        expect(buildsummary.isStepDisplayed(results:results.WARNING)).toBe(true)
        expect(buildsummary.isStepDisplayed(results:results.FAILURE)).toBe(true)
        buildsummary.toggleDetails()

    it 'should provide correct getBuildRequestIDFromURL', ->
        element = $compile("<buildsummary buildid='buildid'></buildsummary>")(scope)
        scope.$apply()
        buildsummary = element.isolateScope().buildsummary
        expect(buildsummary.getBuildRequestIDFromURL("#{baseurl}#buildrequests/123"))
        .toBe(123)

    it 'should provide correct isBuildRequestURL', ->
        element = $compile("<buildsummary buildid='buildid'></buildsummary>")(scope)
        scope.$apply()
        buildsummary = element.isolateScope().buildsummary
        expect(buildsummary.isBuildRequestURL("#{baseurl}#buildrequests/123"))
        .toBe(true)
        expect(buildsummary.isBuildRequestURL("http://otherdomain:5000/#buildrequests/123"))
        .toBe(false)
        expect(buildsummary.isBuildRequestURL("#{baseurl}#builds/123"))
        .toBe(false)
        expect(buildsummary.isBuildRequestURL("#{baseurl}#buildrequests/bla"))
        .toBe(false)

    it 'should provide correct isBuildURL', ->
        element = $compile("<buildsummary buildid='buildid'></buildsummary>")(scope)
        scope.$apply()
        buildsummary = element.isolateScope().buildsummary
        expect(buildsummary.isBuildURL("#{baseurl}#builders/123/builds/123"))
        .toBe(true)
        expect(buildsummary.isBuildURL("#{baseurl}#builders/sdf/builds/123"))
        .toBe(false)
