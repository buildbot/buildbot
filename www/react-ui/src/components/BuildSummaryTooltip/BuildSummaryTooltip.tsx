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

import './BuildSummaryTooltip.scss';
import {useContext} from "react";
import {observer} from "mobx-react";
import {
  Builder,
  Build,
  Step,
  getPropertyValueOrDefault,
  useDataAccessor,
  useDataApiQuery,
  results2class,
  results2text
} from "buildbot-data-js";
import {ConfigContext} from "../../contexts/Config";
import {buildDurationFormatWithLocks, stepDurationFormatWithLocks} from "../../util/DataUtils";
import {useCurrentTime} from "../../util/Moment";
import {analyzeStepUrls, useStepUrlAnalyzer} from "../../util/StepUrls";
import {BadgeRound} from "../BadgeRound/BadgeRound";
import {BadgeStatus} from "../BadgeStatus/BadgeStatus";
import Card from 'react-bootstrap/Card';
import React from "react";

const isStepDisplayed = (step: Step) => {
  return !step.hidden;
}

const limitStringLength = (s: string, limit: number) => {
  let res = s.slice(0, limit);
  if (s.length > limit) {
    res += ' ...';
  }
  return res;
}

type BuildSummaryTooltipProps = {
  build: Build;
}

export const BuildSummaryTooltip = observer(({build}: BuildSummaryTooltipProps) => {
  const accessor = useDataAccessor([build.id]);
  const config = useContext(ConfigContext);

  const propertiesQuery = useDataApiQuery(() => build.getProperties());
  const stepsQuery = useDataApiQuery(() => build.getSteps());
  const builderQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: build.builderid.toString()}));

  const builder = builderQuery.getNthOrNull(0);
  const stepsToDisplay = stepsQuery.array.filter(isStepDisplayed);

  const buildResultClass = build !== null ? " " + results2class(build, null) : "";

  const reason = getPropertyValueOrDefault(propertiesQuery.properties, "reason", null);

  const baseUrls = config.buildbotURLs || [config.buildbotURL];
  const stepUrlAnalyzer = useStepUrlAnalyzer(baseUrls);

  const now = useCurrentTime();

  const headerElements: JSX.Element[] = [];

  if (build !== null) {
    headerElements.push((
      <div key="build" className="flex-row">
        <div className="flex-grow-1">
          <span>{builder !== null ? limitStringLength(builder.name, 80) : ''}</span>
          <BadgeRound className={buildResultClass}>{build.number.toString()}</BadgeRound>
          { reason !== null
            ? <span>&nbsp; | {reason}</span>
            : <></>
          }
        </div>
      </div>
    ));

    headerElements.push((
      <div key="result" className="flex-row">
        <div className="flex-grow-1">
          { buildDurationFormatWithLocks(build, now) }
          &nbsp;
          { limitStringLength(build.state_string, 80) }
          &nbsp;
          <BadgeStatus className={buildResultClass}>{results2text(build)}</BadgeStatus>
        </div>
      </div>
    ));
  } else {
    headerElements.push((
      <div key="build" className="flex-row">loading build details...</div>
    ));
  }

  const stepElements = stepsToDisplay.map((step, index) => {
    if (index >= 3 && index < stepsToDisplay.length - 3) {
      if (index === 3) {
        return (
          <li key={index} className="list-group-item">
            <div className="text-left">
              <span className="bb-buildsummary-tooltip-collapsed-entries">⋮</span>
            </div>
          </li>
        )
      } else {
        return <React.Fragment key={index}/>;
      }
    }

    let stepInfoWhenStarted: JSX.Element | null = null;
    if (step.started_at !== null) {
      stepInfoWhenStarted = (
        <span className="bb-buildsummary-tooltip-step-time">
            { stepDurationFormatWithLocks(step, now) }
          &nbsp;
          {limitStringLength(step.state_string, 40)}
        </span>
      );
    }

    const stepInfo = analyzeStepUrls(stepUrlAnalyzer, step.urls);

    let stepBuildInfoElement: JSX.Element | null = null;
    if (stepInfo.buildrequests.length > 0) {
      stepBuildInfoElement = (
        <span>
          {stepInfo.builds.length} builds,
          {stepInfo.buildrequests.length - stepInfo.builds.length} pending builds
        </span>
      );
    }

    return (
      <li key={index} className="list-group-item">
        <div className="clearfix">
          <span className="bb-buildsummary-tooltip-step-badge">
            <BadgeRound className={results2class(step, 'pulse')}>{step.number.toString()}</BadgeRound>
            &nbsp;
          </span>
          <span className="bb-buildsummary-tooltip-step-name">{limitStringLength(step.name, 40)}
            {stepBuildInfoElement}
          </span>
          <span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
          {stepInfoWhenStarted}
        </div>
      </li>
    )
  });

  return (
    <Card style={{marginBottom: "0px"}} className={buildResultClass}>
      <Card.Header>{headerElements}</Card.Header>
      <ul className="list-group">
        {stepElements}
      </ul>
    </Card>
  );
});
