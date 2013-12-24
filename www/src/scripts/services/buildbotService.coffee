angular.module('app').service 'singulars', ['plurals', (plurals) ->
    ret = {}
    for k, v of plurals
        ret[v] = k
    return ret
]
jsonrpc2_id = 1
angular.module('app').factory 'buildbotService',
['$log', 'Restangular', 'mqService', '$rootScope', 'BASEURLAPI',
    'BASEURLSSE', 'plurals', 'singulars', '$q',
    ($log, Restangular, mqService, $rootScope, BASEURLAPI, BASEURLSSE, plurals, singulars, $q ) ->
        getIdFromElem = (elem) ->
          return elem[elem.route + "id"]
        responseExtractor =  (response, operation) ->
            # for now, we only support one resource type per request
            # we'll have to figure out how to support aggregated response at
            # some point because this will be a big improve in latency
            # so we return the first elem that is not "meta"
            for k, v of response
                if singulars.hasOwnProperty(k)
                    id = singulars[k] + "id"
                    for value in v
                        value["id"] = value[id]
                        value["_raw_data"] = angular.copy(value)
                    if operation == "getList"
                        return v
                    else
                        return v[0]
            throw Error("got unexpected value from data api: #{JSON.stringify(response)}," +
                        " expected one of #{JSON.stringify(singulars)}")

        onElemRestangularized = (elem, isCollection, route, Restangular) ->
            idkey = elem.route + "id"
            elem.bind = ($scope, opts) ->
                defaults_opts =
                    dest_key: elem.route
                    dest: $scope
                    subElement: undefined
                    queryParams: undefined
                    ismutable: -> false
                    onchild: ->
                if isCollection
                    defaults_opts.dest_key = plurals[defaults_opts.dest_key]
                opts = _.extend(defaults_opts, opts)

                if (isCollection)
                    onNewOrChange = (msg) ->
                        l = opts.dest[opts.dest_key]
                        # de-duplicate, if the element is already there
                        for e in l
                            if e[idkey] == msg[idkey]
                                for k, v of msg
                                    e[k] = v
                                return

                        # restangularize the object before putting it in
                        # this allows controllers to get more data within onchild()
                        newobj = _.assign(elem.one(msg[idkey]), msg)
                        # @todo, on new events, need to re-filter through queryParams..
                        l.push(newobj)
                        opts.onchild(newobj)

                    p = elem.getList(opts.queryParams).then (res) ->
                        opts.dest[opts.dest_key] = res
                        for child in res
                            opts.onchild(child)
                        elem.on("*/new", onNewOrChange, $scope)
                        elem.on("*/update", onNewOrChange, $scope)
                        return res
                else
                    onUpdate = (msg) ->
                        for k, v of msg
                            opts.dest[opts.dest_key][k] = v

                    p = this.get().then (res) ->
                        opts.dest[opts.dest_key] = res
                        if opts.ismutable(res)
                            elem.on("update", onUpdate, $scope)
                        return res
                return p

            elem.on = (event, onEvent, $scope) ->
                path = elem.getRestangularUrl().replace(BASEURLAPI,"")
                return mqService.on( path + "/" + event, onEvent)

            elem.control = (method, params) ->
                # do jsonrpc2.0 like POST
                id = jsonrpc2_id++
                req =
                    method: method
                    id: id
                    params: params
                    jsonrpc: "2.0"
                return elem.post("", req)

            return elem
        configurer = (RestangularConfigurer) ->
            RestangularConfigurer.setBaseUrl(BASEURLAPI)
            RestangularConfigurer.setOnElemRestangularized(onElemRestangularized)
            RestangularConfigurer.setResponseExtractor(responseExtractor)
            RestangularConfigurer.getIdFromElem = getIdFromElem
            mqService.setBaseUrl(BASEURLSSE)

        self = Restangular.withConfig(configurer)
        self.bindHierarchy = ($scope, $stateParams, paths) ->
            r = self
            l = []
            for path in paths
                r = r.one(path, $stateParams[path])
                l.push(r.bind($scope))
            return $q.all(l)
        return self

]
