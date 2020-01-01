// test goal: checks the capability to navigate on about web page
// to use previous and next link

import { AboutPage } from './pages/about';

describe('', function() {
    let about = null;

    beforeEach(() => about = new AboutPage('runtests'));


    describe('check about page', () =>
        it('should navigate to the about page, check the default elements inside', async () => {
            await about.goAbout();
            await about.checkBuildbotTitle();
            await about.checkConfigTitle();
            await about.checkAPIDescriptionTitle();
    })
);
});
