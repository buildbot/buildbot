/*global define, requirejs*/
define(['jquery', 'screensize', 'text!templates/popups.mustache', 'mustache', "extend-moment", "timeElements"], function ($, screenSize, popupsMus, Mustache, extendMoment, timeElements) {

    "use strict";
    var helpers,
        css_class_enum = {},
        css_classes = {
            SUCCESS: [0, "success"],
            WARNINGS: [1, "warnings"],
            FAILURE: [2, "failure"],
            SKIPPED: [3, "skipped"],
            EXCEPTION: [4, "exception"],
            RETRY: [5, "retry"],
            CANCELED: [6, "exception"],
            NOT_REBUILT: [7, "not_rebuilt"],
            DEPENDENCY_FAILURE: [8, "dependency_failure"],
            RUNNING: [9, "running"],
            NOT_STARTED: [10, "not_started"],
            None: ""
        };

    $.each(css_classes, function (key, val) {
        css_class_enum[key] = val[0];
    });

    String.prototype.format = function () {
        var args = arguments;
        return this.replace(/\{(\d+)\}/g, function (match, number) {
            return args[number] !== undefined ? args[number] : match;
        });
    };

    Number.prototype.clamp = function (min, max) {
        return Math.min(Math.max(this, min), max);
    };

    helpers = {
        init: function () {
            /*
             // only for testing
             $('<div/>').addClass('windowsize').css({'position': 'absolute', 'fontSize': '20px'}).prependTo('body');

             var ws = $(window).width() + ' ' +  $(window).height();

             $('.windowsize').html(ws);

             $(window).resize(function(event) {
             ws = $(window).width() + ' ' +  $(window).height();
             $('.windowsize').html(ws);
             });
             */
            // Set the currentmenu item
            helpers.setCurrentItem();

            // Authorize on every page
            helpers.authorizeUser();

            if ($('#buildslave_page').length) {
                // display the number of current jobs
                helpers.displaySum($('#currentJobs'), $('#runningBuilds_onBuildslave').find('li'));
            }

            // keyboard shortcuts
            /*
             $('body').keyup(function(event) {

             // p
             if (event.which === 80) {
             location.href = '/projects'
             }
             // q
             if (event.which === 81) {
             location.href = '/buildqueue'
             }
             // s
             if (event.which === 83) {
             location.href = '/buildslaves'
             }
             // h
             if (event.which === 72) {
             location.href = '/'
             }

             });
             */

            // submenu overflow on small screens
            helpers.menuItemWidth(screenSize.isMediumScreen());
            $(window).resize(function () {
                helpers.menuItemWidth(screenSize.isMediumScreen());
            });

            // chrome font problem fix
            $(function userAgent() {
                var is_chrome = /chrome/.test(navigator.userAgent.toLowerCase());
                var isFirefox = /firefox/.test(navigator.userAgent.toLowerCase());
                var isWindows = navigator.platform.toUpperCase().indexOf('WIN') !== -1;
                if (is_chrome) {
                    $('body').addClass('chrome');
                }
                if (isWindows) {
                    $('body').addClass('win');
                }

                if (isFirefox) {
                    $('body').addClass('firefox');
                }

            });

            // tooltip used on the builddetailpage
            helpers.toolTip('.ellipsis-js');

            // parse reason string on the buildqueue page
            helpers.parseReasonString();

            $('#authUserBtn').click(function () {
                helpers.eraseCookie('fullName1', '', 'eraseCookie');
            });
            helpers.tooltip($('.tooltip'));

        },
        randomImage: function (el) {
            var images = ['48273828.jpg'];
            el.attr('src', 'images/' + images[Math.floor(Math.random() * images.length)]);

        },
        tooltip: function (elements) {
            $.each(elements, function (i, el) {
                var $elem = $(el),
                    $toolTipCont = $("<div/>").addClass("tooltip-cont"),
                    clickEvent;



                $elem.hover(function (e) {
                    var title,
                        cursorPosTop = e.pageY + 20,
                        cursorPosLeft = e.pageX + 5,
                        clickHandler = function (event) {
                            clickEvent = event;
                            $toolTipCont.remove();
                            $(e.target).unbind(event);
                        };

                    if ($elem.attr("title") !== undefined) {
                        $elem.attr("data-title", $elem.attr("title"));
                        $elem.attr("title", undefined);
                    }
                    title = $elem.attr("data-title");

                    $elem.bind("click", clickHandler);

                    if (screenSize.isMediumScreen() || !$elem.hasClass('responsive-tooltip')) {
                        $toolTipCont.html(title)
                            .appendTo('body')
                            .css({'top': cursorPosTop, 'left': cursorPosLeft})
                            .fadeIn('fast');
                    } else if ($elem.hasClass('responsive-tooltip')) {

                        $toolTipCont.html(title)
                            .appendTo('body')
                            .css({'top': cursorPosTop, 'right': 28 })
                            .fadeIn('fast');
                    }

                }, function () {
                    if (clickEvent !== undefined) {
                        $elem.unbind(clickEvent);
                        clickEvent = undefined;
                    }

                    var toolTipCont = $('.tooltip-cont');
                    toolTipCont.fadeOut('fast', function () {
                        $(this).unbind();
                        $(this).remove();
                    });
                });
            });
        },
        authorizeUser: function () {
            // Force a user to login
            var url = window.location;
            if (helpers.getCookie("BuildBotSession") === '') {
                // Redirect to loginpage if missing namecookie
                window.location = "/login";
            }
        },
        setCurrentItem: function () {

            var path = window.location.pathname.split("\/");

            $('.top-menu a').each(function (index) {
                var thishref = this.href.split("\/");

                if (this.id === path[1].trim().toLowerCase() || (this.id === 'home' && path[1].trim().toLowerCase().length === 0)) {
                    $(this).parent().addClass("selected");
                }
            });

        },
        jCenter: function ($el) {
            if ($el !== undefined && $el !== null) {

                var h = $(window).height();
                var w = $(window).width();
                var tu = $el.outerHeight();
                var tw = $el.outerWidth();

                // adjust height to browser height , "height":h - 75 , "height":'auto'

                if (h < (tu + 5)) {

                    $el.css({"top": 5 + $(window).scrollTop() + "px", "height": h - 60});
                } else {

                    $el.css({"top": (h - tu) / 2 + $(window).scrollTop() + 'px', "height": 'auto'});
                }

                $el.css("left", (w - tw) / 2 + $(window).scrollLeft() + "px");
                return $el;
            }
        },
        parseReasonString: function () { // parse reason string on the buildqueue page
            $('.codebases-list .reason-txt').each(function () {
                var rTxt = $(this).text().trim();
                if (rTxt === "A build was forced by '':") {
                    $(this).remove();
                }
            });

        },
        selectBuildsAction: function ($table, dontUpdate, updateUrl, parameters) { // check all in tables and perform remove action

            if ($table === undefined) {
                $table = $('#tablesorterRt');
                if ($table.length === 0) {
                    return;
                }
            }
            var mustacheTmpl = Mustache.render(popupsMus, {'preloader': 'true'}),
                preloader = $(mustacheTmpl),
                selectAll = $('#selectall');


            selectAll.click(function () {
                var tableNodes = $table.dataTable().fnGetNodes();
                $('.fi-js', tableNodes).prop('checked', this.checked);
            });

            function ajaxPost(str) {
                var $dataTable = $table.dataTable();
                $('body').append(preloader).show();
                str = str + '&ajax=true';

                $.ajax({
                    type: "POST",
                    url: updateUrl,
                    data: str,
                    success: function (data) {
                        //TODO: Remove this so that we can update with a URL that only returns
                        //the new ones
                        if (dontUpdate === false) {
                            $dataTable.fnClearTable();
                            $dataTable.fnAddData(data);
                        }

                        selectAll.prop('checked', false);
                        preloader.remove();
                    }
                });
                return false;
            }

            $('#submitBtn').click(function (e) {
                e.preventDefault();


                var $dataTable = $table.dataTable();
                var tableNodes = $dataTable.fnGetNodes();
                var checkedNodes = $('.fi-js', tableNodes);

                var formStr = "";
                checkedNodes.each(function () {
                    if ($(this).is(':checked')) {
                        formStr += parameters + $(this).val() + '&';
                    }
                });
                var formStringSliced = formStr.slice(0, -1);

                if (formStringSliced !== '') {
                    ajaxPost(formStringSliced);
                }
            });
            $table.delegate('.force-individual-js', 'click', function (e) {
                e.preventDefault();
                var iVal = $(this).prev().val();
                var str = parameters + iVal;
                ajaxPost(str);
            });

        },
        updateBuilders: function () {
            $.ajax({
                url: "/json/builders/?filter=0",
                dataType: "json",
                type: "GET",
                cache: false,
                success: function (data) {
                    var arrayBuilders = [];
                    var arrayPending = [];
                    var arrayCurrent = [];
                    $.each(data, function (key, value) {
                        arrayBuilders.push(key);
                        arrayPending.push(value.pendingBuilds);
                        if (value.state === 'building') {
                            arrayCurrent.push(value.currentBuilds);
                        }
                    });

                    function sumVal(arr) {
                        var sum = 0;
                        $.each(arr, function () {
                            sum += parseFloat(this) || 0;
                        });
                        return sum;
                    }

                    $('#pendingBuilds').text(sumVal(arrayPending));
                }
            });

            $.ajax({
                url: "/json/slaves/?filter=0",
                dataType: "json",
                type: "GET",
                cache: false,
                success: function (data) {
                    var arraySlaves = [];
                    $.each(data, function (key) {
                        arraySlaves.push(key);
                    });

                    $('#slavesNr').text(arraySlaves.length);
                }
            });
        },
        codeBaseBranchOverview: function (El) {

            var decodedUri = decodeURIComponent(window.location.search);
            var parsedUrl = decodedUri.split('&');
            var cbTable = $('<div class="border-table-holder col-xs-10"><div id="overScrollJS" class="inner-table-holder">' +
                '<table class="codebase-branch-table"><tr class="codebase"><th>Codebase' +
                '</th></tr><tr class="branch"><th>Branch</th></tr></table></div></div>');

            cbTable.appendTo(El);

            $(parsedUrl).each(function (i) {

                // split key and value
                var eqSplit = this.split("=");

                if (eqSplit[0].indexOf('_branch') > 0) {

                    // seperate branch
                    var codeBases = this.split('_branch')[0];
                    // remove the ? from the first codebase value
                    if (i === 0) {
                        codeBases = this.replace('?', '').split('_branch')[0];
                    }

                    var branches = this.split('=')[1];

                    $('tr.codebase').append('<td>' + codeBases + '</td>');
                    $('tr.branch').append('<td>' + branches + '</td>');
                }

            });

        },
        menuItemWidth: function (isMediumScreen) { // set the width on the breadcrumbnavigation. For responsive use

            if (isMediumScreen) {                
                $('.breadcrumbs-nav').width('');
            } else {
                var wEl = 0;
                $('.breadcrumbs-nav li').each(function () {
                    wEl += $(this).outerWidth();
                });
                $('.breadcrumbs-nav').width(wEl + 100);
            }

        },
        toolTip: function (ellipsis) { // tooltip used on the builddetailpage
            $(ellipsis).parent().hover(function () {

                var txt = $(ellipsis, this).attr('data-txt');

                var toolTip = $('<div/>').addClass('tool-tip').text(txt);

                $(this).append($(toolTip).css({
                    'top': $(ellipsis, this).position().top - 10,
                    'left': $(ellipsis, this).position().left - 20
                }).show());

            }, function () {
                $('.tool-tip').remove();
            });
            // ios fix
            $(document).bind('click touchstart', function (e) {
                $('.tool-tip').remove();
                $(this).unbind(e);
            });
        },
        displaySum: function (displayEl, countEl) {
            // Insert the total length of the elements
            displayEl.text(countEl.length);

        },
        setCookie: function (name, value, eraseCookie) { // renew the expirationdate on the cookie

            var today = new Date();
            var expiry = new Date(today.getTime() + 30 * 24 * 3600 * 1000); // plus 30 days
            var expiredate = eraseCookie === undefined ? expiry.toGMTString() : 'Thu, 01 Jan 1970 00:00:00 GMT;';

            document.cookie = name + "=" + value + "; path=/; expires=" + expiredate;

        },
        inDOM: function (element) {
            return $.contains(document.documentElement, element[0]);
        },
        delegateToProgressBar: function (bars) {
            $.each(bars, function (key, elem) {
                var obj = $(elem);
                timeElements.addProgressBarElem(obj, obj.attr('data-starttime'), obj.attr('data-etatime'));
            });
        },
        verticalProgressBar: function (el, per) {
            // must be replaced with json values
            el.height("{0}%".format(per));
        },
        getTime: function (start, end) {

            if (end === null) {
                end = Math.round(+new Date() / 1000);
            }

            var time = end - start;

            var getTime = Math.round(time);
            var days = Math.floor(time / 86400) === 0 ? '' : Math.floor(time / 86400) + ' days ';
            var hours = Math.floor(time / 3600) === 0 ? '' : Math.floor(time / 3600) % 24 + ' hours ';

            var minutes = Math.floor(getTime / 60) === 0 ? '' : Math.floor(getTime / 60) % 60 + ' mins, ';
            var seconds = getTime - Math.floor(getTime / 60) * 60 + ' secs ';
            return days + hours + minutes + seconds;

        },
        getResult: function (resultIndex) {

            var results = ["success", "warnings", "failure", "skipped", "exception", "retry", "canceled"];
            return results[resultIndex];

        },
        getSlavesResult: function (connected, runningBuilds) {

            return connected === false ? 'Not connected' : runningBuilds.length > 0 ? 'Running' : 'idle';

        },
        getClassName: function (connected, runningBuilds) {

            var slavesResult = helpers.getSlavesResult(connected, runningBuilds);

            return slavesResult === 'Not connected' ? 'status-td offline' : slavesResult === 'Running' ? 'status-td building' : 'status-td idle';

        },
        getCurrentPage: function () {
            // return the id of the page
            return document.getElementsByTagName('body')[0].id;
        },
        hasfinished: function () {
            var hasfinished = false;
            var isFinishedAttr = $('#isFinished').attr('data-isfinished');

            if (isFinishedAttr === undefined) {
                hasfinished = false;
            }

            if (isFinishedAttr === true) {
                hasfinished = true;
            }

            return hasfinished;

        },
        isRealTimePage: function () {
            var isRealtimePage = false;
            var currentRtPages = ['buildslaves_page', 'buildslavedetail_page', 'builderdetail_page', 'builddetail_page', 'buildqueue_page',
                'projects_page', 'home_page', 'builders_page', 'jsonhelp_page', 'usersettings_page'];
            var current = helpers.getCurrentPage();
            $.each(currentRtPages, function (key, value) {
                if (value === current) {
                    isRealtimePage = true;
                }
            });
            return isRealtimePage;

        },
        getCookie: function (name) { // get cookie values
            var re = new RegExp(name + "=([^;]+)");
            var value = re.exec(document.cookie);
            return (value !== null) ? decodeURI(value[1]) : '';

        },
        eraseCookie: function (name, value, eraseCookie) {
            helpers.setCookie(name, value, eraseCookie);

        },
        closePopup: function (boxElement, clearEl) {

            var closeBtn = $('.close-btn').add(document);

            closeBtn.bind('click touchstart', function (e) {

                if ((!$(e.target).closest(boxElement).length || $(e.target).closest('.close-btn').length)) {

                    if (clearEl === undefined) {
                        boxElement.remove();
                    } else {

                        boxElement.slideUp('fast', function () {
                            closeBtn.unbind(e);
                        });
                    }

                    closeBtn.unbind(e);

                }

            });
        },
        urlHasCodebases: function () {
            return Object.keys(helpers.codebasesFromURL({})).length > 0;
        },
        codebasesFromURL: function (urlParams) {
            var sPageURL = window.location.search.substring(1);
            var sURLVariables = sPageURL.split('&');
            $.each(sURLVariables, function (index, val) {
                var sParameterName = val.split('=');
                if (sParameterName[0].indexOf("_branch") >= 0) {
                    urlParams[sParameterName[0]] = sParameterName[1];
                }
            });

            return urlParams;
        },
        urlParamsToString: function (urlParams) {
            var ret = [];
            $.each(urlParams, function (name, value) {
                ret.push(name + "=" + value);
            });

            return ret.join("&");
        },
        getCssClassFromStatus: function (status) {
            var values = Object.keys(css_classes).map(function (key) {
                return css_classes[key];
            });
            return values[status][1];
        },
        setIFrameSize: function (iFrame) {
            if (iFrame) {
                var iFrameWin = iFrame.contentWindow || iFrame.contentDocument.parentWindow;
                if (iFrameWin.document.body) {
                    iFrame.height = iFrameWin.document.documentElement.scrollHeight || iFrameWin.document.body.scrollHeight;
                    iFrame.width = iFrameWin.document.documentElement.scrollWidth || iFrameWin.document.body.scrollWidth;
                }
            }
        },
        objectPropertiesToArray: function (arr) {
            var result = [],
                key;

            for (key in arr) {
                if (arr.hasOwnProperty(key)) {
                    result.push(arr[key]);
                }
            }

            return result;
        },
        /**
         * Clear all events and binding on the child elements,
         * this is super useful to make sure we don't have memory leaks
         * when DOM elements are removed from the DOM
         * @param $elem
         */
        clearChildEvents: function ($elem) {
            $elem.find("*").addBack().off();
        },
        cssClassesEnum : css_class_enum
    };

    return helpers;
});
