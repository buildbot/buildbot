beforeEach module 'app'

describe 'buildstep', ->

    $compile = $rootScope = $httpBackend = dataService = scope = RESULTS_TEXT = null
    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $httpBackend = $injector.get('$httpBackend')
        decorateHttpBackend($httpBackend)
        $q = $injector.get('$q')
        webSocketService = $injector.get('webSocketService')
        spyOn(webSocketService, 'getWebSocket').and.returnValue({})
        dataService = $injector.get('dataService')
        spyOn(dataService, 'startConsuming').and.returnValue($q.resolve())
        scope = $rootScope.$new()
        RESULTS_TEXT = $injector.get('RESULTS_TEXT')

    beforeEach inject injected

    getStep = ->
        $httpBackend.expectDataGET 'builds/1'
        build = null
        dataService.getBuilds(1).then (data) -> build = data[0]
        $httpBackend.flush()

        $httpBackend.expectDataGET 'builds/1/steps'
        step = null
        build.loadSteps().then (data) -> step = data[0]
        $httpBackend.flush()

        return step

    it 'should show status correctly', ->
        step = getStep()
        step.started_at = Math.floor((new Date()).valueOf() / 1000) - 5

        $rootScope.step = step
        elem = $compile('<build-step step="step"></build-step>')($rootScope)

        $httpBackend.expectDataGET 'builds/1/steps/2/logs'
        $rootScope.$digest()
        $httpBackend.flush()

        meta = elem.children().eq(0)
        name = meta.children().eq(1)
        state_string = meta.children().eq(2)
        duration = meta.children().eq(3)
        statedot = meta.children().eq(4).children().eq(0)

        expect(name.text()).toBe(step.name)
        expect(state_string.text()).toBe(step.state_string)
        expect(duration.text()).toBe('5s')

        # Pending state
        expect(statedot.hasClass('pending')).toBe(true)

        # Success state
        step.results = 0
        step.complete = true
        step.complete_at = step.started_at + 10
        step.state_string = "finish"
        $rootScope.$digest()

        expect(state_string.text()).toBe('finish')
        expect(duration.text()).toBe('10s')
        expect(statedot.hasClass('success')).toBe(true)
        expect(statedot.hasClass('pending')).toBe(false)

        # Other states
        for result in [1..6]
            step.results = result
            $rootScope.$digest()
            for state in [1..6]
                expect(statedot.hasClass(RESULTS_TEXT[state].toLowerCase())).toBe(result == state)

        # Unknown states
        step.results = 7
        $rootScope.$digest()
        expect(statedot.hasClass('unknown')).toBe(true)
        expect(statedot.hasClass('success')).toBe(false)
        expect(statedot.hasClass('pending')).toBe(false)

    it 'should show logs correctly', ->
        step = getStep()
        step.complete = true
        step.started_at = Math.floor((new Date()).valueOf() / 1000) - 5
        step.complete_at = step.started_at + 10

        $rootScope.step = step
        elem = $compile('<build-step step="step"></build-step>')($rootScope)

        $httpBackend.expectDataGET 'builds/1/steps/2/logs'
        $rootScope.$digest()
        $httpBackend.flush()

        expect(elem.children().length).toBe(1) # logs not showing now

        meta = elem.children().eq(0)
        $httpBackend.expectDataGET('builds/1/steps/2/logs/myslug1/contents')
        $httpBackend.expectGETSVGIcons()
        meta.triggerHandler 'click'
        $httpBackend.flush()

        expect(elem.children().length).toBe(2) # logs showing now

        logscontainer = elem.children().eq(1)
        expect(logscontainer.children().length).toBe(2)

        # add another mock log entry
        oldlog = step.logs[0]
        newlog = angular.copy oldlog
        newlog.name = "nameOfNewLog"
        step.logs.push newlog
        $rootScope.$digest()

        logswitch = logscontainer.children().eq(0)
        expect(logswitch.children().length).toBe(4)

        firstlog = logswitch.children().eq(0)
        secondlog = logswitch.children().eq(1)
        download = logswitch.children().eq(3)

        expect(firstlog.text()).toBe(oldlog.name)
        expect(secondlog.text()).toBe(newlog.name)

        # The first log button is selected
        expect(firstlog.hasClass('selected')).toBe(true)
        expect(secondlog.hasClass('selected')).toBe(false)
        expect(download.attr('href')).toBe("/api/v2/logs/#{ oldlog.logid }/raw")

        # The second log button is selected
        secondlog.triggerHandler 'click'
        expect(firstlog.hasClass('selected')).toBe(false)
        expect(secondlog.hasClass('selected')).toBe(true)
        expect(download.attr('href')).toBe("/api/v2/logs/#{ newlog.logid }/raw")

        # collapse logs
        meta.triggerHandler 'click'
        expect(elem.children().length).toBe(1)
