/*global define*/
define('login', ["jquery"], function ($) {
    "use strict";

    var login = {
        errorMessage: function errorMessage(form, $loginBox, error, errorMsg) {
            var errorInput = $('.error-input');
            errorMsg = errorMsg === '' ? "Fill in your username and password before submitting" : "Incorrect username or password";

            if (error === true && errorInput.length === 0) {
                $('.login-welcome-txt', $loginBox).hide();
                $(form).prepend('<div class="error-input">' + errorMsg + '</div>');
                this.shake($loginBox);

            } else if (error === true && errorInput.length > 0) {
                errorMsg = 'Fill in your username and password before submitting';
                $('.error-input', form).remove();
                $(form).prepend('<div class="error-input">' + errorMsg + '</div>');
                this.shake($loginBox);

            } else {
                this.shake($loginBox, 'remove');
            }
        },
        validateLoginFields: function validateLoginFields(form, loginBox, allInputs, e) {
            var error = false;
            $(allInputs).each(function () {

                if ($(this).val() === '') {
                    e.preventDefault();
                    $(this).addClass('not-valid');
                    error = true;
                }
            });

            // display error message if there is an error
            this.errorMessage(form, loginBox, error);
        },
        shake: function shake(element, rm) {
            if (!rm) {
                element.removeClass('shake');
                element.addClass('shake');
            } else {
                element.removeClass('shake');
            }
        }
    };

    $(document).ready(function () {

        // variables for elements
        var loginBox = $('.login-box');
        var form = $('#loginForm');
        var excludeFields = ':button, :hidden, :checkbox, :submit';
        var allInputs = $('input', form).not(excludeFields);


        // the current url
        var url = window.location;

        // Does the url have 'authorized' ?
        if (url.search.match(/auth_fail=True/) !== null) {
            // give error message if user or password is incorrect
            login.errorMessage(form, loginBox, true, 'incorrect');
        }

        $.fn.center = function () {
            this.css("position", "absolute");
            this.css("top", ($(window).height() - this.outerHeight()) / 2 + $(window).scrollTop() + "px");
            this.css("left", ($(window).width() - this.outerWidth()) / 2 + $(window).scrollLeft() + "px");
            return this;
        };

        $(window).resize(function () {
            $('.more-info-box-js').center();
        });

        $('.more-info-box-js').center();


        // Mark input field red if empty on focus out
        $(allInputs).each(function () {
            $(this).focusout(function () {
                if ($(this).val() === '') {
                    $(this).addClass('not-valid');
                    login.errorMessage(form, loginBox, true);
                } else {
                    $(this).removeClass('not-valid');
                    login.errorMessage(form, loginBox);
                }
            });
        });


        // Submit the form
        $(form).submit(function (e) {
            var value = $('#loginForm');

            login.validateLoginFields(value, loginBox, allInputs, e);

        });
    });
});