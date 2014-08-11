beforeEach ->
    # Mocked module dependencies
    angular.module 'common', []
    angular.module 'ui.bootstrap', []
    angular.module 'ngAnimate', []

    module 'console_view'

describe 'Console view', ->
    $state = null

    injected = ($injector) ->
        $state = $injector.get('$state')

    beforeEach(inject(injected))

    it 'should register a new state with the correct configuration', ->
        name = 'console'
        state = $state.get().pop()
        data = state.data
        expect(state.controller).toBe("#{name}Controller")
        expect(state.controllerAs).toBe('c')
        expect(state.templateUrl).toBe("console_view/views/#{name}.html")
        expect(state.url).toBe("/#{name}")

describe 'Console view controller', ->
    createController = scope = $rootScope = null

    # Test data

    builders = [
        builderid: 1
    ,
        builderid: 2
    ,
        builderid: 3
    ,
        builderid: 4
    ]

    builds1 = [
        buildid: 1
        builderid: 1
        buildrequestid: 1
    ,
        buildid: 2
        builderid: 2
        buildrequestid: 1
    ,
        buildid: 3
        builderid: 4
        buildrequestid: 2
    ,
        buildid: 4
        builderid: 3
        buildrequestid: 2
    ]

    builds2 = [
        buildid: 5
        builderid: 2
        buildrequestid: 3
    ]

    builds = builds1.concat(builds2)

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

    buildsets = [
        bsid: 1
        sourcestamps: [
            ssid: 1
        ]
    ,
        bsid: 2
        sourcestamps: [
            ssid: 2
        ]
    ]

    changes = [
        changeid: 1
        sourcestamp:
            ssid: 1
    ]

    injected = ($injector) ->
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        $window = $injector.get('$window')
        scope = $rootScope.$new()

        # Mocked service
        buildbotServiceMock =
            all: (string) =>
                deferred = $q.defer()
                switch string
                    when 'builds'
                        deferred.resolve builds
                    when 'builders'
                        deferred.resolve builders
                    when 'changes'
                        deferred.resolve changes
                    when 'buildrequests'
                        deferred.resolve buildrequests
                    when 'buildsets'
                        deferred.resolve buildsets
                    else
                        deferred.resolve []
                bind: -> deferred.promise

        # Create new controller using controller as syntax
        $controller = $injector.get('$controller')
        createController = ->
            return $controller 'consoleController as c',
                # Inject controller dependencies
                $q: $q
                $window: $window
                $scope: scope
                buildbotService: buildbotServiceMock

    beforeEach(inject(injected))

    it 'should be defined', ->
        createController()
        expect(scope.c).toBeDefined()

    it 'should bind the builds, builders, changes, buildrequests and buildsets to scope', ->
        createController()
        $rootScope.$digest()
        expect(scope.c.builds).toBeDefined()
        expect(scope.c.builds.length).toBe(builds.length)
        expect(scope.c.builders).toBeDefined()
        expect(scope.c.builders.length).toBe(builders.length)
        expect(scope.c.changes).toBeDefined()
        expect(scope.c.changes.length).toBe(changes.length)
        expect(scope.c.buildrequests).toBeDefined()
        expect(scope.c.buildrequests.length).toBe(buildrequests.length)
        expect(scope.c.buildsets).toBeDefined()
        expect(scope.c.buildsets.length).toBe(buildsets.length)

    it 'should match the builds with the change', ->
        createController()
        $rootScope.$digest()
        expect(scope.c.changes[0]).toBeDefined()
        expect(scope.c.changes[0].builds).toBeDefined()
        expect(scope.c.changes[0].builds.length).toBe(builds1.length)
        for build in builds1
            expect(scope.c.changes[0].builds).toContain(build)
