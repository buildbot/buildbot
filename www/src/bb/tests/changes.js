// This file is part of Buildbot.  Buildbot is free software: you can
// redistribute it and/or modify it under the terms of the GNU General Public
// License as published by the Free Software Foundation, version 2.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
// details.
//
// You should have received a copy of the GNU General Public License along with
// this program; if not, write to the Free Software Foundation, Inc., 51
// Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
//
// Copyright Buildbot Team Members

define(["dojo/main", "doh/main", "bb/tests/utils"], function(dojo, doh, utils){
    utils.registerBBTests(doh, "/changes", "changes",[
        function addChanges(t) {
            if(window.WebSocket) { /* dont test if browser has no WebSocket support
                                      this is the case of webkit/ghost :-( */
            var query = "#dgrid_0-row-24 td.field-revision";
                return utils.when(
                    utils.playTestScenarioWaitForDomChange(
                        "buildbot.test.scenarios.base.BaseScenario.addChanges",
                        query),
                    function() {
                        utils.assertDomText(t,"0e92a098b10", query);
                    });
            }
        }
    ]);
});
