/*
 * decaffeinate suggestions:
 * DS001: Remove Babel/TypeScript constructor workaround
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Collection {
    constructor($q, $injector, $log, dataUtilsService, socketService, DataQuery, $timeout) {
        let CollectionInstance;
        angular.isArray = (Array.isArray = arg => arg instanceof Array);
        return (CollectionInstance = class CollectionInstance extends Array {
            constructor(restPath, query, accessor) {
                let className;
                {
                  // Hack: trick Babel/TypeScript into allowing this before super.
                  if (false) { super(); }
                  let thisFn = (() => { this; }).toString();
                  let thisName = thisFn.slice(thisFn.indexOf('{') + 1, thisFn.indexOf(';')).trim();
                  eval(`${thisName} = this;`);
                }
                this.listener = this.listener.bind(this);
                this.restPath = restPath;
                if (query == null) { query = {}; }
                this.query = query;
                this.accessor = accessor;
                this.socketPath = dataUtilsService.socketPath(this.restPath);
                this.type = dataUtilsService.type(this.restPath);
                this.id = dataUtilsService.classId(this.restPath);
                this.endpoint = dataUtilsService.endpointPath(this.restPath);
                this.socketPathRE = dataUtilsService.socketPathRE(this.socketPath);
                this.queryExecutor = new DataQuery(this.query);
                // default event handlers
                this.onUpdate = angular.noop;
                this.onNew = angular.noop;
                this.onChange = angular.noop;
                this._new = [];
                this._updated = [];
                this._byId = {};
                this.$resolved = false;
                try {
                    // try to get the wrapper class
                    className = dataUtilsService.className(this.restPath);
                    // the classes have the dataService as a dependency
                    // $injector.get doesn't throw circular dependency exception
                    this.WrapperClass = $injector.get(className);
                } catch (e) {
                    // use the Base class otherwise
                    console.log("unknown wrapper for", className);
                    this.WrapperClass = $injector.get('Base');
                }
                socketService.eventStream.subscribe(this.listener);
                if (this.accessor != null) {
                    this.accessor.registerCollection(this);
                }
            }

            then(callback) {
                console.log("Should not use collection as a promise. Callback will be called several times!");
                return this.onChange = callback;
            }

            getArray() {
                console.log("getArray() is deprecated. dataService.get() directly returns the collection!");
                return this;
            }

            get(id) {
                return this._byId[id];
            }

            hasOwnProperty(id) {
                return this._byId.hasOwnProperty(id);
            }

            listener(data) {
                const key = data.k;
                const message = data.m;
                // Test if the message is for me
                if (this.socketPathRE.test(key)) {
                    this.put(message);
                    this.recomputeQuery();
                    return this.sendEvents();
                }
            }

            subscribe() {
                return socketService.subscribe(this.socketPath, this);
            }

            close() {
                return socketService.unsubscribe(this.socketPath, this);
            }

            initial(data) {
                this.$resolved = true;
                // put items one by one if not already in the array
                // if they are that means they come from an update event
                // the event is always considered the latest data
                // so we don't overwrite it with REST data
                for (let i of Array.from(data)) {
                    if (!this.hasOwnProperty(i[this.id])) {
                        this.put(i);
                    }
                }
                this.recomputeQuery();
                return this.sendEvents({initial:true});
            }

            from(data) {
                // put items one by one
                for (let i of Array.from(data)) { this.put(i); }
                this.recomputeQuery();
                return this.sendEvents();
            }

            item(i) {
                return this[i];
            }

            add(element) {
                // don't create wrapper if element is filtered
                if (this.queryExecutor.filter([element]).length === 0) {
                    return;
                }
                const instance = new this.WrapperClass(element, this.endpoint);
                instance.setAccessor(this.accessor);
                instance.$collection = this;
                this._new.push(instance);
                this._byId[instance[this.id]] = instance;
                return this.push(instance);
            }

            put(element) {
                for (let old of Array.from(this)) {
                    if (old[this.id] === element[this.id]) {
                        old.update(element);
                        this._updated.push(old);
                        return;
                    }
                }
                // if not found, add it.
                return this.add(element);
            }

            clear() {
                return (() => {
                    const result = [];
                    while (this.length > 0) {
                        result.push(this.pop());
                    }
                    return result;
                })();
            }

            delete(element) {
                const index = this.indexOf(element);
                if (index > -1) { return this.splice(index, 1); }
            }

            recomputeQuery() {
                return this.queryExecutor.computeQuery(this);
            }

            sendEvents(opts){
                // send the events asynchronously
                const { _new } = this;
                const { _updated } = this;
                this._updated = [];
                this._new = [];
                return $timeout(() => {
                    let changed = false;
                    for (var i of Array.from(_new)) {
                        // is it still in the array?
                        if (Array.from(this).includes(i)) {
                            this.onNew(i);
                            changed = true;
                        }
                    }

                    for (i of Array.from(_updated)) {
                        // is it still in the array?
                        if (Array.from(this).includes(i)) {
                            this.onUpdate(i);
                            changed = true;
                        }
                    }

                    if (changed || (opts != null ? opts.initial : undefined)) {
                        return this.onChange(this);
                    }
                }
                , 0);
            }
        });
    }
}


angular.module('app')
.factory('Collection', ['$q', '$injector', '$log', 'dataUtilsService', 'socketService', 'DataQuery', '$timeout', Collection]);