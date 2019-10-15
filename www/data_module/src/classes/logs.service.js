class Log {
    constructor(Base, dataService) {
        let BuildInstance;
        return (BuildInstance = class BuildInstance extends Base {
            constructor(object, endpoint) {
                const endpoints = [
                    'chunks',           // /chunks
                    'contents'
                ];
                super(object, endpoint, endpoints);
            }
        });
    }
}


angular.module('bbData')
.factory('Log', ['Base', 'dataService', Log]);
