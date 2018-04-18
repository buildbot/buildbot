// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


const forcePage = require('./pages/force.js');
const builderPage = require('./pages/builder.js');
const waterfallPage = require('./pages/waterfall.js');
const homePage = require('./pages/home.js');
const settingsPage = require('./pages/settings.js');

describe('waterfall', function() {
    let force = null;
    let builder = null;
    let waterfall = null;

    beforeEach(function() {
        builder = new builderPage('runtests', 'force');
        force =  new forcePage();
        waterfall = new waterfallPage('runtests');
        const settings =  new settingsPage('runtests');
        settings.goSettings();
        settings.changeScallingFactor('10');
        settings.changeColumnWidth('45');
    });

    afterEach(() => new homePage().waitAllBuildsFinished());

    it('should navigate to the waterfall, check one builder and hyperlink', function() {
        waterfall.go();
        waterfall.goBuilderAndCheck('runtests');
    });

    it('should navigate to the builds waterfall and check the associated hyperlink', function() {
        waterfall.go();
        waterfall.goBuildAndCheck();
    });

    it('should navigate to the builds waterfall and open the popup and close it', function() {
        waterfall.go();
        waterfall.goBuildAndClose();
    });
});
