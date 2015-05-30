beforeEach module 'app'

describe 'panel', ->

    $rootScope = $compile = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')

    beforeEach inject injected

