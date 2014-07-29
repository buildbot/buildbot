# adaptation file to run our application's main inside the karma webserver
if window.__karma__?
    requirejs.config(
        baseUrl: '/base/.temp/scripts'
        deps: ["main"]
        callback: window.__karma__.start
    )