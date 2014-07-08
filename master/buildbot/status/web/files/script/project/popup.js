/*global define, requirejs, jQuery*/
define(['jquery', 'helpers', 'libs/jquery.form', 'text!templates/popups.mustache', 'mustache', 'timeElements', 'toastr'], function ($, helpers, form, popups, Mustache, timeElements, toastr) {

    "use strict";

    var $body = $("body");

    // Extend our jquery object with popup widget
    (function ($) {

        $.fn.popup = function (options) {
            var $elem = $(this);
            var opts = $.extend({}, $.fn.popup.defaults, options),
                clickHandler;
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
                        attr("data-ui-popup", true).hide();

                    if (opts.url) {
                        $.ajax(opts.url).
                            done(function (data) {
                                $elem.append(data);
                                opts.onCreate($elem);
                                privateFunc.showPopup();

                                return true;
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
                        setTimeout(function () {
                            helpers.jCenter($elem);
                            $(window).resize(function () {
                                helpers.jCenter($elem);
                            });
                        }, 50);
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
                            $elem.hide();
                            privateFunc.clear();
                            opts.onHide($elem);
                        });
                    } else {
                        $elem.hide();
                        privateFunc.clear();
                        opts.onHide($elem);
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
                        if ((!$elem.is(e.target) && $elem.has(e.target).length === 0) || $elem.find(".close-btn").is(e.target)) {
                            if ($elem.is(":visible")) {
                                privateFunc.hidePopup();
                                $(this).unbind(e);
                                clickHandler = e;
                            }
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

            $elem.options = function (options) {
                opts = $.extend({}, $.fn.popup.defaults, opts, options);
            };

            //Initialise the popup on this element
            return $elem.each(function () {
                privateFunc.init();
                opts.initalized = true;
            });
        };

        $.fn.popup.defaults = {
            title: "",
            html: undefined,
            url: undefined,
            destroyAfter: false,
            autoShow: true,
            center: true,
            animate: true,
            showAnimation: "fast",
            hideAnimation: "fast",
            onCreate: function ($elem) {
                return undefined;
            },
            onShow: function ($elem) {
                return undefined;
            },
            onHide: function ($elem) {
                return undefined;
            }
        };
    }(jQuery));


    var popup;

    popup = {
        init: function () {
            // Display the codebases form in a popup
            popup.initCodebaseBranchesPopup($("#codebasesBtn"));
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
        initJSONPopup: function (jsonPopupElem, data) {
            var $jsonPopupElem = $(jsonPopupElem);

            $jsonPopupElem.click(function (e) {
                e.preventDefault();
                var html = Mustache.render(popups, data);
                $body.append($("<div/>").popup({
                    title: "",
                    html: html,
                    onShow: function () {
                        if (data.showRunningBuilds !== undefined) {
                            helpers.delegateToProgressBar($('div.more-info-box-js div.percent-outer-js'));
                        }
                        timeElements.updateTimeObjects();
                    }
                }));
            });
        },
        initCodebaseBranchesPopup: function (codebaseElem) {
            var $codebaseElem = $(codebaseElem),
                codebasesURL = $codebaseElem.attr("data-codebases-url");

            $codebaseElem.click(function (event) {
                event.preventDefault();

                //TODO: Remove this
                var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
                var preloader = $(mustacheTmpl);
                $('body').append(preloader).show();

                $.get(codebasesURL).
                    done(function (html) {
                        preloader.remove();
                        requirejs(['selectors'], function (selectors) {
                            var fw = $(html).find('#formWrapper');
                            fw.children('#getForm').attr('action', window.location.href);
                            fw.find('.blue-btn[type="submit"]').val('Update');


                            $body.append($("<div/>").popup({
                                title: $('<h3 class="codebases-head" />').html("Select Branches"),
                                html: fw,
                                destroyAfter: true,
                                onCreate: function ($elem) {
                                    $elem.css("max-width", "80%");
                                },
                                onShow: function ($elem) {
                                    selectors.init();
                                    helpers.jCenter($elem);
                                    $(window).resize(function () {
                                        helpers.jCenter($elem);
                                    });
                                }
                            }));
                        });
                    });
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

                        var cancelURL = data[0].builderURL;
                        var properties = "";
                        if (cancelURL.indexOf("?") > -1) {
                            var split = cancelURL.split("?");
                            properties += split[1] + "&";
                            cancelURL = split[0];
                        }

                        properties += "returnpage=builders_json";
                        cancelURL = "{0}/cancelbuild?{1}".format(cancelURL, properties);

                        var html = Mustache.render(popups, {pendingJobs: data, showPendingJobs: true, cancelURL: cancelURL});

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

            $pendingElem.click(function (event) {
                event.preventDefault();
                openPopup();
            });
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
                    urlParams = helpers.codebasesFromURL({builder_url: builderURL, builder_name: builderName, return_page: dataReturnPage});


                var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
                var $preloader = $(mustacheTmpl); //TODO: Move elsewhere
                $body.append($preloader);
                $preloader.show();

                function errorCreatingBuild() {
                    toastr.error('There was an error when creating your build please try again later', 'Error', {
                        iconClass: 'failure'
                    });
                }

                $.get(url, urlParams)
                    .done(function (html) {
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

                                            toastr.info('Your build will start shortly', 'Info', {
                                                iconClass: 'info'
                                            });
                                        },
                                        error: function () {
                                            $preloader.remove();
                                            errorCreatingBuild();
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
                    })
                    .fail(function () {
                        errorCreatingBuild();
                    })
                    .always(function () {
                        $preloader.hide();
                    });
            }

            $customBuild.click(function (event) {
                event.preventDefault();
                openPopup(false);
            });

            $instantBuild.click(function (event) {
                event.preventDefault();
                openPopup(true);
            });
        },
        initArtifacts: function (artifactList, artifactElem) {
            var $artifactElem = $(artifactElem);

            $artifactElem.click(function (event) {
                event.preventDefault();

                var html = "";
                if (artifactList !== undefined) {
                    $.each(artifactList, function (name, url) {
                        html += '<li class="artifact-js"><a target="_blank" href="{1}">{0}</a></li>'.format(name, url);
                    });
                    html = $('<ul/>').addClass("builders-list").html(html);
                    var $popup = $("<div/>").popup({
                        title: "<h3>Artifacts</h3>",
                        html: html,
                        destroyAfter: true
                    });

                    $body.append($popup);
                }
            });
        }
    };
    return popup;
});
