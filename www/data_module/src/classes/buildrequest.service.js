class Buildrequest {
    constructor(Base, dataService) {
        let BuildrequestInstance;
        return (BuildrequestInstance = class BuildrequestInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'builds'            // /builds
                ];

                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('bbData')
.factory('Buildrequest', ['Base', 'dataService', Buildrequest]);
