beforeEach module 'guanlecoja.ui'
describe 'minimalistic test', ->
    elmBody = scope = null

    injected = ($rootScope, $compile) ->
        elmBody = angular.element(
          '<sidemenu></sidemenu>'
        )

        scope = $rootScope;
        $compile(elmBody)(scope);
        scope.$digest();

    beforeEach (inject(injected))

    it 'should load ', ->
        expect(elmBody).toBeDefined()
