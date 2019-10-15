/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('topbar-contextual-actions', function() {
    let scope;
    beforeEach(angular.mock.module("guanlecoja.ui"));
    let elmBody = (scope = null);

    const injected = function($rootScope, $compile) {
        elmBody = angular.element(
            '<gl-topbar-contextual-actions></gl-contextual-actions>'
        );

        scope = $rootScope.$new();
        $compile(elmBody)(scope);
        return scope.$digest();
    };

    beforeEach((inject(injected)));

    // simple test to make sure the directive loads
    it('should load', function() {
        expect(elmBody).toBeDefined();
        // should be empty at init
        expect(elmBody.find("li").length).toEqual(0);
    });


    // create the buttons via API
    it('should create buttons', inject(function(glTopbarContextualActionsService) {
        expect(elmBody).toBeDefined();
        let called = 0;
        glTopbarContextualActionsService.setContextualActions([{
            caption:"foo",
            action() { return called++; }
        }
        , {
            caption:"bar",
            action() { return called++; }
        }
            ]);

        scope.$digest();
        expect(elmBody.find(".form-group").length).toEqual(2);
        expect(elmBody.find("button").text()).toEqual("foobar");

        // make sure action is called on click
        elmBody.find("button").each(function() {
            return $(this).click();
        });
        scope.$digest();
        expect(called).toEqual(2);
    })
    );
});
