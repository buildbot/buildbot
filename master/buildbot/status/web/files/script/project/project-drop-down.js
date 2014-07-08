/*global define, jQuery*/
define(['jquery', 'screensize', 'helpers'], function ($, screenSize, helpers) {

    "use strict";
    //TODO: Put this in a template + make preloader plugin
    var projectDropDown,
        preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';


    // Extend our jquery object with dropdown widget
    (function ($) {
        $.fn.dropdown = function (options) {
            var $elem = $(this),
                $dropdown,
                opts = $.extend({}, $.fn.dropdown.defaults, options),
                isVisible = false,
                clickHandler;
            $elem.settings = opts;

            var dropdownPrivate = {
                init: function () {
                    dropdownPrivate.setupClick();
                },
                setupClick: function () {
                    $elem.click(function () {
                        if ($dropdown === undefined) {
                            if (dropdownPrivate.createHTML()) {
                                opts.onCreate($elem, $dropdown);
                                dropdownPrivate.showDropdown();
                            }
                        } else if (!isVisible) {
                            dropdownPrivate.showDropdown();
                        }
                    });
                },
                createHTML: function () {
                    if ($dropdown === undefined) {
                        opts.beforeCreate($elem);

                        $dropdown = $("<div/>").addClass("more-info-box").
                            append("<span class='close-btn'></span>").
                            append(opts.title).hide();

                        if (opts.url) {
                            $.ajax(opts.url).
                                done(function (data) {
                                    if (!opts.onResponse($elem, $dropdown, data)) {
                                        $elem.append(data);
                                    }

                                    $elem.append($dropdown);
                                    opts.onCreate($elem, $dropdown);
                                    dropdownPrivate.showDropdown();
                                });

                            return false;
                        }
                        $elem.append($dropdown);
                        $dropdown.append($("<div/>").html(opts.html));
                        return true;
                    }

                    return true;
                },
                showDropdown: function () {
                    opts.beforeShow($elem, $dropdown);

                    if (($.isFunction(opts.animate) && opts.animate()) || (!$.isFunction(opts.animate) && opts.animate)) {
                        $dropdown.slideDown(opts.showAnimation, function () {
                            dropdownPrivate.initCloseButton();
                            opts.onShow($elem, $dropdown);
                            isVisible = true;
                        });
                    } else {
                        isVisible = true;
                        $dropdown.show();
                        opts.onShow($elem, $dropdown);
                        setTimeout(function () {
                            dropdownPrivate.initCloseButton();
                        }, 50);
                    }
                },
                hideDropdown: function () {
                    if (($.isFunction(opts.animate) && opts.animate()) || (!$.isFunction(opts.animate) && opts.animate)) {
                        $dropdown.slideUp(opts.hideAnimation, function () {
                            $dropdown.hide();
                            isVisible = false;
                            opts.onHide($elem, $dropdown);
                        });
                    } else {
                        isVisible = false;
                        $dropdown.hide();
                        opts.onHide($elem, $dropdown);
                    }

                    if (clickHandler !== undefined) {
                        $(this).unbind(clickHandler);
                        clickHandler = undefined;
                    }
                },
                initCloseButton: function () {
                    //Hide when clicking document or close button clicked
                    if (clickHandler !== undefined) {
                        $(this).unbind(clickHandler);
                        clickHandler = undefined;
                    }
                    $(document).bind("click touchstart", function (e) {
                        if ((!$dropdown.is(e.target) && $dropdown.has(e.target).length === 0) || $dropdown.find(".close-btn").is(e.target)) {
                            if (isVisible) {
                                dropdownPrivate.hideDropdown();
                            }
                            $(this).unbind(e);
                            clickHandler = e;
                        }
                    });
                }
            };

            $elem.showDropdown = function () {
                dropdownPrivate.showDropdown();
            };

            $elem.hideDropdown = function () {
                dropdownPrivate.hideDropdown();
            };

            $elem.options = function (options) {
                opts = $.extend({}, $.fn.dropdown.defaults, opts, options);
            };

            //Initialise the dropdown on this element
            return $elem.each(function () {
                dropdownPrivate.init();
                opts.initalized = true;
            });
        };

        $.fn.dropdown.defaults = {
            title: "<h3>Builders shortcut</h3>",
            html: undefined,
            url: undefined,
            animate: true,
            showAnimation: "fast",
            hideAnimation: "fast",
            beforeCreate: function ($elem) {
                return undefined;
            },
            onCreate: function ($elem, $dropdown) {
                return undefined;
            },
            onResponse: function ($elem, $dropdown, response) {
                return false;
            },
            beforeShow: function ($elem, $dropdown) {
                return undefined;
            },
            onShow: function ($elem, $dropdown) {
                return undefined;
            },
            onHide: function ($elem, $dropdown) {
                return undefined;
            }
        };
    }(jQuery));

    projectDropDown = {
        init: function () {

            var mobileHTML,
                desktopHTML;

            $("#projectDropdown").dropdown({
                url: "/projects",
                beforeCreate: function ($elem) {
                    $('body').append(preloader).show();
                },
                onCreate: function ($elem, $dropdown) {
                    $('#bowlG').remove();
                    $(window).resize(function () {
                        $elem.hideDropdown();
                    });
                },
                onResponse: function ($elem, $dropdown, response) {
                    if (desktopHTML === undefined || mobileHTML === undefined) {
                        //Cache desktop HTML
                        desktopHTML = $(response).find('.tablesorter-js');


                        var fw = $(response).find('.scLink');
                        mobileHTML = $('<ul/>').addClass('submenu list-unstyled');
                        $(fw).each(function () {
                            var scLink = $(this).attr('data-sc');
                            $(this).attr('href', scLink);
                            var $li = $('<li/>').append($(this));
                            mobileHTML.append($li);
                        });

                        $(desktopHTML, mobileHTML).find("a").each(function () {
                            var scLink = $(this).attr('data-sc');
                            $(this).attr('href', scLink);
                        });
                    }

                    return true;
                },
                beforeShow: function ($elem, $dropdown) {
                    if (screenSize.isMediumScreen()) {
                        $dropdown.append(desktopHTML);
                    } else {
                        $elem.append(mobileHTML);
                    }
                },
                onShow: function ($elem, $dropdown) {
                    if (!screenSize.isMediumScreen()) {
                        $dropdown.hide();
                    }
                },
                onHide: function ($elem, $dropdown) {
                    $elem.find("ul").remove();
                },
                animate: function () {
                    return screenSize.isMediumScreen();
                }
            });

            //TODO: This should be elsewhere
            // mobile top menu
            $('.smartphone-nav').click(function () {
                var $topMenu = $('.top-menu');
                if ($topMenu.is(':hidden')) {
                    $topMenu.addClass('show-topmenu');
                } else {
                    $topMenu.removeClass('show-topmenu');
                }
            });

            $(window).resize(function () {
                $(".top-menu").removeClass("show-topmenu");
            });
        }
    };

    return projectDropDown;
});