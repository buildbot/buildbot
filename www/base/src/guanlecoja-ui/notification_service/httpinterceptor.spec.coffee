describe 'http Interceptor', ->
    beforeEach module "guanlecoja.ui"

    it 'should intercept errors', inject ($q, $rootScope, glNotificationService, $timeout, glHttpInterceptor) ->
        d = $q.defer()
        i = glHttpInterceptor(d.promise)
        spyOn(glNotificationService, "network").and.returnValue(null)
        d.reject("oups")
        $rootScope.$digest()
        $timeout.flush()
        expect(glNotificationService.network).toHaveBeenCalledWith("oups");

    it 'should intercept http errors', inject ($q, $rootScope, glNotificationService, $timeout, glHttpInterceptor) ->
        d = $q.defer()
        i = glHttpInterceptor(d.promise)
        spyOn(glNotificationService, "network").and.returnValue(null)
        d.reject(status: "404", data:{error:"not found"}, config:{method:"get",url:"http://foo"})
        $rootScope.$digest()
        $timeout.flush()
        expect(glNotificationService.network).toHaveBeenCalledWith("404:not found when:get http://foo");
