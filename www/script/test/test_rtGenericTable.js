/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "rtGenericTable", "project/handlebars-extend"], function ($, gt, hb) {
    "use strict";

    var buildData = {
        artifacts: {
            "ZippedForTeamCity.zip": "http://artifact.hq.unity3d.com/testbuilds/proj0-Build_MacDevelopmentWebPlayer_128986_13_06_2014_07_44_35_+0000/build/ZippedForTeamCity.zip"
        },
        builderFriendlyName: "Build MacDevelopmentWebPlayer",
        builderName: "proj0-Build MacDevelopmentWebPlayer",
        builder_url: "http://10.45.6.89:8001/projects/Unity%20-%20Trunk/builders/proj0-Build%20MacDevelopmentWebPlayer?unity_branch=trunk",
        number: 41,
        reason: "Build caused by 'Daniel Hobley <danielh@unity3d.com>': Triggerable(MacDevelopmentWebPlayer-Dependency)",
        results: 7,
        results_text: "not_rebuilt",
        slave: "mba01",
        slave_friendly_name: "mac-test-vm-v3-01",
        slave_url: "http://10.45.6.89:8001/buildslaves/mba01",
        sourceStamps: [
            {
                branch: "trunk",
                codebase: "unity",
                display_repository: "http://rhodecode.hq.unity3d.com/unity/unity",
                project: "general",
                repository: "http://mercurial-mirror.hq.unity3d.com/all-unity",
                revision: "b841045fb3160b1c0044b3b04f40482f685208cf",
                revision_short: "b841045fb316"
            },
            {
                branch: "faked",
                codebase: "fakedrepo",
                display_repository: "http://rhodecode.hq.unity3d.com/fake/fake",
                project: "general",
                repository: "http://mercurial-mirror.hq.unity3d.com/fake",
                revision: "c841045fb3160b1c0044b3b04f40482f685208cf",
                revision_short: "b841045fb316"
            }
        ],
        text: [
            "Successful Build Found (did not rebuild)"
        ],
        times: [
            1402648683.694,
            1402648983.858,
            1402648883.858
        ],
        url: {
            path: "http://10.45.6.89:8001/projects/Unity - Trunk/builders/proj0-Build%20MacDevelopmentWebPlayer/builds/41?unity_branch=trunk",
            text: "proj0-Build MacDevelopmentWebPlayer #41"
        }

    };

    var builderData = {
        name: "proj0-Build MacDevelopmentWebPlayer",
        friendly_name: "Build MacDevelopmentWebPlayer",
        latestBuild: buildData,
        project: "Unity - Trunk",
        slaves: ["mba01"],
        url: "http://10.45.6.89:8001/projects/Unity%20-%20Trunk/builders/proj0-Build%20MacDevelopmentWebPlayer?unity_branch=trunk"
    };

    var slaveData = {
        mba01: {
            builders: [
                {
                    builds: [1, 2, 3, 4, 5],
                    friendly_name: "ABuildVerification [ABV]",
                    name: "proj0-ABuildVerification",
                    url: "http://10.45.6.89:8001/projects/Unity%20-%20Trunk/builders/proj0-ABuildVerification"
                },
                {
                    builds: [1, 2, 3],
                    friendly_name: "Build AndroidDevelopmentPlayer [ABV]",
                    name: "proj0-Build AndroidDevelopmentPlayer",
                    url: "http://10.45.6.89:8001/projects/Unity%20-%20Trunk/builders/proj0-Build%20AndroidDevelopmentPlayer"
                },
                {
                    builds: [36, 35, 34, 33, 32, 31, 30],
                    friendly_name: "Build AndroidPlayer [ABV]",
                    name: "proj0-Build AndroidPlayer",
                    url: "http://10.45.6.89:8001/projects/Unity%20-%20Trunk/builders/proj0-Build%20AndroidPlayer"
                },
                {
                    builds: [41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30],
                    friendly_name: "Build MacDevelopmentWebPlayer",
                    name: "proj0-Build MacDevelopmentWebPlayer",
                    url: "http://10.45.6.89:8001/projects/Unity%20-%20Trunk/builders/proj0-Build%20MacDevelopmentWebPlayer"
                }
            ]
        },
        connected: true,
        friendly_name: "mac-test-vm-v3-01",
        lastMessage: 1403612820.811,
        name: "mba01",
        url: "http://10.45.6.89:8001/buildslaves/mba01",
        version: "0.8.7p1",
        health: 0
    };

    function rawHTMLToJQuery(html, parentElement) {
        if (parentElement === undefined) {
            return $("<test/>").append($.parseHTML(html));
        }

        return $(parentElement).append($.parseHTML(html));
    }

    function expectProgressBarRendersCorrectly($elem, build) {
        var $dataDiv = $elem.find("div[data-starttime]"),
            $timeSpan = $dataDiv.find(".time-txt-js"),
            $percentDiv = $dataDiv.find(".percent-inner-js"),
            $overlayDiv = $dataDiv.find(".progressbar-overlay");

        expect($dataDiv.hasClass("percent-outer")).toBeTruthy();
        expect($dataDiv.hasClass("percent-outer-js")).toBeTruthy();
        expect(parseFloat($dataDiv.attr("data-starttime"))).toEqual(build.times[0]);
        expect(parseInt($dataDiv.attr("data-etatime"), 10)).toEqual(build.eta);

        expect($timeSpan.length).toEqual(1);
        expect($timeSpan.hasClass("time-txt")).toBeTruthy();

        expect($percentDiv.length).toEqual(1);
        expect($percentDiv.hasClass(".percent-inner"));

        expect($overlayDiv.length).toEqual(1);
    }

    var $body = $("body");

    describe("A revision cell", function () {
        var $revisionDict,
            $html;

        it("renders correctly", function () {
            $revisionDict = gt.cell.revision(0, function (data) {
                return data.latestBuild.sourceStamps;
            }, false);

            $html = $($revisionDict.mRender(undefined, undefined, builderData));

            var $rows = $html.find("li");
            expect($rows.length).toEqual(2);

            $.each($rows, function (i, row) {
                var $row = $(row),
                    $links = $row.find("a"),
                    sourceStamps = builderData.latestBuild.sourceStamps,
                    displayURL = sourceStamps[i].display_repository,
                    changesetURL = displayURL + "/changeset/" + sourceStamps[i].revision,
                    text = $row.text(),
                    textParts = text.split("/");

                expect(textParts.length).toEqual(3);
                expect(textParts[1].trim()).toEqual(sourceStamps[i].branch);

                expect($links.length).toEqual(2);

                expect($($links[0]).attr("href")).toEqual(sourceStamps[i].display_repository);
                expect($($links[0]).html()).toEqual(sourceStamps[i].codebase);

                expect($($links[1]).attr("href")).toEqual(changesetURL);
                expect($($links[1]).html()).toEqual(sourceStamps[i].revision_short);
            });
        });

        it("hides branches", function () {
            $revisionDict = gt.cell.revision(0, function (data) {
                return data.latestBuild.sourceStamps;
            }, true);
            $html = $($revisionDict.mRender(undefined, undefined, builderData));

            var $rows = $html.find("li");
            expect($rows.length).toEqual(2);

            $.each($rows, function (i, row) {
                var $row = $(row),
                    text = $row.text(),
                    textParts = text.split("/");

                expect(textParts.length).toEqual(2);
            });
        });
    });

    describe("A build ID cell", function () {
        var $buildIDDict = gt.cell.buildID(0),
            $html = rawHTMLToJQuery($buildIDDict.mRender(undefined, undefined, buildData)),
            $a = $html.find("a");

        it("renders correctly", function () {
            expect($a.length).toEqual(1);
            expect($a.attr("href")).toEqual(buildData.url.path);
            expect($a.text().trim()).toEqual("#" + buildData.number);
        });
    });

    describe("A build status cell", function () {
        var $buildStatusDict = gt.cell.buildStatus(0),
            $html,
            $spans,
            statusText = "";

        $.each(buildData.text, function (i, str) {
            statusText += str;
        });

        function renderHTML(data) {
            $html = rawHTMLToJQuery($buildStatusDict.mRender(undefined, undefined, data));
            $spans = $html.find("span");
        }

        it("renders correctly", function () {
            renderHTML(buildData);
            expect($spans.length).toEqual(2);
            $.each($spans, function (i, span) {
                expect($(span).text().trim()).toEqual(statusText);
            });
        });

        it("renders correctlXy with a dictionary url", function () {
            renderHTML(buildData);
            var $a = $html.find("a");
            
            expect($a.length).toEqual(1);
            expect($a.attr("href")).toEqual(buildData.url.path);
        });

        it("renders correctly with a string url", function () {
            var customBuildData = $.extend({}, buildData, {url: "http://www.moo.com"});
            renderHTML(customBuildData);

            var $a = $html.find("a");
            expect($a.length).toEqual(1);
            expect($a.attr("href")).toEqual(customBuildData.url);
        });
    });

    describe("A builder name cell", function () {
        var $buildNameDict = gt.cell.builderName(0),
            $html = rawHTMLToJQuery($buildNameDict.mRender(undefined, undefined, builderData));

        it("renders correctly", function () {
            var $a = $html.find("a");
            expect($a.length).toEqual(1);
            expect($a.attr("href")).toEqual(buildData.builder_url);
            expect($a.text().trim()).toEqual(buildData.builderFriendlyName);
        });
    });

    describe("A short time cell", function () {
        var $buildNameDict = gt.cell.shortTime(0, function (data) {
                return data.times[0];
            }),
            date = $buildNameDict.mRender(undefined, undefined, buildData);

        it("renders correctly", function () {
            expect(date).toEqual("June 13, 10:38:03");
        });
    });


    describe("A slave name cell", function () {
        var $buildNameDict = gt.cell.slaveName(0, "friendly_name", "url"),
            $html = rawHTMLToJQuery($buildNameDict.mRender(undefined, undefined, slaveData));

        it("renders correctly", function () {
            var $a = $html.find("a");
            expect($a.length).toEqual(1);
            expect($a.attr("href")).toEqual(slaveData.url);
            expect($a.text().trim()).toEqual(slaveData.friendly_name);
        });
    });

    describe("A slave status cell", function () {
        var $buildNameDict,
            $tr;

        function expectRendersCorrectly(status) {
            expect($tr.text().trim()).toEqual(status);
        }

        describe("with idle slave", function () {
            beforeEach(function () {
                var customSlaveData = $.extend({}, slaveData, {connected: true});
                $buildNameDict = gt.cell.slaveStatus(0);
                $tr = rawHTMLToJQuery($buildNameDict.mRender(undefined, undefined, customSlaveData), "<tr/>");
            });

            it("renders correctly", function () {
                expectRendersCorrectly("Idle");
            });
        });

        describe("with offline slave", function () {
            beforeEach(function () {
                var customSlaveData = $.extend({}, slaveData, {connected: false});
                $buildNameDict = gt.cell.slaveStatus(0);
                $tr = rawHTMLToJQuery($buildNameDict.mRender(undefined, undefined, customSlaveData), "<tr/>");
            });

            it("renders correctly", function () {
                expectRendersCorrectly("Offline");
            });
        });

        describe("with running slave", function () {
            var customSlaveData;
            var customBuilds;

            function setup(overTimeBuild) {
                customBuilds = [
                    $.extend({}, buildData, {times: [1402648683.694], eta: 0 }),
                    $.extend({}, buildData, {times: [1337], eta: 1337 }) ];

                if (overTimeBuild === true) {
                    customBuilds.push($.extend({}, buildData, {times: [745482], eta: -50 }));
                }

                customSlaveData = $.extend({}, slaveData, {connected: true, runningBuilds: customBuilds});
                $buildNameDict = gt.cell.slaveStatus(0);
                $tr = rawHTMLToJQuery($buildNameDict.mRender(undefined, undefined, customSlaveData), "<tr/>");
            }

            it("renders correctly", function () {
                setup();
                expectRendersCorrectly("2 build(s)");
                var $a = $tr.find("a"),
                    $span = $tr.find("span");

                expect($tr.hasClass("tooltip")).toBeFalsy();
                expect($tr.hasClass("overtime")).toBeFalsy();

                expect($a.length).toEqual(1);
                expect($a.hasClass("more-info")).toBeTruthy();
                expect($a.hasClass("popup-btn-json-js")).toBeTruthy();

                expect($span.length).toEqual(1);
                expect($span.hasClass("spin-icon")).toBeTruthy();
                expect($span.hasClass("animate-spin")).toBeTruthy();
            });

            it("creates the build popup", function () {
                setup();
                $buildNameDict.fnCreatedCell($tr, undefined, customSlaveData);

                var $popupButton = $tr.find('a.popup-btn-json-js');
                $popupButton.click();

                var $popup = $body.find("[data-ui-popup]");

                expect($tr.hasClass("building")).toBeTruthy();
                expect($popup.length).toEqual(1);

                var $h3 = $popup.find("h3"),
                    $ul = $popup.find("ul"),
                    $li = $ul.find("li");

                expect($h3.text()).toEqual("Running builds");

                expect($ul.hasClass("list")).toBeTruthy();
                expect($ul.hasClass("building")).toBeTruthy();
                expect($ul.hasClass("current-job-js")).toBeTruthy();

                expect($li.length).toEqual(2);
                $.each($li, function (i, l) {
                    var $l = $(l),
                        $a = $l.find("a"),
                        $spinner = $l.find(".spin-icon");

                    expect($spinner.length).toEqual(1);
                    expect($spinner.hasClass("animate-spin")).toBeTruthy();

                    expect($a.length).toEqual(2);
                    expect($($a[0]).attr("href")).toEqual(customBuilds[i].url.path);
                    expect($($a[0]).text()).toEqual("#" + customBuilds[i].number);
                    expect($($a[1]).attr("href")).toEqual(customBuilds[i].builder_url);
                    expect($($a[1]).text()).toEqual(customBuilds[i].builderFriendlyName);

                    expectProgressBarRendersCorrectly($l, customBuilds[i]);
                });
                $popup.remove();
            });

            it("shows an overtimed build", function () {
                setup(true);
                expectRendersCorrectly("3 build(s)");
                $buildNameDict.fnCreatedCell($tr, undefined, customSlaveData);

                expect($tr.hasClass("building")).toBeFalsy();
                expect($tr.hasClass("overtime")).toBeTruthy();
                expect($tr.hasClass("tooltip")).toBeTruthy();

                expect($tr.attr("title")).toEqual("One or more builds on overtime");
            });
        });
    });

    describe("build progress cell", function () {
        var $buildProgressDict,
            $tr;

        function setup(data, singleBuild) {
            $buildProgressDict = gt.cell.buildProgress(0, singleBuild);
            $tr = rawHTMLToJQuery($buildProgressDict.mRender(undefined, undefined, data), "<tr/>");
        }

        it("renders correctly", function () {
            var data = $.extend({}, buildData, {eta: 0});
            setup(data, true);

            var $ul = $tr.find("ul"),
                $li = $ul.find("li"),
                $builderStatusDiv = $li.find(".builders-status-truncate"),
                $a = $builderStatusDiv.find("a"),
                $spinner = $li.find(".spin-icon");

            expect($builderStatusDiv.length).toEqual(1);
            expect($a.attr("href")).toEqual(data.url.path);
            expect($a.text()).toEqual("#" + data.number);
            expect($spinner.length).toEqual(1);

            expectProgressBarRendersCorrectly($li, data);
        });

        it("shows multiple running builds", function () {
            var customBuildData = $.extend({}, buildData, {eta: 0});
            var data = {
                currentBuilds: [customBuildData, customBuildData, customBuildData]
            };

            setup(data, false);

            var $li = $tr.find("li");
            expect($li.length).toEqual(3);
            $.each($li, function (i, elem) {
                expectProgressBarRendersCorrectly($(elem), data.currentBuilds[i]);
            });
        });

        it("shows pending builds", function () {
            var data = $.extend({}, builderData, {pendingBuilds: 3});
            setup(data, false);

            var $a = $tr.find("a");

            expect($a.length).toEqual(1);
            expect($a.hasClass("more-info")).toBeTruthy();
            expect($a.hasClass("pending-popup")).toBeTruthy();
            expect($a.hasClass("mod-1")).toBeTruthy();

            expect($a.attr("data-buildername")).not.toBeUndefined();
            expect($a.attr("data-buildername")).toEqual(data.name);
        });
    });

    describe("A stop build cell", function () {
        var $stopBuildDict = gt.cell.stopBuild(0),
            $tr = rawHTMLToJQuery($stopBuildDict.mRender(undefined, undefined, slaveData), "<tr/>");

        it("renders correctly", function () {
            var $input = $tr.find("input[type='checkbox']"),
                $a = $tr.find("a");

            expect($input.length).toEqual(1);

            expect($a.length).toEqual(1);
            expect($a.attr("href")).toEqual("#");
            expect($a.hasClass("delete-icon")).toBeTruthy();
            expect($a.attr("data-cancel-url")).toContain("/stop/stop");
            expect($a.attr("title")).toEqual("Remove this build");
        });
    });

    describe("A build length cell", function () {
        var $tr;

        function setup(data) {
            var $buildLengthDict = gt.cell.buildLength(0, "times");
            $tr = rawHTMLToJQuery($buildLengthDict.mRender(undefined, undefined, data), "<tr/>");
        }

        it("renders correctly", function () {
            setup(buildData);
            expect($tr.text()).toEqual("3m 20s");
        });

        it("returns correctly with 2 times", function () {
            var customBuildData = $.extend({}, buildData, {times: [1402648683.694, 1402648983.858]});
            setup(customBuildData);
            expect($tr.text()).toEqual("5m 0s");
        });
    });

    describe("A slave health cell", function () {
        var $slaveHealthDict = gt.cell.slaveHealth(0);

        function checkHealthType(data, type) {
            it("renders correctly with health of " + type, function () {
                var $html = rawHTMLToJQuery($slaveHealthDict.mRender(undefined, undefined, data)),
                    $span = $html.find("span");

                expect($span.length).toEqual(1);
                expect($span.hasClass("health-icon")).toBeTruthy();
                expect($span.hasClass(type + "-health-icon")).toBeTruthy();
            });
        }

        checkHealthType($.extend({}, slaveData, {health: 0}), "good");
        checkHealthType($.extend({}, slaveData, {health: -1}), "warning");
        checkHealthType($.extend({}, slaveData, {health: -2}), "bad");
    });
});
