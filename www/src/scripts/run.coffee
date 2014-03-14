# this is the last loaded file of the app.

# actually not... we load the plugins
# and then bootstrap angular

angular.module('app').run
['$rootScope', '$log', ($rootScope, $log) ->
    # fire an event related to the current route
    $rootScope.$on '$routeChangeSuccess', (event, currentRoute, priorRoute) ->
        $rootScope.$broadcast "#{currentRoute.controller}$routeChangeSuccess",
                              currentRoute, priorRoute
]


plugins_modules = []
plugins_paths = {}
config = @config
@config = undefined  # prevent modules to access config via the global variable
config ?= {plugins: {}, url: "", devmode: true}

# load plugins's css (async)
for plugin, cfg of config.plugins
    link = document.createElement("link")
    link.type = "text/css"
    link.rel = "stylesheet"
    link.href = "#{plugin}/styles.css"
    document.getElementsByTagName("head")[0].appendChild(link)

    plugins_modules.push("#{plugin}/main")
    plugins_paths[plugin] = config.url + "#{plugin}"
    angular.module('app').constant("#{plugin}_config", cfg)

# make the config global variable accessible as a DI module
# so that it can be mocked in tests
angular.module('app').constant("config", config)

requirejs.config
    paths: plugins_paths
# loads the plugin js modules, and the start angular magic
require(plugins_modules, ->
    if window.__karma__?
        window.__karma__.start()
    else
        if config.devmode?
            app = 'devapp'
        else
            app = 'app'
        angular.bootstrap document, [ app ]
)
