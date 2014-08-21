/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var slaveHealth = require('text!templates/partials/slave-health.hbs'),
        buildersPopup = require('text!templates/partials/builders-popup.hbs');

    require('handlebars');

    function registerPartials() {
        Handlebars.registerPartial('slave:health', slaveHealth);
        Handlebars.registerPartial('slave:builders', buildersPopup);
    }

    function registerHelpers() {
        var healthNames = ["good", "warning", "bad"];

        Handlebars.registerHelper('slave:healthClass', function () {
            return healthNames[-this.health];
        });
    }

    return {
        "init": function init() {
            registerPartials();
            registerHelpers();
        }
    };
});