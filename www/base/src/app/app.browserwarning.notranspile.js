// this file is not transpiled and included direcly to index.html because we must show the browser
// warning even on ancient browsers. The browser list here must correspond to the browser list in
// babel config which is located at www/build_common/src/webpack.js
outdatedBrowserRework({
    browserSupport: {
        'Chrome': 56, // Includes Chrome for mobile devices
        'Chromium': 56, // same as Chrome, but needs to be listed explicitly
                        // (https://github.com/mikemaccana/outdated-browser-rework/issues/49)
        'Edge': 13,
        'Safari': 10,
        'Mobile Safari': 10,
        'Firefox': 52,
        'Opera': 43, // uses Chrome 56 internally
        'IE': false
    },
    requireChromeOnAndroid: false,
    isUnknownBrowserOK: true,
});
