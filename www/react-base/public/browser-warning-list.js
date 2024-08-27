// this file is not transpiled and included directly to index.html because we must show the browser
// warning even on ancient browsers. The browser list should correspond to the list of browsers
// supporting ES2020 target in https://caniuse.com.
outdatedBrowserRework({
    browserSupport: {
        'Chrome': 80, // Includes Chrome for mobile devices
        'Chromium': 80, // same as Chrome, but needs to be listed explicitly
                        // (https://github.com/mikemaccana/outdated-browser-rework/issues/49)
        'Edge': 80,
        'Safari': 14,
        'Mobile Safari': 14,
        'Firefox': 80,
        'Opera': 67,
        'IE': false
    },
    requireChromeOnAndroid: false,
    isUnknownBrowserOK: true,
});
