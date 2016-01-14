/*global define, describe, it, expect, beforeEach, afterEach, spyOn*/
define(function (require) {
    "use strict";

    var $ = require("jquery"),
        rtBuilders = require("rtBuilders"),
        helpers = require("helpers"),
        nightlyTag = "Nightly",
        abvTag = [
            ["ABV"]
        ],
        abvNightlyTag = [
            ["ABV", "Nightly"]
        ],
        trunk = [
            ["Trunk"]
        ],
        trunkNightly = [
            ["Trunk-Nightly"]
        ],
        unity46 = [
            ["4.6"]
        ],
        unity46Nightly = [
            ["4.6-Nightly"]
        ],
        noTags = [
            []
        ],
        trunkWIPTags = [
          ["Trunk", "WIP"]
        ],
        unstableNightly = [
            ["Nightly", "Unstable"]
        ],
        simpleBuilders = [
            abvTag,
            noTags,
            abvNightlyTag,
            trunkWIPTags
        ],
        expandedBuilders = [
            trunk,
            trunkNightly,
            unity46,
            unity46Nightly,
            noTags,
            abvNightlyTag,
            trunkWIPTags
        ],
        unstableBuilders = [
            abvTag,
            noTags,
            abvNightlyTag,
            unstableNightly,
            trunkWIPTags,
            trunk
        ],
        allTags = [
            {tags: abvTag[0]},
            {tags: trunk[0]},
            {tags: trunkNightly[0]},
            {tags: unity46[0]},
            {tags: unity46Nightly[0]}
        ],
        filter = rtBuilders.filterByTags(0);

    function testTagFilter(tests, builders) {
        $.each(tests, function eachTest(i, test) {

            // Replace the selected tags function
            rtBuilders.getSelectedTags = function () {
                return test.tags;
            };

            // Replace the codebases from url function
            helpers.codebasesFromURL = function () {
                if (test.branch !== undefined) {
                    return {unity_branch: test.branch};
                }

                return {}
            };

            // Set if hiding unstable
            if (test.hide_unstable === true) {
                rtBuilders.setHideUnstable(true);
            } else {
                rtBuilders.setHideUnstable(false);
            }

            // Set filtering condition
            if (test.and_condition === true) {
                rtBuilders.orCondition = function(){
                    return false;
                };
            } else {
                 rtBuilders.orCondition = function(){
                    return true;
                };
            }

            var result = $.grep(builders, function (a) {
                return filter(undefined, undefined, undefined, {tags: a[0]});
            });

            expect(result).toEqual(test.result);
        });
    }

    describe("Builder tags", function () {
        rtBuilders.findAllTags(allTags);

        it("are filtered", function () {
            var tests = [
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV"]},
                {branch: "", result: [abvNightlyTag], tags: ["Nightly"]},
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV", "Nightly"]}
            ];

            testTagFilter(tests, simpleBuilders);
        });

        it("are filtered - OR condition with AND enabled", function () {
            var tests_and = [
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV"], and_condition: true},
                {branch: "", result: [abvNightlyTag], tags: ["Nightly"], and_condition: true},
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV", "Nightly"], and_condition: true}
            ];

            testTagFilter(tests_and, simpleBuilders);

        });

        it("are filtered - AND condition", function () {
            var tests_and = [
                {branch: "", result: [abvNightlyTag], tags: ["ABV,Nightly"], and_condition: true},
                {branch: "", result: [unstableNightly], tags: ["Nightly,Unstable"], and_condition: true},
                {branch: "", result: [abvTag, abvNightlyTag, unstableNightly], tags: ["ABV", "Nightly,Unstable"], and_condition: true}
            ];

            testTagFilter(tests_and, unstableBuilders);
        });

        it("are not filtered when no tags are selected", function () {
            var tests = [
                {branch: "", result: expandedBuilders, tags: []},
                {branch: "trunk", result: [trunk, trunkNightly, noTags, abvNightlyTag, trunkWIPTags], tags: []},
                {branch: "release/5.0/test", result: [trunk, trunkNightly, noTags, abvNightlyTag, trunkWIPTags], tags: []},
                {branch: "release/4.6/test", result: [unity46, unity46Nightly, noTags, abvNightlyTag], tags: []}
            ];

            testTagFilter(tests, expandedBuilders);
        });

        it("are not filtered when no tags are selected - OR condition with AND enabled", function () {
            var tests = [
                {branch: "", result: expandedBuilders, tags: []},
                {branch: "trunk", result: [trunk, trunkNightly, noTags, abvNightlyTag, trunkWIPTags], tags: [], and_condition: true},
                {branch: "release/5.0/test", result: [trunk, trunkNightly, noTags, abvNightlyTag, trunkWIPTags], tags: [], and_condition: true},
                {branch: "release/4.6/test", result: [unity46, unity46Nightly, noTags, abvNightlyTag], tags: [], and_condition: true}
            ];

            testTagFilter(tests, expandedBuilders);
        });

        it("filters tags based on branch", function () {
            var noTagsTag = rtBuilders.noTag,
                tests = [
                    {branch: "trunk", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag]},
                    {branch: "release/4.6/test", result: [unity46Nightly, abvNightlyTag], tags: [nightlyTag]},
                    {branch: "5.0/release/test", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag]},
                    {branch: "5.1/release/test", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag]},
                    {branch: "test", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag]},
                    {branch: undefined, result: [abvNightlyTag], tags: [nightlyTag]},
                    {branch: undefined, result: expandedBuilders, tags: []},
                    {branch: undefined, result: [noTags], tags: [noTagsTag]},
                    {branch: "trunk", result: [trunk, noTags], tags: [noTagsTag]}
                ];

            testTagFilter(tests, expandedBuilders);

        });

        it("filters tags based on branch - OR condition with AND enabled", function () {
            var noTagsTag = rtBuilders.noTag,
                tests = [
                    {branch: "trunk", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag], and_condition: true},
                    {branch: "release/4.6/test", result: [unity46Nightly, abvNightlyTag], tags: [nightlyTag], and_condition: true},
                    {branch: "5.0/release/test", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag], and_condition: true},
                    {branch: "5.1/release/test", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag], and_condition: true},
                    {branch: "test", result: [trunkNightly, abvNightlyTag], tags: [nightlyTag], and_condition: true},
                    {branch: undefined, result: [abvNightlyTag], tags: [nightlyTag], and_condition: true},
                    {branch: undefined, result: expandedBuilders, tags: [], and_condition: true},
                    {branch: undefined, result: [noTags], tags: [noTagsTag], and_condition: true},
                    {branch: "trunk", result: [trunk, noTags], tags: [noTagsTag], and_condition: true}
                ];

            testTagFilter(tests, expandedBuilders);
        });

        it("filters tags based on branch - AND condition", function () {
            var noTagsTag = rtBuilders.noTag,
                tests = [
                    {branch: "trunk", result: [abvNightlyTag], tags: ["ABV,Nightly"], and_condition: true},
                    {branch: "release/4.6/test", result: [abvNightlyTag], tags: ["ABV,Nightly"], and_condition: true},
                    {branch: "5.0/release/test", result: [abvNightlyTag], tags: ["ABV,Nightly"], and_condition: true},
                    {branch: "5.1/release/test", result: [abvNightlyTag], tags: ["ABV,Nightly"], and_condition: true},
                    {branch: "test", result: [abvNightlyTag], tags: ["ABV,Nightly"], and_condition: true},
                    {branch: undefined, result: [abvNightlyTag], tags: ["ABV,Nightly"], and_condition: true}
                ];

            testTagFilter(tests, expandedBuilders);
        });

        it("hides tags not for this branch", function () {
            var tags = [
                {tag: "ABV", branch_type: "4.6", result: true},
                {tag: "4.6-ABV", branch_type: "4.6", result: true},
                {tag: "Trunk-ABV", branch_type: "4.6", result: false},
                {tag: "Trunk-ABV", branch_type: "trunk", result: true},
                {tag: "NoBranch", branch_type: undefined, result: true},
                {tag: "4.6", branch_type: "4.6", result: false},
                {tag: "Trunk", branch_type: "Trunk", result: false}
            ];

            $.each(tags, function (i, dict) {
                expect(rtBuilders.tagVisibleForBranch(dict.tag, dict.branch_type)).toEqual(dict.result);
            });
        });

        it("hides tags not for this branch - OR condition with AND enabled", function () {
            var tags = [
                {tag: "ABV", branch_type: "4.6", result: true, and_condition: true},
                {tag: "4.6-ABV", branch_type: "4.6", result: true, and_condition: true},
                {tag: "Trunk-ABV", branch_type: "4.6", result: false, and_condition: true},
                {tag: "Trunk-ABV", branch_type: "trunk", result: true, and_condition: true},
                {tag: "NoBranch", branch_type: undefined, result: true, and_condition: true},
                {tag: "4.6", branch_type: "4.6", result: false, and_condition: true},
                {tag: "Trunk", branch_type: "Trunk", result: false, and_condition: true}
            ];

            $.each(tags, function (i, dict) {
                expect(rtBuilders.tagVisibleForBranch(dict.tag, dict.branch_type)).toEqual(dict.result);
            });
        });

        it("format correctly", function () {
            var tags = [
                {tag: "4.6-ABV", branch_type: "4.6", result: "ABV"},
                {tag: "Trunk-ABV", branch_type: "trunk", result: "ABV"},
                {tag: "ABV", branch_type: "trunk", result: "ABV"},
                {tag: ["Nightly", "4.6-ABV"], branch_type: "4.6", result: ["Nightly", "ABV"]},
                {tag: "4.6-ABV", branch_type: undefined, result: "4.6-ABV"}
            ];

            $.each(tags, function (i, dict) {
                expect(rtBuilders.formatTags(dict.tag, dict.branch_type)).toEqual(dict.result);
            });
        });

        it("format correctly - OR condition with AND enabled", function () {
            var tags = [
                {tag: "4.6-ABV", branch_type: "4.6", result: "ABV", and_condition: true},
                {tag: "Trunk-ABV", branch_type: "trunk", result: "ABV", and_condition: true},
                {tag: "ABV", branch_type: "trunk", result: "ABV", and_condition: true},
                {tag: ["Nightly", "4.6-ABV"], branch_type: "4.6", result: ["Nightly", "ABV"], and_condition: true},
                {tag: "4.6-ABV", branch_type: undefined, result: "4.6-ABV", and_condition: true}
            ];

            $.each(tags, function (i, dict) {
                expect(rtBuilders.formatTags(dict.tag, dict.branch_type)).toEqual(dict.result);
            });
        });

        it("are filtered and hide unstable", function () {
            var tests = [
                {branch: "", result: [trunk], tags: ["Trunk"], hide_unstable: true},
                {branch: "", result: [trunkWIPTags, trunk], tags: ["Trunk"], hide_unstable: false},
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV"], hide_unstable: true},
                {branch: "", result: [abvNightlyTag, unstableNightly], tags: ["Nightly"], hide_unstable: false},
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV", "Nightly"], hide_unstable: true},
            ];

            testTagFilter(tests, unstableBuilders);
        });

         it("are filtered and hide unstable - OR condition with AND enabled", function () {
            var tests = [
                {branch: "", result: [trunk], tags: ["Trunk"], hide_unstable: true, and_condition: true},
                {branch: "", result: [trunkWIPTags, trunk], tags: ["Trunk"], hide_unstable: false, and_condition: true},
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV"], hide_unstable: true, and_condition: true},
                {branch: "", result: [abvNightlyTag, unstableNightly], tags: ["Nightly"], hide_unstable: false, and_condition: true},
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["ABV", "Nightly"], hide_unstable: true, and_condition: true},
            ];

            testTagFilter(tests, unstableBuilders);
        });

        it("are filtered and hide unstable - AND condition", function () {
            var tests = [
                {branch: "", result: [], tags: ["Nightly,Unstable"], hide_unstable: true, and_condition: true},
                {branch: "", result: [abvTag, abvNightlyTag], tags: ["Nightly,Unstable", "ABV"], hide_unstable: true, and_condition: true}
            ];

            testTagFilter(tests, unstableBuilders);
        });
    });

    describe("Builder page", function () {
        it("produces the right branch type", function () {
            var branches = [
                {branch: "trunk", branch_type: "trunk"},
                {branch: "5.0/release/test", branch_type: "trunk"},
                {branch: "release/4.6/test", branch_type: "4.6"},
                {branch: "5.0/ai/test", branch_type: "trunk"}
            ];


            $.each(branches, function (i, dict) {
                helpers.codebasesFromURL = function () {
                    return {unity_branch: dict.branch};
                };

                var branch_type = rtBuilders.getBranchType();
                expect(branch_type).toEqual(dict.branch_type);
            });
        })

    });
});
