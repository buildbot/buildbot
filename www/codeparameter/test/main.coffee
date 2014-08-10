angular.module('common', []).constant('config', {'url': 'foourl'})
beforeEach module 'codeparameter'
describe 'minimalistic test', ->
    elmBody = scope = null

    injected = ($rootScope, $compile) ->
        elmBody = angular.element(
          '<codefield></codefield>'
        )

        scope = $rootScope;
        scope.field =
            height:400
            mode:"python"
            readonly:true
        $compile(elmBody)(scope);
        scope.$digest();

    beforeEach (inject(injected))

    it 'should load ace ui ', ->
        expect(elmBody).toBeDefined()
        # if we can find a div with class ace_layer, then ace has loaded
        elm = elmBody.find('.ace_layer');
        expect(elm.length).toBeGreaterThan(0)
