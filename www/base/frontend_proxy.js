#!/usr/bin/env node
'use strict';

const argv = require('minimist')(process.argv);
const fs = require('fs');
const path = require('path');
const http = require('http');
const httpProxy = require('http-proxy');
const child_process = require('child_process');

const baseAppBuildDir = 'buildbot_www/static';
const proxyBuildDir = 'buildbot_www_proxy';

// this is a task for developing, it proxy api request to http://nine.buildbot.net
if (argv.host == null) {
    console.log('Host not set, using nine.buildbot.net as the default');
    argv.host = 'nine.buildbot.net';
}
if (argv.port == null) {
    console.log('Port not set, using 8080 as the default');
    argv.port = 8080;
}
if (argv.secure == null) {
    argv.secure = false;
}
if (argv.ignoresslerrors == null) {
    argv.ignoresslerrors = false;
}

console.log('Creating file tree for the proxy');
console.log(`buildbot processwwwindex --src-dir "${baseAppBuildDir}" ` +
            `--dst-dir "${proxyBuildDir}"`);
child_process.execSync(`buildbot processwwwindex --src-dir "${baseAppBuildDir}" ` +
                       `--dst-dir "${proxyBuildDir}"`, {stdio: 'inherit', stderr: 'inherit'});
console.log('... Done');

const proxy = httpProxy.createProxyServer({
    secure: !argv.ignoresslerrors,
});

proxy.on('proxyReq', function(proxyReq, req, res, options) {
    delete proxyReq.removeHeader('Origin');
    delete proxyReq.removeHeader('Referer');
});

proxy.on('proxyRes', function(proxyRes, req, res) {
    proxyRes.headers['Access-Control-Allow-Origin'] = '*';
    console.log(`[Proxy] ${req.method} ${req.url}`);
});

const server = http.createServer(function(req, res) {
    if (req.url.match(/^\/(api|sse|avatar)/)) {
        return proxy.web(req, res, {target: `http${argv.secure ? 's' : ''}://${argv.host}`});
    } else {
        let filepath = proxyBuildDir + req.url.split('?')[0];
        if (fs.existsSync(filepath) && fs.lstatSync(filepath).isDirectory()) {
            filepath = path.join(filepath, 'index.html');
        }
        return fs.readFile(filepath, function(err, data) {
            if (err) {
                res.writeHead(404);
                return res.end(JSON.stringify(err));
            } else {
                res.writeHead(200);
                return res.end(data);
            }
        });
    }
});

server.on('upgrade', (req, socket, head) => {
    return proxy.ws(req, socket, {target: `ws${argv.secure ? 's' : ''}://${argv.host}`});
});

server.listen(parseInt(argv.port));
console.log(`[Proxy] server listening on port ${argv.port}, ` +
            `target {http${argv.secure ? 's' : ''},ws${argv.secure ? 's' : ''}}` +
            `://${argv.host}/{api,sse,avatar}`);

