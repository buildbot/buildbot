// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link

import { BuilderPage } from './pages/builder';
import { WaterfallPage } from './pages/waterfall';
import { SettingsPage } from './pages/settings';

describe('', function() {
    let builder = null;
    let waterfall = null;
    let settings = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        waterfall = new WaterfallPage('runtests');
        settings =  new SettingsPage('runtests');
        return builder.goDefault();
    });

    const scallingVar = '10';
    describe('manage settings', () =>
        it('should navigate to the setting, change the scalling factor and check it', function() {
            settings.goSettings();
            settings.changeScallingFactor(scallingVar);
            waterfall.go();
            settings.goSettings();
            settings.checkScallingFactor(scallingVar);
        })
    );

    const columnVar = '450';
    describe('manage settings', () =>
        it('should navigate to the settings, change the Column Width and check it', function() {
            settings.goSettings();
            settings.changeColumnWidth(columnVar);
            waterfall.go();
            settings.goSettings();
            settings.checkColumnWidth(columnVar);
        })
    );

    const lazyLoadingLimit = '30';
    describe('manage settings', () =>
        it('should navigate to the settings, change the Lazy Loading and check it', function() {
            settings.goSettings();
            settings.changeLazyLoadingLimit(lazyLoadingLimit);
            waterfall.go();
            settings.goSettings();
            return settings.checkLazyLoadingLimit(lazyLoadingLimit);
        })
    );

    const idleTimeVar = '15';
    describe('manage settings', () =>
        it('should navigate to the settings, change the Idle Time value and check it', function() {
            settings.goSettings();
            settings.changeIdleTime(idleTimeVar);
            waterfall.go();
            settings.goSettings();
            return settings.checkIdleTime(idleTimeVar);
        })
    );

    const maxBuildVar = '130';
    describe('manage settings', () =>
        it('should navigate to the settings, change the Max Build value and check it', function() {
            settings.goSettings();
            settings.changeMaxBuild(maxBuildVar);
            waterfall.go();
            settings.goSettings();
            return settings.checkMaxBuild(maxBuildVar);
        })
    );

    const maxBuildersVar='45';
    describe('manage settings', () =>
        it('should navigate to the settings, change the Max Builder value and check it', function() {
            settings.goSettings();
            settings.changeMaxRecentsBuilders(maxBuildersVar);
            waterfall.go();
            settings.goSettings();
            return settings.checkMaxRecentsBuilders(maxBuildersVar);
    })
);
});
