beforeEach module 'app'

describe 'forcebuildform', ->

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
