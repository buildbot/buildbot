/*global define, describe, it, expect, beforeEach, afterEach, spyOn*/
define(function (require) {
    "use strict";

    var $ = require("jquery"),
        rtBuildDetails = require("rtBuildDetail");


    describe("Build details test reports", function () {
        it("returns xml report if json report doesn't exist", function () {
            var data = {
                steps : [],
                logs  :[["TestResults.xml", "link/TestResults.xml"], ["TestReport.html", "link/TestReport.html"]]
            };

            var html = $(rtBuildDetails.processArtifacts(data));

            var xmlLink = html.find('a[href="'+data.logs[0][1]+'"]:contains("'+data.logs[0][0] +'")')  ;
            var htmlLink = html.find('a[href="'+data.logs[1][1]+'"]:contains("'+data.logs[1][0] +'")')  ;

            expect(xmlLink.length).toEqual(1);
            expect(htmlLink.length).toEqual(1);
        });

        it("returns json report if json report exists", function () {
            var data = {
                steps : [],
                logs  :[["ReportData.json", "link/ReportData.json"], ["TestReport.html", "link/TestReport.html"]]
            };

            var html = $(rtBuildDetails.processArtifacts(data));

            var xmlLink = html.find('a[href="'+data.logs[0][1]+'"]:contains("'+data.logs[0][0] +'")')  ;
            var htmlLink = html.find('a[href="'+data.logs[1][1]+'"]:contains("'+data.logs[1][0] +'")')  ;

            expect(xmlLink.length).toEqual(1);
            expect(htmlLink.length).toEqual(1);
        });

        it("returns json report if json and xml report exists", function () {
            var data = {
                steps : [],
                logs  :[["TestResults.xml", "link/TestResults.xml"],
                        ["TestReport.html", "link/TestReport.html"],
                        ["ReportData.json", "link/ReportData.json"],
                        ["TestReport.html", "link/TestReport.html"],
                        ["TestResults2.xml", "link/TestResults2.xml"]]
            };

            var html = $(rtBuildDetails.processArtifacts(data));

            var aElements = html.find('li a');
            var xmlLink = html.find('a[href="'+data.logs[2][1]+'"]:contains("'+data.logs[2][0] +'")')  ;
            var htmlLink = html.find('a[href="'+data.logs[3][1]+'"]:contains("'+data.logs[3][0] +'")')  ;

            expect(aElements.length).toEqual(2);
            expect(xmlLink.length).toEqual(1);
            expect(htmlLink.length).toEqual(1);
        });

         it("if logs list contains the same keys result will render the last one", function () {
            var data = {
                steps : [],
                logs  :[["TestResults.xml", "the/first/link/TestResults.xml"],
                        ["TestReport.html", "link/TestReport.html"],
                        ["ReportData.json", "link/ReportData.json"],
                        ["TestReport.html", "the/second/link/TestReport.html"]]
            };

            var html = $(rtBuildDetails.processArtifacts(data));

            var aElements = html.find('li a');
            var xmlLink = html.find('a[href="'+data.logs[3][1]+'"]:contains("'+data.logs[3][0] +'")')  ;
            var htmlLink = html.find('a[href="'+data.logs[3][1]+'"]:contains("'+data.logs[3][0] +'")')  ;

            expect(aElements.length).toEqual(2);
            expect(xmlLink.length).toEqual(1);
            expect(htmlLink.length).toEqual(1);
        });
    });
});
