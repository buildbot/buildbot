/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
angular.module('common', []).constant('config', {'url': 'foourl'});
beforeEach(angular.mock.module('codeparameter'));
describe('minimalistic test', function() {
    let scope;
    let elmBody = (scope = null);

    const injected = function($rootScope, $compile) {
        elmBody = angular.element(
          '<codefield></codefield>'
        );

        scope = $rootScope;
        scope.field = {
            height:400,
            mode:"python",
            readonly:true
        };
        $compile(elmBody)(scope);
        return scope.$digest();
    };

    beforeEach((inject(injected)));

    it('should load ace ui ', function() {
        expect(elmBody).toBeDefined();
        // if we can find a div with class ace_layer, then ace has loaded
        const elm = elmBody.find('.ace_layer');
        expect(elm.length).toBeGreaterThan(0);
    });
});
