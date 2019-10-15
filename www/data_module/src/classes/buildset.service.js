class Buildset {
    constructor(Base, dataService) {
        let BuildsetInstance;
        return (BuildsetInstance = class BuildsetInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'properties'        // /properties
                ];

                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('bbData')
.factory('Buildset', ['Base', 'dataService', Buildset]);
