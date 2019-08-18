/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('http Interceptor', function() {
    beforeEach(angular.mock.module("guanlecoja.ui"));

    it('should intercept errors', inject(function($q, $rootScope, glNotificationService, $timeout, glHttpInterceptor) {
        const d = $q.defer();
        const i = glHttpInterceptor(d.promise);
        spyOn(glNotificationService, "network").and.returnValue(null);
        d.reject("oups");
        $rootScope.$digest();
        $timeout.flush();
        expect(glNotificationService.network).toHaveBeenCalledWith("oups");
    })
    );

    it('should intercept http errors',
       inject(function($q, $rootScope, glNotificationService, $timeout, glHttpInterceptor) {
        const d = $q.defer();
        const i = glHttpInterceptor(d.promise);
        spyOn(glNotificationService, "network").and.returnValue(null);
        d.reject({status: "404", data:{error:"not found"}, config:{method:"get",url:"http://foo"}});
        $rootScope.$digest();
        $timeout.flush();
        expect(glNotificationService.network).toHaveBeenCalledWith("404:not found when:get http://foo");
    })
    );
});
