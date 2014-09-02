/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var helpers = require('helpers'),
        KT = require('precompiled.handlebars');

    require('handlebars');

    function registerHelpers() {
        var healthNames = ["good", "warning", "bad"];

        Handlebars.registerHelper('slave:healthClass', function () {
            return healthNames[-this.health];
        });

        Handlebars.registerHelper('buildCSSClass', function (value) {
            return helpers.getCssClassFromStatus(value);
        });
    }
    registerHelpers();
    return KT;
});