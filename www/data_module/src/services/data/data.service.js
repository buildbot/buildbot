/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS206: Consider reworking classes to avoid initClass
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Data {
    static initClass() {
        // TODO caching
        this.prototype.cache = false;
    }
    constructor($log, $q, restService, socketService, dataUtilsService, Collection,
                ENDPOINTS) {
        let DataService;
        return new ((DataService = (function() {
            let self = undefined;
            DataService = class DataService {
                static initClass() {
                    self = null;

                //############# utils for testing
                // register return values for the mocked get function
                    this.prototype.mocks = {};
                    this.prototype.spied = false;
                }
                constructor() {
                    self = this;
                    // setup socket listeners
                    //socketService.eventStream.onUnsubscribe = @unsubscribeListener
                    socketService.onclose = this.socketCloseListener;
                    // generate loadXXX functions for root endpoints
                    this.constructor.generateEndpoints();
                }

                // the arguments are in this order: endpoint, id, child, id of child, query
                get(...args) {

                    // get the query parameters
                    let accessor, query, subscribePromise;
                    [args, query] = Array.from(dataUtilsService.splitOptions(args));
                    let subscribe = (accessor = undefined);

                    // subscribe for changes if 'subscribe' is true
                    subscribe = query.subscribe === true;
                    ({ accessor } = query);
                    if (subscribe && !accessor) {
                        $log.warn("subscribe call should be done after DataService.open()");
                        $log.warn("for maintaining trace of observers");
                        subscribe = false;
                    }

                    // 'subscribe' is not part of the query
                    delete query.subscribe;
                    delete query.accessor;

                    const restPath = dataUtilsService.restPath(args);
                    // up to date array, this will be returned
                    const collection = new Collection(restPath, query, accessor);

                    if (subscribe) {
                        subscribePromise = collection.subscribe();
                    } else {
                        subscribePromise = $q.resolve();
                    }

                    subscribePromise.then(() =>
                        // get the data from the rest api
                        restService.get(restPath, query).then(function(response) {

                            const type = dataUtilsService.type(restPath);
                            const datalist = response[type];
                            // the response should always be an array
                            if (!angular.isArray(datalist)) {
                                const e = `${datalist} is not an array`;
                                $log.error(e);
                                return;
                            }

                            // fill up the collection with initial data
                            collection.initial(datalist);
                        })
                    );

                    return collection;
                }


                control(ep, id, method, params) {
                    if (params == null) { params = {}; }
                    const restPath = dataUtilsService.restPath([ep, id]);
                    return restService.post(restPath, {
                        id: this.getNextId(),
                        jsonrpc: '2.0',
                        method,
                        params
                    }
                    );
                }

                // returns next id for jsonrpc2 control messages
                getNextId() {
                    if (this.jsonrpc == null) { this.jsonrpc = 1; }
                    return this.jsonrpc++;
                }

                // generate functions for root endpoints
                static generateEndpoints() {
                    return ENDPOINTS.forEach(e => {
                        // capitalize endpoint names
                        const E = dataUtilsService.capitalize(e);
                        return this.prototype[`get${E}`] = (...args) => self.get(e, ...Array.from(args));
                    });
                }

                // opens a new accessor
                open() {
                    let DataAccessor;
                    return new ((DataAccessor = (function() {
                        let collectionRefs = undefined;
                        DataAccessor = class DataAccessor {
                            static initClass() {
                                collectionRefs = [];
                            }
                            constructor() {
                                this.constructor.generateEndpoints();
                            }

                            registerCollection(c) {
                                return collectionRefs.push(c);
                            }

                            close() {
                                return collectionRefs.forEach(c => c.close());
                            }

                            // Closes the group when the scope is destroyed
                            closeOnDestroy(scope) {
                                if (!angular.isFunction(scope.$on)) {
                                    throw new TypeError("Parameter 'scope' doesn't have an $on function");
                                }
                                scope.$on('$destroy', () => this.close());
                                return this;
                            }

                            // Generate functions for root endpoints
                            static generateEndpoints() {
                                return ENDPOINTS.forEach(e => {
                                    // capitalize endpoint names
                                    const E = dataUtilsService.capitalize(e);
                                    this.prototype[`get${E}`] = function(...args) {
                                        let query;
                                        [args, query] = Array.from(dataUtilsService.splitOptions(args));
                                        if (query.subscribe == null) { query.subscribe = true; }
                                        query.accessor = this;
                                        return self.get(e, ...Array.from(args), query);
                                    };
                                });
                            }
                        };
                        DataAccessor.initClass();
                        return DataAccessor;
                    })()));
                }
                when(url, query, returnValue) {
                    if ((returnValue == null)) {
                        [query, returnValue] = Array.from([{}, query]);
                    }
                    if ((typeof jasmine !== 'undefined' && jasmine !== null) && !this.spied) {
                        spyOn(this, 'get').and.callFake(this._mockGet);
                        this.spied = true;
                    }

                    if (this.mocks[url] == null) { this.mocks[url] = {}; }
                    return this.mocks[url][query] = returnValue;
                }

                expect(url, query, returnValue) {
                    if ((returnValue == null)) {
                        [query, returnValue] = Array.from([{}, query]);
                    }
                    if (this._expects == null) { this._expects = []; }
                    this._expects.push([url, query]);
                    return this.when(url, query, returnValue);
                }

                verifyNoOutstandingExpectation() {
                    if ((this._expects != null) && this._expects.length) {
                        return fail(`expecting ${this._expects.length} more data requests ` +
                            `(${angular.toJson(this._expects)})`);
                    }
                }

                // register return values with the .when function
                // when testing get will return the given values
                _mockGet(...args) {
                    const [url, query] = Array.from(this.processArguments(args));
                    const queryWithoutSubscribe = {};
                    for (let k in query) {
                        const v = query[k];
                        if ((k !== "subscribe") && (k !== "accessor")) {
                            queryWithoutSubscribe[k] = v;
                        }
                    }
                    if (this._expects) {
                        const [exp_url, exp_query] = Array.from(this._expects.shift());
                        expect(exp_url).toEqual(url);
                        expect(exp_query).toEqual(queryWithoutSubscribe);
                    }
                    const returnValue = (this.mocks[url] != null ? this.mocks[url][query] : undefined) || (this.mocks[url] != null ? this.mocks[url][queryWithoutSubscribe] : undefined);
                    if ((returnValue == null)) { throw new Error(`No return value for: ${url} ` +
                        `(${angular.toJson(queryWithoutSubscribe)})`); }
                    const collection = this.createCollection(url, queryWithoutSubscribe, returnValue);
                    return collection;
                }

                processArguments(args) {
                    let query;
                    [args, query] = Array.from(dataUtilsService.splitOptions(args));
                    const restPath = dataUtilsService.restPath(args);
                    return [restPath, query || {}];
                }


                // for easier testing
                createCollection(url, query, response) {
                    const restPath = url;
                    const type = dataUtilsService.type(restPath);
                    const collection = new Collection(restPath, query);

                    // populate the response with default ids
                    // for convenience
                    const { id } = collection;
                    let idCounter = 1;
                    response.forEach(function(d) {
                        if (!d.hasOwnProperty(id)) {
                            d[id] = idCounter++;
                        }
                    });

                    collection.initial(response);
                    return collection;
                }
            };
            DataService.initClass();
            return DataService;
        })()));
    }
}
Data.initClass();


angular.module('bbData')
.service('dataService', ['$log', '$q', 'restService', 'socketService',
                         'dataUtilsService', 'Collection', 'ENDPOINTS', Data]);
