angular.module 'devapp', ['app', 'ngMockE2E']

angular.module('devapp').run [
    '$httpBackend', ($httpBackend) ->
        decorateHttpBackend($httpBackend)
        $httpBackend.whenGET(/^views\//).passThrough()
        for dataEp in window.dataspec
            path = dataEp.path
            lastpath = $httpBackend.epLastPath(path)
            if (lastpath.indexOf("n:") == 0)
                $httpBackend.whenDataGET($httpBackend.epExample(path))
            else
                $httpBackend.whenDataGET($httpBackend.epExample(path), {nItems: 10})
    ]
