beforeEach ->
    module ($provide) ->
        $provide.service '$modal', -> open: ->
        null

    # Mock bbSettingsProvider
    module ($provide) ->
        $provide.provider 'bbSettingsService', class
            group = {}
            addSettingsGroup: (g) -> g.items.map (i) ->
                if i.name is 'lazy_limit_waterfall'
                    i.default_value = 2
                group[i.name] = value: i.default_value
            $get: ->
                getSettingsGroup: ->
                    return group
                save: ->
        null

    module 'waterfall_view'

describe 'Waterfall view controller', ->
    $rootScope = $state = elem = w = $document = $window = $modal = $timeout =
        bbSettingsService = dataService = null

    builders = [
        builderid: 1
        name: 'builder1'
    ,
        builderid: 2
        name: 'builder2'
    ,
        builderid: 3
        name: 'builder3'
    ,
        builderid: 4
        name: 'builder4'
    ]

    builds = [
        buildid: 1
        builderid: 1
        started_at: 1403059709
        complete_at: 1403059772
        complete: true
        results: 'success'
    ,
        buildid: 2
        builderid: 2
        buildrequestid: 1
        started_at: 1403059802
        complete_at: 1403060287
        complete: true
        results: 'success'
    ,
        buildid: 3
        builderid: 2
        buildrequestid: 2
        started_at: 1403059710
        complete_at: 1403060278
        complete: true
        results: 'failure'
    ,
        buildid: 4
        builderid: 3
        buildrequestid: 2
        started_at: 1403060250
        complete_at: 0
        complete: false
    ]

    buildrequests = [
        builderid: 1
        buildrequestid: 1
        buildsetid: 1
    ,
        builderid: 1
        buildrequestid: 2
        buildsetid: 1
    ,
        builderid: 1
        buildrequestid: 3
        buildsetid: 2
    ]

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        scope = $rootScope.$new()
        $compile = $injector.get('$compile')
        $controller = $injector.get('$controller')
        $state = $injector.get('$state')
        $document = $injector.get('$document')
        $window = $injector.get('$window')
        $modal = $injector.get('$modal')
        $timeout = $injector.get('$timeout')
        bbSettingsService = $injector.get('bbSettingsService')
        dataService = $injector.get('dataService')

        dataService.when('builds', {limit: 2}, builds[...2])
        dataService.when('builders', builders)
        dataService.when('buildrequests', buildrequests)
        dataService.when('builds/1/steps', [{buildid: 1}])

        elem = $compile('<div><ui-view></ui-view></div>')(scope)
        $document.find('body').append(elem)

        $state.transitionTo('waterfall')
        $rootScope.$digest()
        elem = elem.children()
        waterfall = elem.children()
        scope = waterfall.scope()
        w = waterfall.controller()
        spyOn(w, 'mouseOver').and.callThrough()
        spyOn(w, 'mouseOut').and.callThrough()
        spyOn(w, 'mouseMove').and.callThrough()
        spyOn(w, 'click').and.callThrough()
        spyOn(w, 'loadMore').and.callThrough()
        # Data is loaded
        $timeout.flush()

    beforeEach(inject(injected))

    # make sure we remove the element from the dom
    afterEach ->
        expect($document.find('svg').length).toEqual(2)
        elem.remove()
        expect($document.find('svg').length).toEqual(0)

    it 'should be defined', ->
        expect(w).toBeDefined()

    it 'should bind the builds and builders to scope', ->
        group = bbSettingsService.getSettingsGroup()
        limit = group.lazy_limit_waterfall.value
        expect(w.builds).toBeDefined()
        expect(w.builds.length).toBe(limit)
        expect(w.builders).toBeDefined()
        expect(w.builders.length).not.toBe(0)

    it 'should create svg elements', ->
        expect(elem.find('svg').length).toBeGreaterThan(1)
        expect(elem.find('g').length).toBeGreaterThan(1)

    it 'should rerender the waterfall on resize', ->
        spyOn(w, 'render').and.callThrough()
        expect(w.render).not.toHaveBeenCalled()
        angular.element($window).triggerHandler('resize')
        expect(w.render).toHaveBeenCalled()

    it 'should rerender the waterfall on data change', ->
        dataService.when('builds', builds)
        spyOn(w, 'render').and.callThrough()
        expect(w.render).not.toHaveBeenCalled()
        w.loadMore()
        $timeout.flush()
        expect(w.render).toHaveBeenCalled()

    it 'should lazy load data on scroll', ->
        spyOn(w, 'getHeight').and.returnValue(900)
        e = d3.select('.inner-content')
        n = e.node()
        w.loadMore.calls.reset()
        callCount = w.loadMore.calls.count()
        expect(callCount).toBe(0)
        angular.element(n).triggerHandler('scroll')
        callCount = w.loadMore.calls.count()
        expect(callCount).toBe(1)

    it 'height should be scalable', ->
        height = w.getInnerHeight()
        group = bbSettingsService.getSettingsGroup()
        oldSetting = group.scaling_waterfall.value
        w.incrementScaleFactor()
        w.render()
        newHeight = w.getInnerHeight()
        expect(newHeight).toBe(height * 1.5)
        newSetting = group.scaling_waterfall.value
        expect(newSetting).toBe(oldSetting * 1.5)

    it 'should have string representations of result codes', ->
        testBuild =
            complete: false
            started_at: 0
        expect(w.getResultClassFromThing(testBuild)).toBe('pending')
        testBuild.complete = true
        expect(w.getResultClassFromThing(testBuild)).toBe('unknown')
        results =
            0: 'success'
            1: 'warnings'
            2: 'failure'
            3: 'skipped'
            4: 'exception'
            5: 'cancelled'
        for i in [0..5]
            testBuild.results = i
            expect(w.getResultClassFromThing(testBuild)).toBe(results[i])
