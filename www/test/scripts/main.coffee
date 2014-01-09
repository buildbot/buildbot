# adaptation file to run our application's main inside the karma webserver
if window.__karma__?
    requirejs.config(
        baseUrl: '/base/buildbot_www/scripts'
        deps: ["main"]
    )
