/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// coffee script
// test goal: checks the capability to navigate on about web page
// to use previous and next link

const aboutPage = require('./pages/about.coffee');

describe('', function() {
    let about = null;

    beforeEach(() => about = new aboutPage('runtests'));


    return describe('check about page', () =>
        it('should navigate to the about page, check the default elements inside', function() {
            about.goAbout();
            about.checkAboutPage();
            about.checkBuildbotTitle();
            about.checkConfigTitle();
            return about.checkDependenciesTitle();
    })
);
});
