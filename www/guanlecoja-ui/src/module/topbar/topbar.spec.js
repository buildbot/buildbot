/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('topbar', function() {
    let scope;
    beforeEach(angular.mock.module("guanlecoja.ui"));
    let elmBody = (scope = null);

    const injected = function($rootScope, $compile) {
        elmBody = angular.element(
          '<gl-topbar></gl-topbar>'
        );

        scope = $rootScope;
        $compile(elmBody)(scope);
        return scope.$digest();
    };

    beforeEach((inject(injected)));

    // simple test to make sure the directive loads
    it('should load', function() {
        expect(elmBody).toBeDefined();
        // if there is an ul, the sidebar has been created
        expect(elmBody.find("ul").length).toBeGreaterThan(0);
    });

    // simple test to make sure the directive loads
    it('should update breadcrumb upon messages', inject(function($location){
        $location.hash = () => "bar/";
        scope.$broadcast("$stateChangeStart",
            {name: "foo"});
        expect(scope.breadcrumb).toEqual([ { caption : 'Foo', href : '#bar/' } ]);

        scope.$broadcast("glBreadcrumb", [{
            caption: "bar",
            sref: "foo"
        }
        ]);
        expect(scope.breadcrumb).toEqual([ { caption : 'bar', sref : 'foo' } ]);
    })
    );
});
