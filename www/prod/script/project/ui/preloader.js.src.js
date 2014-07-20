/*global define*/
define(["jquery", "jquery-ui"], function ($) {
    

    // Create a stateful widget for preloaders

    $.widget("katana.preloader", {
        options: {
            destroyAfter: false,
            autoShow: true,
            timeout: 30000
        },

        _create: function () {
            //TODO: Can we make this less complicated?
            this.element.append($("<div/>").
                attr("id", "bowl_ringG").
                append($("<div/>").addClass("ball_holderG").
                    append($("<div/>").addClass("ballG"))))
                .hide();

            if (this.options.autoShow) {
                this.showPreloader();
            }
        },
        destroy: function () {
            this._clearTimeout();
            this.element.find("div#bowl_ringG").remove();

            // Call the base destroy function
            $.Widget.prototype.destroy.call(this);
        },
        showPreloader: function () {
            this._clearTimeout();
            this.element.show();
            this.timeout = this._delay(this.hidePreloader, this.options.timeout);
        },
        hidePreloader: function () {
            this._clearTimeout();
            this.element.hide();
            if (this.options.destroyAfter) {
                this.element.remove();
            }
            this._destroy();
        },
        _clearTimeout: function () {
            if (this.timeout !== undefined) {
                clearTimeout(this.timeout);
                this.timeout = undefined;
            }
        }
    });
});
