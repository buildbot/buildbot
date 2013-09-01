angular.module('app').constant("route_config",
    home:
        caption: "Home"
        route: "/"
    builders:
        caption: "Builders"
        route: "/builders"
    lastbuilds:
        caption: "Last Builds"
        route: "/lastbuilds"
    changes:
        caption: "Last Changes"
        route: "/changes"
    buildslaves:
        caption: "Build Slaves"
        route: "/buildslaves"
    buildmasters:
        caption: "Build Masters"
        route: "/buildmasters"
    schedulers:
        caption: "Schedulers"
        route: "/schedulers"
    users:
        caption: "Users"
        route: "/users"
    admin:
        caption: "Admin"
        route: "/admin"
    about:
        caption: "About"
        route: "/about"


    builder:
        route: "/builders/:builder"
        tabid: "builders"
    build:
        route: "/builders/:builder/build/:build"
        tabid: "builders"
    step:
        route: "/builders/:builder/build/:build/steps/:step"
        tabid: "builders"
    log:
        route: "/builders/:builder/build/:build/steps/:step/logs/:log"
        tabid: "builders"

    buildslave:
        route: "/buildslaves/:buildslave"
        tabid: "buildslaves"
    buildmaster:
        route: "/buildmasters/:buildmaster"
        tabid: "buildmasters"
    user:
        route: "/users/:user"
        tabid: "users"

    editconf:
        route: "/admin/:conffile"
        tabid: "admin"
)
route_config_fn = ($routeProvider, route_config, plugins_routes...) ->
    # agregate the base app route_config with plugin route config
    # :-/ need to watch for namespace clashes between plugins...
    for i in [0..plugins_routes.length - 1]
        plugin = plugin_names[i]
        plugin_routes = plugins_routes[i]
        for id, route_cfg of plugin_routes
            route_config[id] = route_cfg
            if !route_cfg.templateUrl
                route_cfg.templateUrl = "#{plugin}/views/#{id}.html"

    # by convention, the key of the first mapping
    # is the name of the template and of the controller
    # If the route has a caption, it is linked in the top menu
    # The route is configured in $routeProvider
    $.each route_config, (id, cfg) ->
        # needs to be a $.each to create a scope for changeTab..
        cfg.tabid ?= id
        cfg.tabhash = "##{id}"
        if !cfg.controller
            cfg.controller = "#{id}Controller"
        if !cfg.templateUrl
            cfg.templateUrl = "views/#{id}.html"
        $routeProvider
        .when cfg.route,
                controller: cfg.controller
                reloadOnSearch: true
                templateUrl: cfg.templateUrl
                resolve:
                        changeTab: ['$rootScope', ($rootScope) ->
                            $rootScope.selectedTab = cfg
                        ]
    $routeProvider.otherwise redirectTo: '/'

# generate the dependancy injection dynamically, given all plugins
di = ['$routeProvider', 'route_config']
plugin_names = []
if @config?
    for plugin, cfg of @config.plugins
        di.push(plugin + "_route_config")
        plugin_names.push(plugin)

di.push(route_config_fn)
angular.module('app').config(di)
