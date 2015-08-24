beforeEach module 'app'

describe 'forcebuildform', ->

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

    it 'should show fields correctly', ->
        $rootScope.fields =
            type: 'nested'
            layout: 'simple'
            fields:[
                type: 'int'
                label: 'intlabel'
            ,
                type: 'textarea'
                label: 'textarealabel'
            ,
                type: 'text'
                label: 'textlabel'
            ,
                type: 'bool'
                label: 'boollabel'
            ,
                type: 'list'
                label: 'listlabel'
                choices: ['a', 'b', 'c']
            ]
        $rootScope.data = {}
        elem = $compile('<forcebuild-form fields="fields" data="data"></forcebuild-form>')($rootScope)
        $rootScope.digest()
