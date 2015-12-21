beforeEach module 'app'

describe 'buildsticker controller', ->
    dataService = scope = $compile = results = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')
        results = $injector.get('RESULTS')
        dataService = $injector.get('dataService')

    beforeEach(inject(injected))

    it 'directive should generate correct html', ->
        build = buildid: 3, builderid: 2, number: 1
        dataService.when('builds/3', [build])
        dataService.when('builders/2', [{builderid: 2}])
        dataService.open(scope).getBuilds(build.buildid).then (builds) ->
            scope.build = builds[0]
        scope.$apply()
        element = $compile("<buildsticker build='build'></buildsticker>")(scope)
        scope.$apply()

        sticker = element.children().eq(0)

        row0 = sticker.children().eq(0)
        row1 = sticker.children().eq(1)

        resultSpan = row0.children().eq(0)
        buildLink = row0.children().eq(1)
        durationSpan = row1.children().eq(0)
        startedSpan = row1.children().eq(1)
        stateSpan = row1.children().eq(2)

        # the link of build should be correct
        expect(buildLink.attr('href')).toBe('#/builders/2/builds/1')

        # pending state
        scope.build.complete = false
        scope.build.started_at = Date.now()
        scope.build.results = -1
        scope.build.state_string = 'pending'
        scope.$apply()
        expect(resultSpan.hasClass('results_PENDING')).toBe(true)
        expect(resultSpan.text()).toBe('...')
        expect(durationSpan.hasClass('ng-hide')).toBe(true)
        expect(startedSpan.hasClass('ng-hide')).toBe(false)
        expect(stateSpan.text()).toBe('pending')

        # success state
        scope.build.complete = true
        scope.build.complete_at = scope.build.started_at + 1
        scope.build.results = results.SUCCESS
        scope.build.state_string = 'finished'
        scope.$apply()
        expect(resultSpan.hasClass('results_SUCCESS')).toBe(true)
        expect(resultSpan.text()).toBe('SUCCESS')
        expect(durationSpan.hasClass('ng-hide')).toBe(false)
        expect(startedSpan.hasClass('ng-hide')).toBe(true)
        expect(durationSpan.text()).toBe('1 s')
        expect(stateSpan.text()).toBe('finished')

        # failed state
        scope.build.complete = true
        scope.build.complete_at = scope.build.started_at + 1
        scope.build.results = results.FAILURE
        scope.build.state_string = 'failed'
        scope.$apply()
        expect(resultSpan.hasClass('results_FAILURE')).toBe(true)
        expect(resultSpan.text()).toBe('FAILURE')
        expect(durationSpan.hasClass('ng-hide')).toBe(false)
        expect(startedSpan.hasClass('ng-hide')).toBe(true)
        expect(durationSpan.text()).toBe('1 s')
        expect(stateSpan.text()).toBe('failed')
