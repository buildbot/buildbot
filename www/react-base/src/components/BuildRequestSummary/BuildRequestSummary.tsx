/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import './BuildRequestSummary.scss';
import {observer} from "mobx-react";
import {Card} from "react-bootstrap";
import {useDataAccessor, useDataApiQuery} from "../../data/ReactUtils";
import {Buildrequest} from "../../data/classes/Buildrequest";
import {Builder} from "../../data/classes/Builder";
import BadgeStatus from "../BadgeStatus/BadgeStatus";
import BuildSummary from "../BuildSummary/BuildSummary";
import {Buildset} from "../../data/classes/Buildset";
import {Link} from "react-router-dom";

type BuildRequestSummaryProps = {
  buildrequestid: string;
}

const BuildRequestSummary = observer(({buildrequestid}: BuildRequestSummaryProps) => {
  const accessor = useDataAccessor([buildrequestid]);

  const buildRequestQuery = useDataApiQuery(
    () => Buildrequest.getAll(accessor, {id: buildrequestid}));
  const buildsetsQuery = useDataApiQuery(() => buildRequestQuery.getRelated(
    br => Buildset.getAll(accessor, {id: br.buildsetid.toString()})));
  const buildsQuery = useDataApiQuery(() => buildRequestQuery.getRelated(br => br.getBuilds()));
  const builderQuery = useDataApiQuery(() => buildRequestQuery.getRelated(
    br => Builder.getAll(accessor, {id: br.builderid.toString()})));

  const buildRequest = buildRequestQuery.getNthOrNull(0);
  const builds = buildsQuery.getParentCollectionOrEmpty(buildrequestid);
  const buildset = buildsetsQuery.getNthOrNull(0);
  const builder = builderQuery.getNthOrNull(0);

  const buildElements = builds.array.map(build => (
    <BuildSummary build={build} condensed={true} parentBuild={null} parentRelationship={null}/>
  ));

  const renderBuildRequestDetails = () => {
    if (buildRequest === null) {
      return <>loading buildrequests details...</>
    }

    const reason = buildset === null ? "(loading ...)" : buildset.reason;
    const builderName = builder === null ? "loading ... " : builder.name;

    return (
      <>
        <div className="flex-grow-1">
          <Link to={`/builders/${buildRequest.builderid}`}>{builderName}</Link>
          / buildrequests /
          <Link to={`/buildrequests/${buildrequestid}`}>{buildrequestid}</Link>
          | {reason}
        </div>
        <div className="flex-grow-1 text-right">
          <span>waiting for available worker and locks</span>
          <BadgeStatus className="results_PENDING">...</BadgeStatus>
        </div>
      </>
    );
  }

  const renderPendingBuilds = () => {
    return (
      <div>
        <Card className="bb-build-request-summary-pending-panel results_PENDING">
          <Card.Header className="no-select">
            <div className="flex-row">
              {renderBuildRequestDetails()}
            </div>
          </Card.Header>
        </Card>
      </div>
    )
  }

  return (
    <div className="bb-build-request-summary">
      <>
        {buildElements}
        {builds.array.length === 0 ? renderPendingBuilds() : <></>}
      </>
    </div>
  );
});

export default BuildRequestSummary;
