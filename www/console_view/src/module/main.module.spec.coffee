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
    # Test data

    builders = [
        builderid: 1
        masterids: [1]
    ,
        builderid: 2
        masterids: [1]
    ,
        builderid: 3
        masterids: [1]
    ,
        builderid: 4
        masterids: [1]
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
    createController = scope = $rootScope = dataService = $window = $timeout = null

    injected = ($injector) ->
        $q = $injector.get('$q')
        $rootScope = $injector.get('$rootScope')
        $window = $injector.get('$window')
        $timeout = $injector.get('$timeout')
        dataService = $injector.get('dataService')
        scope = $rootScope.$new()
        dataService.when('builds', builds)
        dataService.when('builders', builders)
        dataService.when('changes', changes)
        dataService.when('buildrequests', buildrequests)
        dataService.when('buildsets', buildsets)

        # Create new controller using controller as syntax
        $controller = $injector.get('$controller')
        createController = ->
            return $controller 'consoleController as c',
                # Inject controller dependencies
                $q: $q
                $window: $window
                $scope: scope

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
        $timeout.flush()
        expect(scope.c.changes[0]).toBeDefined()
        expect(scope.c.changes[0].buildsPerBuilder).toBeDefined()
        builds = scope.c.changes[0].buildsPerBuilder
        expect(builds[1][0].buildid).toBe(1)
        expect(builds[2][0].buildid).toBe(2)
        expect(builds[3][0].buildid).toBe(4)
        expect(builds[4][0].buildid).toBe(3)
