BOWERDEPS = (typeof BOWERDEPS === 'undefined') ? {}: BOWERDEPS;
(function() {
  var App;

  App = (function() {
    function App() {
      return [];
    }

    return App;

  })();

  angular.module('bbData', new App());

}).call(this);

(function() {
  var Api, Endpoints;

  Api = (function() {
    function Api() {
      return 'api/v2/';
    }

    return Api;

  })();

  Endpoints = (function() {
    function Endpoints() {
      return ['builders', 'builds', 'buildrequests', 'workers', 'buildsets', 'changes', 'changesources', 'masters', 'sourcestamps', 'schedulers', 'forceschedulers'];
    }

    return Endpoints;

  })();

  angular.module('bbData').constant('API', Api()).constant('ENDPOINTS', Endpoints());

}).call(this);

(function() {
  var Base,
    slice = [].slice;

  Base = (function() {
    function Base(dataService, socketService, dataUtilsService) {
      var BaseInstance;
      return BaseInstance = (function() {
        function BaseInstance(object, _endpoint, childEndpoints) {
          var classId;
          this._endpoint = _endpoint;
          if (childEndpoints == null) {
            childEndpoints = [];
          }
          if (!angular.isString(this._endpoint)) {
            throw new TypeError("Parameter 'endpoint' must be a string, not " + (typeof this.endpoint));
          }
          this.$accessor = null;
          this.update(object);
          this.constructor.generateFunctions(childEndpoints);
          classId = dataUtilsService.classId(this._endpoint);
          this._id = this[classId];
          if (this._id != null) {
            this._endpoint = dataUtilsService.type(this._endpoint);
          }
        }

        BaseInstance.prototype.setAccessor = function(a) {
          return this.$accessor = a;
        };

        BaseInstance.prototype.update = function(o) {
          return angular.merge(this, o);
        };

        BaseInstance.prototype.get = function() {
          var args;
          args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
          return dataService.get.apply(dataService, [this._endpoint, this._id].concat(slice.call(args)));
        };

        BaseInstance.prototype.control = function(method, params) {
          return dataService.control(this._endpoint, this._id, method, params);
        };

        BaseInstance.generateFunctions = function(endpoints) {
          return endpoints.forEach((function(_this) {
            return function(e) {
              var E;
              E = dataUtilsService.capitalize(e);
              _this.prototype["load" + E] = function() {
                var args;
                args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
                return this[e] = this.get.apply(this, [e].concat(slice.call(args)));
              };
              return _this.prototype["get" + E] = function() {
                var args, query, ref;
                args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
                ref = dataUtilsService.splitOptions(args), args = ref[0], query = ref[1];
                if (this.$accessor) {
                  if (query.subscribe == null) {
                    query.subscribe = true;
                  }
                  query.accessor = this.$accessor;
                }
                return this.get.apply(this, [e].concat(slice.call(args), [query]));
              };
            };
          })(this));
        };

        return BaseInstance;

      })();
    }

    return Base;

  })();

  angular.module('bbData').factory('Base', ['dataService', 'socketService', 'dataUtilsService', Base]);

}).call(this);

(function() {
  var Build,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Build = (function() {
    function Build(Base, dataService) {
      var BuildInstance;
      return BuildInstance = (function(superClass) {
        extend(BuildInstance, superClass);

        function BuildInstance(object, endpoint) {
          var endpoints;
          endpoints = ['changes', 'properties', 'steps'];
          BuildInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return BuildInstance;

      })(Base);
    }

    return Build;

  })();

  angular.module('bbData').factory('Build', ['Base', 'dataService', Build]);

}).call(this);

(function() {
  var Builder,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Builder = (function() {
    function Builder(Base, dataService) {
      var BuilderInstance;
      return BuilderInstance = (function(superClass) {
        extend(BuilderInstance, superClass);

        function BuilderInstance(object, endpoint) {
          var endpoints;
          endpoints = ['builds', 'buildrequests', 'forceschedulers', 'workers', 'masters'];
          BuilderInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return BuilderInstance;

      })(Base);
    }

    return Builder;

  })();

  angular.module('bbData').factory('Builder', ['Base', 'dataService', Builder]);

}).call(this);

(function() {
  var Buildrequest,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Buildrequest = (function() {
    function Buildrequest(Base, dataService) {
      var BuildrequestInstance;
      return BuildrequestInstance = (function(superClass) {
        extend(BuildrequestInstance, superClass);

        function BuildrequestInstance(object, endpoint) {
          var endpoints;
          endpoints = ['builds'];
          BuildrequestInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return BuildrequestInstance;

      })(Base);
    }

    return Buildrequest;

  })();

  angular.module('bbData').factory('Buildrequest', ['Base', 'dataService', Buildrequest]);

}).call(this);

(function() {
  var Buildset,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Buildset = (function() {
    function Buildset(Base, dataService) {
      var BuildsetInstance;
      return BuildsetInstance = (function(superClass) {
        extend(BuildsetInstance, superClass);

        function BuildsetInstance(object, endpoint) {
          var endpoints;
          endpoints = ['properties'];
          BuildsetInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return BuildsetInstance;

      })(Base);
    }

    return Buildset;

  })();

  angular.module('bbData').factory('Buildset', ['Base', 'dataService', Buildset]);

}).call(this);

(function() {
  var Change,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Change = (function() {
    function Change(Base, dataService, dataUtilsService) {
      var ChangeInstance;
      return ChangeInstance = (function(superClass) {
        extend(ChangeInstance, superClass);

        function ChangeInstance(object, endpoint) {
          var author, email;
          ChangeInstance.__super__.constructor.call(this, object, endpoint);
          author = this.author;
          if (this.author == null) {
            author = "unknown";
          }
          email = dataUtilsService.emailInString(author);
          if (email) {
            if (author.split(' ').length > 1) {
              this.author_name = author.replace(RegExp("\\s<" + email + ">"), '');
              this.author_email = email;
            } else {
              this.author_name = email.split("@")[0];
              this.author_email = email;
            }
          } else {
            this.author_name = author;
          }
        }

        return ChangeInstance;

      })(Base);
    }

    return Change;

  })();

  angular.module('bbData').factory('Change', ['Base', 'dataService', 'dataUtilsService', Change]);

}).call(this);

(function() {
  var Changesource,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Changesource = (function() {
    function Changesource(dataService, Base) {
      var ChangesourceInstance;
      return ChangesourceInstance = (function(superClass) {
        extend(ChangesourceInstance, superClass);

        function ChangesourceInstance(object, endpoint) {
          ChangesourceInstance.__super__.constructor.call(this, object, endpoint);
        }

        return ChangesourceInstance;

      })(Base);
    }

    return Changesource;

  })();

  angular.module('bbData').factory('Changesource', ['dataService', 'Base', Changesource]);

}).call(this);

(function() {
  var Forcescheduler,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Forcescheduler = (function() {
    function Forcescheduler(Base, dataService) {
      var ForceschedulerInstance;
      return ForceschedulerInstance = (function(superClass) {
        extend(ForceschedulerInstance, superClass);

        function ForceschedulerInstance(object, endpoint) {
          ForceschedulerInstance.__super__.constructor.call(this, object, endpoint);
        }

        return ForceschedulerInstance;

      })(Base);
    }

    return Forcescheduler;

  })();

  angular.module('bbData').factory('Forcescheduler', ['Base', 'dataService', Forcescheduler]);

}).call(this);

(function() {
  var Log,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Log = (function() {
    function Log(Base, dataService) {
      var BuildInstance;
      return BuildInstance = (function(superClass) {
        extend(BuildInstance, superClass);

        function BuildInstance(object, endpoint) {
          var endpoints;
          endpoints = ['chunks', 'contents'];
          BuildInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return BuildInstance;

      })(Base);
    }

    return Log;

  })();

  angular.module('bbData').factory('Log', ['Base', 'dataService', Log]);

}).call(this);

(function() {
  var Master,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Master = (function() {
    function Master(Base, dataService) {
      var MasterInstance;
      return MasterInstance = (function(superClass) {
        extend(MasterInstance, superClass);

        function MasterInstance(object, endpoint) {
          var endpoints;
          endpoints = ['builders', 'workers', 'changesources', 'schedulers'];
          MasterInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return MasterInstance;

      })(Base);
    }

    return Master;

  })();

  angular.module('bbData').factory('Master', ['Base', 'dataService', Master]);

}).call(this);

(function() {
  var Propertie,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Propertie = (function() {
    function Propertie(Base, dataService) {
      var BuildInstance;
      return BuildInstance = (function(superClass) {
        extend(BuildInstance, superClass);

        function BuildInstance(object, endpoint) {
          BuildInstance.__super__.constructor.call(this, object, endpoint, []);
        }

        return BuildInstance;

      })(Base);
    }

    return Propertie;

  })();

  angular.module('bbData').factory('Propertie', ['Base', 'dataService', Propertie]);

}).call(this);

(function() {
  var Scheduler,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Scheduler = (function() {
    function Scheduler(Base, dataService) {
      var SchedulerInstance;
      return SchedulerInstance = (function(superClass) {
        extend(SchedulerInstance, superClass);

        function SchedulerInstance(object, endpoint) {
          SchedulerInstance.__super__.constructor.call(this, object, endpoint);
        }

        return SchedulerInstance;

      })(Base);
    }

    return Scheduler;

  })();

  angular.module('bbData').factory('Scheduler', ['Base', 'dataService', Scheduler]);

}).call(this);

(function() {
  var Sourcestamp,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Sourcestamp = (function() {
    function Sourcestamp(Base, dataService) {
      var SourcestampInstance;
      return SourcestampInstance = (function(superClass) {
        extend(SourcestampInstance, superClass);

        function SourcestampInstance(object, endpoint) {
          var endpoints;
          endpoints = ['changes'];
          SourcestampInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return SourcestampInstance;

      })(Base);
    }

    return Sourcestamp;

  })();

  angular.module('bbData').factory('Sourcestamp', ['Base', 'dataService', Sourcestamp]);

}).call(this);

(function() {
  var Step,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Step = (function() {
    function Step(Base, dataService) {
      var BuildInstance;
      return BuildInstance = (function(superClass) {
        extend(BuildInstance, superClass);

        function BuildInstance(object, endpoint) {
          var endpoints;
          endpoints = ['logs'];
          BuildInstance.__super__.constructor.call(this, object, endpoint, endpoints);
        }

        return BuildInstance;

      })(Base);
    }

    return Step;

  })();

  angular.module('bbData').factory('Step', ['Base', 'dataService', Step]);

}).call(this);

(function() {
  var Worker,
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty;

  Worker = (function() {
    function Worker(Base, dataService) {
      var WorkerInstance;
      return WorkerInstance = (function(superClass) {
        extend(WorkerInstance, superClass);

        function WorkerInstance(object, endpoint) {
          WorkerInstance.__super__.constructor.call(this, object, endpoint);
        }

        return WorkerInstance;

      })(Base);
    }

    return Worker;

  })();

  angular.module('bbData').factory('Worker', ['Base', 'dataService', Worker]);

}).call(this);

(function() {
  var Data,
    slice = [].slice;

  Data = (function() {
    function Data() {}

    Data.prototype.cache = false;


    /* @ngInject */

    Data.prototype.$get = function($log, $injector, $q, restService, socketService, dataUtilsService, Collection, ENDPOINTS) {
      var DataService;
      return new (DataService = (function() {
        var self;

        self = null;

        function DataService() {
          self = this;
          socketService.onclose = this.socketCloseListener;
          this.constructor.generateEndpoints();
        }

        DataService.prototype.get = function() {
          var accessor, args, collection, query, ref, restPath, subscribe, subscribePromise;
          args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
          ref = dataUtilsService.splitOptions(args), args = ref[0], query = ref[1];
          subscribe = accessor = void 0;
          subscribe = query.subscribe === true;
          accessor = query.accessor;
          if (subscribe && !accessor) {
            $log.warn("subscribe call should be done after DataService.open()");
            $log.warn("for maintaining trace of observers");
            subscribe = false;
          }
          delete query.subscribe;
          delete query.accessor;
          restPath = dataUtilsService.restPath(args);
          collection = new Collection(restPath, query, accessor);
          if (subscribe) {
            subscribePromise = collection.subscribe();
          } else {
            subscribePromise = $q.resolve();
          }
          subscribePromise.then(function() {
            return restService.get(restPath, query).then(function(response) {
              var datalist, e, type;
              type = dataUtilsService.type(restPath);
              datalist = response[type];
              if (!angular.isArray(datalist)) {
                e = datalist + " is not an array";
                $log.error(e);
                return;
              }
              return collection.initial(datalist);
            });
          });
          return collection;
        };

        DataService.prototype.control = function(ep, id, method, params) {
          var restPath;
          if (params == null) {
            params = {};
          }
          restPath = dataUtilsService.restPath([ep, id]);
          return restService.post(restPath, {
            id: this.getNextId(),
            jsonrpc: '2.0',
            method: method,
            params: params
          });
        };

        DataService.prototype.getNextId = function() {
          if (this.jsonrpc == null) {
            this.jsonrpc = 1;
          }
          return this.jsonrpc++;
        };

        DataService.generateEndpoints = function() {
          return ENDPOINTS.forEach((function(_this) {
            return function(e) {
              var E;
              E = dataUtilsService.capitalize(e);
              return _this.prototype["get" + E] = function() {
                var args;
                args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
                return self.get.apply(self, [e].concat(slice.call(args)));
              };
            };
          })(this));
        };

        DataService.prototype.open = function() {
          var DataAccessor;
          return new (DataAccessor = (function() {
            var collectionRefs;

            collectionRefs = [];

            function DataAccessor() {
              this.constructor.generateEndpoints();
            }

            DataAccessor.prototype.registerCollection = function(c) {
              return collectionRefs.push(c);
            };

            DataAccessor.prototype.close = function() {
              return collectionRefs.forEach(function(c) {
                return c.close();
              });
            };

            DataAccessor.prototype.closeOnDestroy = function(scope) {
              if (!angular.isFunction(scope.$on)) {
                throw new TypeError("Parameter 'scope' doesn't have an $on function");
              }
              scope.$on('$destroy', (function(_this) {
                return function() {
                  return _this.close();
                };
              })(this));
              return this;
            };

            DataAccessor.generateEndpoints = function() {
              return ENDPOINTS.forEach((function(_this) {
                return function(e) {
                  var E;
                  E = dataUtilsService.capitalize(e);
                  return _this.prototype["get" + E] = function() {
                    var args, query, ref;
                    args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
                    ref = dataUtilsService.splitOptions(args), args = ref[0], query = ref[1];
                    if (query.subscribe == null) {
                      query.subscribe = true;
                    }
                    query.accessor = this;
                    return self.get.apply(self, [e].concat(slice.call(args), [query]));
                  };
                };
              })(this));
            };

            return DataAccessor;

          })());
        };

        DataService.prototype.mocks = {};

        DataService.prototype.spied = false;

        DataService.prototype.when = function(url, query, returnValue) {
          var base, ref;
          if (returnValue == null) {
            ref = [{}, query], query = ref[0], returnValue = ref[1];
          }
          if ((typeof jasmine !== "undefined" && jasmine !== null) && !this.spied) {
            spyOn(this, 'get').and.callFake(this._mockGet);
            this.spied = true;
          }
          if ((base = this.mocks)[url] == null) {
            base[url] = {};
          }
          return this.mocks[url][query] = returnValue;
        };

        DataService.prototype.expect = function(url, query, returnValue) {
          var ref;
          if (returnValue == null) {
            ref = [{}, query], query = ref[0], returnValue = ref[1];
          }
          if (this._expects == null) {
            this._expects = [];
          }
          this._expects.push([url, query]);
          return this.when(url, query, returnValue);
        };

        DataService.prototype.verifyNoOutstandingExpectation = function() {
          if ((this._expects != null) && this._expects.length) {
            return fail(("expecting " + this._expects.length + " more data requests ") + ("(" + (angular.toJson(this._expects)) + ")"));
          }
        };

        DataService.prototype._mockGet = function() {
          var args, collection, exp_query, exp_url, k, query, queryWithoutSubscribe, ref, ref1, ref2, ref3, returnValue, url, v;
          args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
          ref = this.processArguments(args), url = ref[0], query = ref[1];
          queryWithoutSubscribe = {};
          for (k in query) {
            v = query[k];
            if (k !== "subscribe" && k !== "accessor") {
              queryWithoutSubscribe[k] = v;
            }
          }
          if (this._expects) {
            ref1 = this._expects.shift(), exp_url = ref1[0], exp_query = ref1[1];
            expect(exp_url).toEqual(url);
            expect(exp_query).toEqual(queryWithoutSubscribe);
          }
          returnValue = ((ref2 = this.mocks[url]) != null ? ref2[query] : void 0) || ((ref3 = this.mocks[url]) != null ? ref3[queryWithoutSubscribe] : void 0);
          if (returnValue == null) {
            throw new Error(("No return value for: " + url + " ") + ("(" + (angular.toJson(queryWithoutSubscribe)) + ")"));
          }
          collection = this.createCollection(url, queryWithoutSubscribe, returnValue);
          return collection;
        };

        DataService.prototype.processArguments = function(args) {
          var query, ref, restPath;
          ref = dataUtilsService.splitOptions(args), args = ref[0], query = ref[1];
          restPath = dataUtilsService.restPath(args);
          return [restPath, query || {}];
        };

        DataService.prototype.createCollection = function(url, query, response) {
          var collection, id, idCounter, restPath, type;
          restPath = url;
          type = dataUtilsService.type(restPath);
          collection = new Collection(restPath, query);
          id = collection.id;
          idCounter = 1;
          response.forEach(function(d) {
            if (!d.hasOwnProperty(id)) {
              return d[id] = idCounter++;
            }
          });
          collection.initial(response);
          return collection;
        };

        return DataService;

      })());
    };

    return Data;

  })();

  angular.module('bbData').provider('dataService', [Data]);

}).call(this);

(function() {
  var DataUtils;

  DataUtils = (function() {
    function DataUtils() {
      var dataUtilsService;
      return new (dataUtilsService = (function() {
        function dataUtilsService() {}

        dataUtilsService.prototype.capitalize = function(string) {
          return string[0].toUpperCase() + string.slice(1).toLowerCase();
        };

        dataUtilsService.prototype.type = function(arg) {
          var a, type;
          a = this.copyOrSplit(arg);
          a = a.filter(function(e) {
            return e !== '*';
          });
          if (a.length % 2 === 0) {
            a.pop();
          }
          type = a.pop();
          if (type === "contents") {
            type = "logchunks";
          }
          return type;
        };

        dataUtilsService.prototype.singularType = function(arg) {
          return this.type(arg).replace(/s$/, '');
        };

        dataUtilsService.prototype.className = function(arg) {
          return this.capitalize(this.singularType(arg));
        };

        dataUtilsService.prototype.classId = function(arg) {
          if (this.singularType(arg) === "forcescheduler") {
            return "name";
          }
          if (this.singularType(arg) === "buildset") {
            return "bsid";
          }
          return this.singularType(arg) + "id";
        };

        dataUtilsService.prototype.socketPath = function(arg) {
          var a, stars;
          a = this.copyOrSplit(arg);
          stars = ['*'];
          if (a.length % 2 === 1) {
            stars.push('*');
          }
          return a.concat(stars).join('/');
        };

        dataUtilsService.prototype.socketPathRE = function(socketPath) {
          return new RegExp("^" + socketPath.replace(/\*/g, "[^/]+") + "$");
        };

        dataUtilsService.prototype.restPath = function(arg) {
          var a;
          a = this.copyOrSplit(arg);
          a = a.filter(function(e) {
            return e !== '*';
          });
          return a.join('/');
        };

        dataUtilsService.prototype.endpointPath = function(arg) {
          var a;
          a = this.copyOrSplit(arg);
          a = a.filter(function(e) {
            return e !== '*';
          });
          if (a.length % 2 === 0) {
            a.pop();
          }
          return a.join('/');
        };

        dataUtilsService.prototype.copyOrSplit = function(arrayOrString) {
          if (angular.isArray(arrayOrString)) {
            return arrayOrString.slice(0);
          } else if (angular.isString(arrayOrString)) {
            return arrayOrString.split('/');
          } else {
            throw new TypeError("Parameter 'arrayOrString' must be a array or a string, not " + (typeof arrayOrString));
          }
        };

        dataUtilsService.prototype.unWrap = function(object, path) {
          return object[this.type(path)];
        };

        dataUtilsService.prototype.splitOptions = function(args) {
          var accessor, last, query, subscribe;
          args = args.filter(function(e) {
            return e != null;
          });
          query = {};
          last = args[args.length - 1];
          subscribe = accessor = null;
          if (angular.isObject(last)) {
            query = args.pop();
          }
          return [args, query];
        };

        dataUtilsService.prototype.parse = function(object) {
          var error, k, v;
          for (k in object) {
            v = object[k];
            try {
              object[k] = angular.fromJson(v);
            } catch (error1) {
              error = error1;
            }
          }
          return object;
        };

        dataUtilsService.prototype.numberOrString = function(str) {
          var number;
          if (str == null) {
            str = null;
          }
          if (angular.isNumber(str)) {
            return str;
          }
          number = parseInt(str, 10);
          if (!isNaN(number)) {
            return number;
          } else {
            return str;
          }
        };

        dataUtilsService.prototype.emailInString = function(string) {
          var emailRegex;
          if (!angular.isString(string)) {
            throw new TypeError("Parameter 'string' must be a string, not " + (typeof string));
          }
          emailRegex = /[a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/;
          try {
            return emailRegex.exec(string).pop() || '';
          } catch (error1) {
            return '';
          }
        };

        return dataUtilsService;

      })());
    }

    return DataUtils;

  })();

  angular.module('bbData').service('dataUtilsService', [DataUtils]);

}).call(this);

(function() {
  var Rest,
    slice = [].slice;

  Rest = (function() {
    function Rest($http, $q, API) {
      var RestService;
      return new (RestService = (function() {
        function RestService() {}

        RestService.prototype.execute = function(config) {
          return $q(function(resolve, reject) {
            return $http(config).success(function(response) {
              var data, e;
              try {
                data = angular.fromJson(response);
                return resolve(data);
              } catch (error) {
                e = error;
                return reject(e);
              }
            }).error(function(reason) {
              return reject(reason);
            });
          });
        };

        RestService.prototype.get = function(url, params) {
          var config;
          if (params == null) {
            params = {};
          }
          config = {
            method: 'GET',
            url: this.parse(API, url),
            params: params,
            headers: {
              'Accept': 'application/json'
            }
          };
          return this.execute(config);
        };

        RestService.prototype.post = function(url, data) {
          var config;
          if (data == null) {
            data = {};
          }
          config = {
            method: 'POST',
            url: this.parse(API, url),
            data: data,
            headers: {
              'Content-Type': 'application/json'
            }
          };
          return this.execute(config);
        };

        RestService.prototype.parse = function() {
          var args;
          args = 1 <= arguments.length ? slice.call(arguments, 0) : [];
          return args.join('/').replace(/\/\//, '/');
        };

        return RestService;

      })());
    }

    return Rest;

  })();

  angular.module('bbData').service('restService', ['$http', '$q', 'API', Rest]);

}).call(this);

(function() {
  var Socket;

  Socket = (function() {
    function Socket($log, $q, $rootScope, $location, Stream, webSocketService) {
      var SocketService;
      return new (SocketService = (function() {
        SocketService.prototype.eventStream = null;

        function SocketService() {
          this.queue = [];
          this.deferred = {};
          this.subscribers = {};
          this.open();
        }

        SocketService.prototype.open = function() {
          if (this.socket == null) {
            this.socket = webSocketService.getWebSocket(this.getUrl());
          }
          this.socket.onopen = (function(_this) {
            return function() {
              return _this.flush();
            };
          })(this);
          return this.setupEventStream();
        };

        SocketService.prototype.setupEventStream = function() {
          if (this.eventStream == null) {
            this.eventStream = new Stream();
          }
          return this.socket.onmessage = (function(_this) {
            return function(message) {
              var data, e, id, ref, ref1, ref2;
              try {
                data = angular.fromJson(message.data);
                if (data.code != null) {
                  id = data._id;
                  if (data.code === 200) {
                    return (ref = _this.deferred[id]) != null ? ref.resolve(true) : void 0;
                  } else {
                    return (ref1 = _this.deferred[id]) != null ? ref1.reject(data) : void 0;
                  }
                } else {
                  return $rootScope.$applyAsync(function() {
                    return _this.eventStream.push(data);
                  });
                }
              } catch (error) {
                e = error;
                return (ref2 = _this.deferred[id]) != null ? ref2.reject(e) : void 0;
              }
            };
          })(this);
        };

        SocketService.prototype.close = function() {
          return this.socket.close();
        };

        SocketService.prototype.send = function(data) {
          var base, id;
          id = this.nextId();
          data._id = id;
          if ((base = this.deferred)[id] == null) {
            base[id] = $q.defer();
          }
          data = angular.toJson(data);
          if (this.socket.readyState === (this.socket.OPEN || 1)) {
            this.socket.send(data);
          } else {
            this.queue.push(data);
          }
          return this.deferred[id].promise;
        };

        SocketService.prototype.flush = function() {
          var data, results;
          results = [];
          while (data = this.queue.pop()) {
            results.push(this.socket.send(data));
          }
          return results;
        };

        SocketService.prototype.nextId = function() {
          if (this.id == null) {
            this.id = 0;
          }
          this.id = this.id < 1000 ? this.id + 1 : 0;
          return this.id;
        };

        SocketService.prototype.getRootPath = function() {
          return location.pathname;
        };

        SocketService.prototype.getUrl = function() {
          var defaultport, host, path, port, protocol;
          host = $location.host();
          protocol = $location.protocol() === 'https' ? 'wss' : 'ws';
          defaultport = $location.protocol() === 'https' ? 443 : 80;
          path = this.getRootPath();
          port = $location.port() === defaultport ? '' : ':' + $location.port();
          return protocol + "://" + host + port + path + "ws";
        };

        SocketService.prototype.subscribe = function(eventPath, collection) {
          var base, l;
          l = (base = this.subscribers)[eventPath] != null ? base[eventPath] : base[eventPath] = [];
          l.push(collection);
          if (l.length === 1) {
            return this.send({
              cmd: "startConsuming",
              path: eventPath
            });
          }
          return $q.resolve();
        };

        SocketService.prototype.unsubscribe = function(eventPath, collection) {
          var base, l, pos;
          l = (base = this.subscribers)[eventPath] != null ? base[eventPath] : base[eventPath] = [];
          pos = l.indexOf(collection);
          if (pos >= 0) {
            l.splice(pos, 1);
            if (l.length === 0) {
              return this.send({
                cmd: "stopConsuming",
                path: eventPath
              });
            }
          }
          return $q.resolve();
        };

        return SocketService;

      })());
    }

    return Socket;

  })();

  angular.module('bbData').service('socketService', ['$log', '$q', '$rootScope', '$location', 'Stream', 'webSocketService', Socket]);

}).call(this);

(function() {
  var WebSocketBackend;

  WebSocketBackend = (function() {
    var MockWebSocket, self;

    self = null;

    function WebSocketBackend() {
      self = this;
      this.webSocket = new MockWebSocket();
    }

    WebSocketBackend.prototype.sendQueue = [];

    WebSocketBackend.prototype.receiveQueue = [];

    WebSocketBackend.prototype.send = function(message) {
      var data;
      data = {
        data: message
      };
      return this.sendQueue.push(data);
    };

    WebSocketBackend.prototype.flush = function() {
      var message, results;
      results = [];
      while (message = this.sendQueue.shift()) {
        results.push(this.webSocket.onmessage(message));
      }
      return results;
    };

    WebSocketBackend.prototype.getWebSocket = function() {
      return this.webSocket;
    };

    MockWebSocket = (function() {
      function MockWebSocket() {}

      MockWebSocket.prototype.OPEN = 1;

      MockWebSocket.prototype.send = function(message) {
        return self.receiveQueue.push(message);
      };

      MockWebSocket.prototype.close = function() {
        return typeof this.onclose === "function" ? this.onclose() : void 0;
      };

      return MockWebSocket;

    })();

    return WebSocketBackend;

  })();

  angular.module('bbData').service('webSocketBackendService', [WebSocketBackend]);

}).call(this);

(function() {
  var WebSocket;

  WebSocket = (function() {
    function WebSocket($window) {
      var WebSocketProvider;
      return new (WebSocketProvider = (function() {
        function WebSocketProvider() {}

        WebSocketProvider.prototype.getWebSocket = function(url) {
          var match;
          match = /wss?:\/\//.exec(url);
          if (!match) {
            throw new Error('Invalid url provided');
          }
          if ($window.ReconnectingWebSocket != null) {
            return new $window.ReconnectingWebSocket(url);
          } else {
            return new $window.WebSocket(url);
          }
        };

        return WebSocketProvider;

      })());
    }

    return WebSocket;

  })();

  angular.module('bbData').service('webSocketService', ['$window', WebSocket]);

}).call(this);

(function() {
  var Stream;

  Stream = (function() {
    function Stream() {
      var StreamInstance;
      return StreamInstance = (function() {
        function StreamInstance() {}

        StreamInstance.prototype.onUnsubscribe = null;

        StreamInstance.prototype.listeners = [];

        StreamInstance.prototype.subscribe = function(listener) {
          if (!angular.isFunction(listener)) {
            throw new TypeError("Parameter 'listener' must be a function, not " + (typeof listener));
          }
          listener.id = this.generateId();
          this.listeners.push(listener);
          return (function(_this) {
            return function() {
              var i, removed;
              i = _this.listeners.indexOf(listener);
              removed = _this.listeners.splice(i, 1);
              if (angular.isFunction(_this.onUnsubscribe)) {
                return _this.onUnsubscribe(listener);
              }
            };
          })(this);
        };

        StreamInstance.prototype.push = function(data) {
          var j, len, listener, ref, results;
          ref = this.listeners;
          results = [];
          for (j = 0, len = ref.length; j < len; j++) {
            listener = ref[j];
            results.push(listener(data));
          }
          return results;
        };

        StreamInstance.prototype.destroy = function() {
          var results;
          results = [];
          while (this.listeners.length > 0) {
            results.push(this.listeners.pop());
          }
          return results;
        };

        StreamInstance.prototype.generateId = function() {
          if (this.lastId == null) {
            this.lastId = 0;
          }
          return this.lastId++;
        };

        return StreamInstance;

      })();
    }

    return Stream;

  })();

  angular.module('bbData').factory('Stream', [Stream]);

}).call(this);

(function() {
  var Collection,
    bind = function(fn, me){ return function(){ return fn.apply(me, arguments); }; },
    extend = function(child, parent) { for (var key in parent) { if (hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; },
    hasProp = {}.hasOwnProperty,
    indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  Collection = (function() {
    function Collection($q, $injector, $log, dataUtilsService, socketService, DataQuery, $timeout) {
      var CollectionInstance;
      angular.isArray = Array.isArray = function(arg) {
        return arg instanceof Array;
      };
      return CollectionInstance = (function(superClass) {
        extend(CollectionInstance, superClass);

        function CollectionInstance(restPath, query, accessor) {
          var className, e, ref;
          this.restPath = restPath;
          this.query = query != null ? query : {};
          this.accessor = accessor;
          this.listener = bind(this.listener, this);
          this.socketPath = dataUtilsService.socketPath(this.restPath);
          this.type = dataUtilsService.type(this.restPath);
          this.id = dataUtilsService.classId(this.restPath);
          this.endpoint = dataUtilsService.endpointPath(this.restPath);
          this.socketPathRE = dataUtilsService.socketPathRE(this.socketPath);
          this.queryExecutor = new DataQuery(this.query);
          this.onUpdate = angular.noop;
          this.onNew = angular.noop;
          this.onChange = angular.noop;
          this._new = [];
          this._updated = [];
          this._byId = {};
          this.$resolved = false;
          try {
            className = dataUtilsService.className(this.restPath);
            this.WrapperClass = $injector.get(className);
          } catch (error) {
            e = error;
            console.log("unknown wrapper for", className);
            this.WrapperClass = $injector.get('Base');
          }
          socketService.eventStream.subscribe(this.listener);
          if ((ref = this.accessor) != null) {
            ref.registerCollection(this);
          }
        }

        CollectionInstance.prototype.then = function(callback) {
          console.log("Should not use collection as a promise. Callback will be called several times!");
          return this.onChange = callback;
        };

        CollectionInstance.prototype.getArray = function() {
          console.log("getArray() is deprecated. dataService.get() directly returns the collection!");
          return this;
        };

        CollectionInstance.prototype.get = function(id) {
          return this._byId[id];
        };

        CollectionInstance.prototype.hasOwnProperty = function(id) {
          return this._byId.hasOwnProperty(id);
        };

        CollectionInstance.prototype.listener = function(data) {
          var key, message;
          key = data.k;
          message = data.m;
          if (this.socketPathRE.test(key)) {
            this.put(message);
            this.recomputeQuery();
            return this.sendEvents();
          }
        };

        CollectionInstance.prototype.subscribe = function() {
          return socketService.subscribe(this.socketPath, this);
        };

        CollectionInstance.prototype.close = function() {
          return socketService.unsubscribe(this.socketPath, this);
        };

        CollectionInstance.prototype.initial = function(data) {
          var i, j, len;
          this.$resolved = true;
          for (j = 0, len = data.length; j < len; j++) {
            i = data[j];
            if (!this.hasOwnProperty(i[this.id])) {
              this.put(i);
            }
          }
          this.recomputeQuery();
          return this.sendEvents({
            initial: true
          });
        };

        CollectionInstance.prototype.from = function(data) {
          var i, j, len;
          for (j = 0, len = data.length; j < len; j++) {
            i = data[j];
            this.put(i);
          }
          this.recomputeQuery();
          return this.sendEvents();
        };

        CollectionInstance.prototype.item = function(i) {
          return this[i];
        };

        CollectionInstance.prototype.add = function(element) {
          var instance;
          if (this.queryExecutor.filter([element]).length === 0) {
            return;
          }
          instance = new this.WrapperClass(element, this.endpoint);
          instance.setAccessor(this.accessor);
          instance.$collection = this;
          this._new.push(instance);
          this._byId[instance[this.id]] = instance;
          return this.push(instance);
        };

        CollectionInstance.prototype.put = function(element) {
          var j, len, old, ref;
          ref = this;
          for (j = 0, len = ref.length; j < len; j++) {
            old = ref[j];
            if (old[this.id] === element[this.id]) {
              old.update(element);
              this._updated.push(old);
              return;
            }
          }
          return this.add(element);
        };

        CollectionInstance.prototype.clear = function() {
          var results;
          results = [];
          while (this.length > 0) {
            results.push(this.pop());
          }
          return results;
        };

        CollectionInstance.prototype["delete"] = function(element) {
          var index;
          index = this.indexOf(element);
          if (index > -1) {
            return this.splice(index, 1);
          }
        };

        CollectionInstance.prototype.recomputeQuery = function() {
          return this.queryExecutor.computeQuery(this);
        };

        CollectionInstance.prototype.sendEvents = function(opts) {
          var _new, _updated;
          _new = this._new;
          _updated = this._updated;
          this._updated = [];
          this._new = [];
          return $timeout((function(_this) {
            return function() {
              var changed, i, j, k, len, len1;
              changed = false;
              for (j = 0, len = _new.length; j < len; j++) {
                i = _new[j];
                if (indexOf.call(_this, i) >= 0) {
                  _this.onNew(i);
                  changed = true;
                }
              }
              for (k = 0, len1 = _updated.length; k < len1; k++) {
                i = _updated[k];
                if (indexOf.call(_this, i) >= 0) {
                  _this.onUpdate(i);
                  changed = true;
                }
              }
              if (changed || (opts != null ? opts.initial : void 0)) {
                return _this.onChange(_this);
              }
            };
          })(this), 0);
        };

        return CollectionInstance;

      })(Array);
    }

    return Collection;

  })();

  angular.module('bbData').factory('Collection', ['$q', '$injector', '$log', 'dataUtilsService', 'socketService', 'DataQuery', '$timeout', Collection]);

}).call(this);

(function() {
  var DataQuery,
    indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  DataQuery = (function() {
    function DataQuery($http, $q, API) {
      var DataQueryClass;
      return DataQueryClass = (function() {
        function DataQueryClass(query) {
          var fieldAndOperator, value;
          if (query == null) {
            query = {};
          }
          this.query = query;
          this.filters = {};
          for (fieldAndOperator in query) {
            value = query[fieldAndOperator];
            if (['field', 'limit', 'offset', 'order', 'property'].indexOf(fieldAndOperator) < 0) {
              if (['on', 'true', 'yes'].indexOf(value) > -1) {
                value = true;
              } else if (['off', 'false', 'no'].indexOf(value) > -1) {
                value = false;
              }
              this.filters[fieldAndOperator] = value;
            }
          }
        }

        DataQueryClass.prototype.computeQuery = function(array) {
          var limit, order, ref, ref1;
          this.filter(array);
          order = (ref = this.query) != null ? ref.order : void 0;
          this.sort(array, order);
          limit = (ref1 = this.query) != null ? ref1.limit : void 0;
          return this.limit(array, limit);
        };

        DataQueryClass.prototype.isFiltered = function(v) {
          var cmp, field, fieldAndOperator, operator, ref, ref1, value;
          cmp = false;
          ref = this.filters;
          for (fieldAndOperator in ref) {
            value = ref[fieldAndOperator];
            ref1 = fieldAndOperator.split('__'), field = ref1[0], operator = ref1[1];
            switch (operator) {
              case 'ne':
                cmp = v[field] !== value;
                break;
              case 'lt':
                cmp = v[field] < value;
                break;
              case 'le':
                cmp = v[field] <= value;
                break;
              case 'gt':
                cmp = v[field] > value;
                break;
              case 'ge':
                cmp = v[field] >= value;
                break;
              default:
                cmp = v[field] === value || (angular.isArray(v[field]) && indexOf.call(v[field], value) >= 0) || v["_" + field] === value || (angular.isArray(v["_" + field]) && indexOf.call(v["_" + field], value) >= 0);
            }
            if (!cmp) {
              return false;
            }
          }
          return true;
        };

        DataQueryClass.prototype.filter = function(array) {
          var i, results, v;
          i = 0;
          results = [];
          while (i < array.length) {
            v = array[i];
            if (this.isFiltered(v)) {
              results.push(i += 1);
            } else {
              results.push(array.splice(i, 1));
            }
          }
          return results;
        };

        DataQueryClass.prototype.sort = function(array, order) {
          var compare;
          compare = function(property) {
            var reverse;
            reverse = false;
            if (property[0] === '-') {
              property = property.slice(1);
              reverse = true;
            }
            return function(a, b) {
              var ref;
              if (reverse) {
                ref = [b, a], a = ref[0], b = ref[1];
              }
              if (a[property] < b[property]) {
                return -1;
              } else if (a[property] > b[property]) {
                return 1;
              } else {
                return 0;
              }
            };
          };
          if (angular.isString(order)) {
            return array.sort(compare(order));
          } else if (angular.isArray(order)) {
            return array.sort(function(a, b) {
              var f, j, len, o;
              for (j = 0, len = order.length; j < len; j++) {
                o = order[j];
                f = compare(o)(a, b);
                if (f) {
                  return f;
                }
              }
              return 0;
            });
          }
        };

        DataQueryClass.prototype.limit = function(array, limit) {
          var results;
          results = [];
          while (array.length > limit) {
            results.push(array.pop());
          }
          return results;
        };

        return DataQueryClass;

      })();
    }

    return DataQuery;

  })();

  angular.module('bbData').factory('DataQuery', ['$http', '$q', 'API', DataQuery]);

}).call(this);

//# sourceMappingURL=buildbot-data.js.map
