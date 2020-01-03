// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link

import { BuilderPage } from './pages/builder';
import { WaterfallPage } from './pages/waterfall';
import { SettingsPage } from './pages/settings';

describe('manage settings', function() {
    let builder = null;
    let waterfall = null;
    let settings = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        waterfall = new WaterfallPage('runtests');
        settings =  new SettingsPage('runtests');
        return builder.goBuildersList();
    });

    describe('waterfall', () => {
        const scalingFactor = '10';
        it('change the "scalling factor" and check it', async () => {
            await settings.goSettings();
            await settings.changeScallingFactor(scalingFactor);
            await waterfall.go();
            await settings.goSettings();
            await settings.checkScallingFactor(scalingFactor);
        })

        const scalingWidth = '450';
        it('change the "minimum column width" and check it', async () => {
            await settings.goSettings();
            await settings.changeColumnWidth(scalingWidth);
            await waterfall.go();
            await settings.goSettings();
            await settings.checkColumnWidth(scalingWidth);
        })

        const lazyLoadingLimit = '30';
        it('change the "lazy loading limit" and check it', async () => {
            await settings.goSettings();
            await settings.changeLazyLoadingLimit(lazyLoadingLimit);
            await waterfall.go();
            await settings.goSettings();
            await settings.checkLazyLoadingLimit(lazyLoadingLimit);
        })

        const idleTimeThreshold = '15';
        it('change the "idle time threshold" and check it', async () => {
            await settings.goSettings();
            await settings.changeIdleTime(idleTimeThreshold);
            await waterfall.go();
            await settings.goSettings();
            await settings.checkIdleTime(idleTimeThreshold);
        })
    });

    describe('console', () => {
        const buildsToFetch = '130';
        it('change the "number of builds to fetch" and check it', async () => {
            await settings.goSettings();
            await settings.changeMaxBuild(buildsToFetch);
            await waterfall.go();
            await settings.goSettings();
            await settings.checkMaxBuild(buildsToFetch);
        })

        const changesToFetch='45';
        it('change the "number of changes to fetch" and check it', async () => {
            await settings.goSettings();
            await settings.changeMaxRecentsBuilders(changesToFetch);
            await waterfall.go();
            await settings.goSettings();
            await settings.checkMaxRecentsBuilders(changesToFetch);
        })
    });
});
