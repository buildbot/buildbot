/*global define, requirejs, jQuery*/
define(['jquery', 'helpers', 'libs/jquery.form', 'text!templates/popups.mustache', 'mustache', 'timeElements'], function ($, helpers, form, popups, Mustache, timeElements) {

    "use strict";

    var $body = $("body");

    // Extend our jquery object with popup widget
    (function ($) {

        $.fn.popup = function (options) {
            var $elem = $(this);
            var opts = $.extend({}, $.fn.popup.defaults, options);
            $elem.settings = opts;

            var privateFunc = {
                init: function () {
                    privateFunc.clear();
                    if (privateFunc.createHTML()) {
                        opts.onCreate($elem);

                        if (opts.autoShow) {
                            $elem.ready(function () {
                                privateFunc.showPopup();
                            });
                        }
                    }
                },
                createHTML: function () {
                    $elem.addClass("more-info-box more-info-box-js").
                        append("<span class='close-btn'></span>").
                        append(opts.title).
                        attr("data-ui-popup", true);

                    if (opts.url) {
                        $.ajax(opts.url).
                            done(function (data) {
                                $elem.append(data);
                                opts.onCreate($elem);
                                privateFunc.showPopup();
                            });

                        return false;
                    }

                    $elem.append($("<div/>").html(opts.html));
                    return true;
                },
                clear: function () {
                    if ($elem.attr("data-ui-popup") === "true") {
                        if (opts.destroyAfter) {
                            $elem.remove();
                        } else {
                            $elem.empty();
                        }
                    }
                },
                showPopup: function () {
                    if (opts.center) {
                        helpers.jCenter($elem);
                    }

                    if (opts.animate) {
                        $elem.fadeIn(opts.showAnimation, function () {
                            privateFunc.initCloseButton();
                            opts.onShow($elem);
                        });
                    } else {
                        $elem.show({
                            complete: function () {
                                opts.onShow($elem);
                                privateFunc.initCloseButton();
                            }
                        });
                    }
                },
                hidePopup: function () {
                    if (opts.animate) {
                        $elem.fadeOut(opts.hideAnimation, function () {
                            privateFunc.clear();
                        });
                    } else {
                        $elem.hide();
                        privateFunc.clear();
                    }
                },
                initCloseButton: function () {
                    //Hide when clicking document or close button clicked
                    $(document).bind("click touchstart", function (e) {
                        if ((!$elem.is(e.target) && $elem.has(e.target).length === 0) || $elem.find(".close-btn").is(e.target)) {
                            privateFunc.hidePopup();
                            $(this).unbind(e);
                        }
                    });
                }
            };

            $elem.showPopup = function () {
                privateFunc.showPopup();
            };

            $elem.hidePopup = function () {
                privateFunc.hidePopup();
            };

            //Initialise the popup on this element
            return $elem.each(function () {
                privateFunc.init();
                opts.initalized = true;
            });
        };

        $.fn.popup.defaults = {
            title: "<h3>Katana Popup</h3>",
            html: undefined,
            url: undefined,
            destroyAfter: false,
            autoShow: true,
            center: true,
            animate: true,
            showAnimation: "fast",
            hideAnimation: "fast",
            onCreate: function () {},
            onShow: function () {}
        };
    }(jQuery));


    var popup;

    popup = {
        init: function () {

            //For non ajax boxes
            var $tableSorterRt = $('#tablesorterRt');
            popup.registerJSONPopup($tableSorterRt);

            $('.popup-btn-js-2').click(function (e) {
                e.preventDefault();
                popup.nonAjaxPopup($(this));
            });

            // Display the codebases form in a popup
            $('#getBtn').click(function (e) {
                e.preventDefault();
                popup.codebasesBranches();
            });
        },
        showjsonPopup: function (jsonObj) {
            var mustacheTmpl = Mustache.render(popups, jsonObj);
            var mustacheTmplShell = $(Mustache.render(popups, {MoreInfoBoxOuter: true}, {partial: mustacheTmpl}));

            $('body').append(mustacheTmplShell);

            if (jsonObj.showRunningBuilds !== undefined) {
                helpers.delegateToProgressBar($('div.more-info-box-js div.percent-outer-js'));
            }

            helpers.jCenter(mustacheTmplShell).fadeIn('fast', function () {
                helpers.closePopup(mustacheTmplShell);
            });

        },
        validateForm: function (formContainer) { // validate the forcebuildform
            var formEl = $('.command_forcebuild', formContainer);
            var excludeFields = ':button, :hidden, :checkbox, :submit';
            $('.grey-btn', formEl).click(function (e) {

                var allInputs = $('input', formEl).not(excludeFields);

                var rev = allInputs.filter(function () {
                    return this.name.indexOf("revision") >= 0;
                });

                var emptyRev = rev.filter(function () {
                    return this.value === "";
                });

                if (emptyRev.length > 0 && emptyRev.length < rev.length) {

                    rev.each(function () {
                        if ($(this).val() === "") {
                            $(this).addClass('not-valid');
                        } else {
                            $(this).removeClass('not-valid');
                        }
                    });

                    $('.form-message', formEl).hide();

                    if (!$('.error-input', formEl).length) {
                        var mustacheTmplErrorinput = Mustache.render(popups, {'errorinput': 'true', 'text': 'Fill out the empty revision fields or clear all before submitting'});
                        var errorinput = $(mustacheTmplErrorinput);
                        $(formEl).prepend(errorinput);
                    }
                    e.preventDefault();
                }
            });
        },
        nonAjaxPopup: function (thisEl) {
            var clonedInfoBox = thisEl.next($('.more-info-box-js')).clone();
            clonedInfoBox.appendTo($('body'));
            helpers.jCenter(clonedInfoBox).fadeIn('fast', function () {
                helpers.closePopup(clonedInfoBox);
            });
            $(window).resize(function () {
                helpers.jCenter(clonedInfoBox);
            });

        },
        codebasesBranches: function () {

            var path = $('#pathToCodeBases').attr('href');

            var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
            var preloader = $(mustacheTmpl);

            $('body').append(preloader).show();
            var mib = popup.htmlModule('Select branches');

            $(mib).appendTo('body');


            $.get(path)
                .done(function (data) {
                    requirejs(['selectors'], function (selectors) {

                        var formContainer = $('#content1');
                        preloader.remove();

                        var fw = $(data).find('#formWrapper');
                        fw.children('#getForm').attr('action', window.location.href);
                        var blueBtn = fw.find('.blue-btn[type="submit"]').val('Update');


                        fw.appendTo(formContainer);

                        helpers.jCenter(mib).fadeIn('fast', function () {
                            selectors.init();
                            blueBtn.focus();
                            helpers.closePopup(mib);

                        });

                        $(window).resize(function () {
                            helpers.jCenter(mib);
                        });

                    });
                });
        },
        customTabs: function () { // tab list for custom build
            $('.tabs-list li').click(function (i) {
                var indexLi = $(this).index();
                $(this).parent().find('li').removeClass('selected');
                $(this).addClass('selected');
                $('.content-blocks > div').each(function (i) {
                    if ($(this).index() !== indexLi) {
                        $(this).hide();
                    } else {
                        $(this).show();
                    }
                });

            });
        },
        htmlModule: function (headLine) { // html chunks
            var mib =
                $('<div class="more-info-box remove-js">' +
                    '<span class="close-btn"></span>' +
                    '<h3 class="codebases-head">' + headLine + '</h3>' +
                    '<div id="content1"></div></div>');

            return mib;
        },
        registerJSONPopup: function ($parentElem) {
            $parentElem.delegate('a.popup-btn-json-js', 'click', function (e) {
                e.preventDefault();
                popup.showjsonPopup($(this).data());
                timeElements.updateTimeObjects();
            });
        },
        initPendingPopup: function (pendingElem) {
            var $pendingElem = $(pendingElem),
                builder_name = encodeURIComponent($pendingElem.attr('data-builderName')),
                urlParams = helpers.codebasesFromURL({}),
                paramsString = helpers.urlParamsToString(urlParams),
                url = "/json/pending/{0}/?{1}".format(builder_name, paramsString);

            function openPopup() {
                // TODO: Remove this
                var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
                var preloader = $(mustacheTmpl);
                $('body').append(preloader).show();

                $.ajax({
                    url: url,
                    cache: false,
                    dataType: "json",
                    success: function (data) {
                        preloader.remove();
                        var html = Mustache.render(popups, {pendingJobs: data, showPendingJobs: true, cancelAllbuilderURL: data[0].builderURL});

                        $body.append($("<div/>").popup({
                            html: html,
                            destroyAfter: true,
                            onCreate: function ($elem) {
                                var waitingtime = $elem.find('.waiting-time-js');
                                waitingtime.each(function (i) {
                                    timeElements.addElapsedElem($(this), data[i].submittedAt);
                                    timeElements.updateTimeObjects();
                                });

                                $elem.find('form').ajaxForm({
                                    success: function (data, text, xhr, $form) {
                                        requirejs(['realtimePages'], function (realtimePages) {
                                            setTimeout(function () {
                                                var name = "builders";
                                                realtimePages.updateSingleRealTimeData(name, data);
                                            }, 300);
                                        });

                                        var cancelAll = $form.attr("id") === "cancelall";
                                        if (!cancelAll) {
                                            $form.parent().remove();
                                        }

                                        if (cancelAll || $elem.find('li').length === 1) {
                                            $elem.hidePopup();
                                        }
                                    }
                                });
                            }
                        }));
                    }
                });
            }

            $pendingElem.click(openPopup);
        },
        initRunBuild: function (customBuildElem, instantBuildElem) {
            var $customBuild = $(customBuildElem),
                $instantBuild = $(instantBuildElem);

            if ($customBuild.length === 0) {
                //Bailing early as we didn't find our elements
                return;
            }

            function openPopup(instantBuild) {
                var builderURL = $customBuild.attr('data-builder-url'),
                    dataReturnPage = $customBuild.attr('data-return-page'),
                    builderName = $customBuild.attr('data-builder-name'),
                    title = $customBuild.attr('data-popup-title'),
                    url = location.protocol + "//" + location.host + "/forms/forceBuild",
                    urlParams = {builder_url: builderURL, builder_name: builderName, return_page: dataReturnPage};

                var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
                var $preloader = $(mustacheTmpl); //TODO: Move elsewhere
                $body.append($preloader);
                $preloader.show();

                $.get(url, urlParams).
                    done(function (html) {
                        $preloader.hide();

                        var $html = $(html);

                        // Create popup
                        var $popup = $("<div/>").popup({
                            title: $('<h2 class="small-head" />').html(title),
                            html: html,
                            destroyAfter: true,
                            autoShow: false,
                            onCreate: function ($elem) {
                                popup.validateForm($elem);

                                //Setup AJAX form and instant builds
                                var $form = $elem.find('form'),
                                    formOptions = {
                                        beforeSubmit: function () {
                                            $elem.hidePopup();
                                            $preloader.show();
                                        },
                                        success: function (data) {
                                            requirejs(['realtimePages'], function (realtimePages) {
                                                var name = dataReturnPage.replace("_json", "");
                                                realtimePages.updateSingleRealTimeData(name, data);
                                            });
                                            $preloader.remove();
                                        }
                                    };

                                $form.ajaxForm(formOptions);

                                if (instantBuild) {
                                    $form.ajaxSubmit(formOptions);
                                }
                            }
                        });

                        $body.append($popup);
                        if (!instantBuild) {
                            $popup.showPopup();
                        }
                    });
            }

            $customBuild.click(function () {
                openPopup(false);
            });

            $instantBuild.click(function () {
                openPopup(true);
            });
        }
    };
    return popup;
});
