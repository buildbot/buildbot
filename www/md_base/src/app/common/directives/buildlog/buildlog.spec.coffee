beforeEach module 'app'

describe 'buildlog', ->

    $compile = $rootScope = $httpBackend = dataService = scope = null
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

    beforeEach inject injected

    getLog = ->
        $httpBackend.expectDataGET 'builds/1'
        build = null
        dataService.getBuilds(1).then (data) -> build = data[0]
        $httpBackend.flush()

        $httpBackend.expectDataGET 'builds/1/steps'
        step = null
        build.loadSteps().then (data) -> step = data[0]
        $httpBackend.flush()

        $httpBackend.expectDataGET 'builds/1/steps/2/logs'
        log = null
        step.loadLogs().then (data) -> log = data[0]
        $httpBackend.flush()

        return log

    it 'should display log contents correctly', ->
        log = getLog()
        $rootScope.log = log
        $httpBackend.expectDataGET('builds/1/steps/2/logs/myslug1/contents')
        elem = $compile('<build-log log="log"></build-log>')($rootScope)
        $rootScope.$digest()
        $httpBackend.flush()

        codetable = elem.children().eq(0)
        expect(codetable.children().length).toBe(0)

        log.contents.push
            firstline: 0 # content object returns by API start numbering from zero
            content:'''
            testline1
            testline2
            testline3
            testline4
            testline5
            testline6

            ''' # content has a tailing \n
        $rootScope.$digest()

        expect(codetable.children().length).toBe(6)
        for line in [1..6]
            tr = codetable.children().eq(line - 1)
            lineno = tr.children().eq(0)
            linecontent = tr.children().eq(1)
            expect(lineno.text()).toBe('' + line)
            expect(linecontent.text()).toBe('testline' + line)

        # Test append new content object
        log.contents.push
            firstline: 6
            content:'''
            more-testline7
            more-testline8
            more-testline9
            more-testline10
            more-testline11
            more-testline12

            ''' # content has a tailing \n
        $rootScope.$digest()

        expect(codetable.children().length).toBe(12)

        # Verify the first 6 line again
        for line in [1..6]
            tr = codetable.children().eq(line - 1)
            lineno = tr.children().eq(0)
            linecontent = tr.children().eq(1)
            expect(lineno.text()).toBe('' + line)
            expect(linecontent.text()).toBe('testline' + line)

        # Verify new lines
        for line in [7..12]
            tr = codetable.children().eq(line - 1)
            lineno = tr.children().eq(0)
            linecontent = tr.children().eq(1)
            expect(lineno.text()).toBe('' + line)
            expect(linecontent.text()).toBe('more-testline' + line)

    it 'should refresh content automatically', ->
        # If user another log instance is given to the same build-log directive,
        # it should refresh the contents instead of appending them.
        originlog = getLog()
        newlog = angular.copy originlog
        newlog.slug = 'myslug2'

        $rootScope.log = originlog
        $httpBackend.expectDataGET('builds/1/steps/2/logs/myslug1/contents')
        elem = $compile('<build-log log="log"></build-log>')($rootScope)
        $rootScope.$digest()
        $httpBackend.flush()

        codetable = elem.children().eq(0)
        expect(codetable.children().length).toBe(0)

        originlog.contents.push
            firstline: 0
            content: '''
            origin log content line 1
            origin log content line 2
            origin log content line 3
            origin log content line 4
            origin log content line 5
            origin log content line 6

            '''

        $rootScope.$digest()
        expect(codetable.children().length).toBe(6)

        for line in [1..6]
            tr = codetable.children().eq(line - 1)
            lineno = tr.children().eq(0)
            linecontent = tr.children().eq(1)
            expect(lineno.text()).toBe('' + line)
            expect(linecontent.text()).toBe('origin log content line ' + line)

        $rootScope.log = newlog
        $httpBackend.expectDataGET('builds/1/steps/2/logs/myslug2/contents')
        $rootScope.$digest()
        $httpBackend.flush()

        expect(codetable.children().length).toBe(0)

        newlog.contents.push
            firstline: 0
            content: '''
            new log content line 1
            new log content line 2
            new log content line 3

            '''

        $rootScope.$digest()
        expect(codetable.children().length).toBe(3)

        for line in [1..3]
            tr = codetable.children().eq(line - 1)
            lineno = tr.children().eq(0)
            linecontent = tr.children().eq(1)
            expect(lineno.text()).toBe('' + line)
            expect(linecontent.text()).toBe('new log content line ' + line)
