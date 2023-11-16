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

import './BuildSummary.scss';
import {useContext, useState} from "react";
import {observer} from "mobx-react";
import {FaExpand} from "react-icons/fa";
import {buildbotGetSettings} from "buildbot-plugin-support";
import {
  ArrowExpander,
  BadgeRound,
  BadgeStatus,
  ConfigContext,
  analyzeStepUrls,
  durationFormat,
  useCurrentTime,
  useStateWithParentTrackingWithDefaultIfNotSet,
  useStepUrlAnalyzer
} from "buildbot-ui";
import {
  Build,
  Builder,
  DataCollection,
  Log,
  Step,
  getPropertyValueOrDefault,
  results2class,
  results2text,
  SUCCESS,
  useDataAccessor,
  useDataApiDynamicQuery,
  useDataApiQuery,
} from "buildbot-data-js";
import {Link} from "react-router-dom";
import {LogPreview} from "../LogPreview/LogPreview";
import {BuildRequestSummary} from "../BuildRequestSummary/BuildRequestSummary";
import {Card} from "react-bootstrap";

enum DetailLevel {
  None = 0,
  OnlyNotSuccess = 1,
  Everything = 2,
  Count = 3
}

const detailLevelToString = (level: DetailLevel) => {
  switch (level) {
    case DetailLevel.None:
      return "None";
    case DetailLevel.OnlyNotSuccess:
      return "Problems";
    case DetailLevel.Everything:
    default:
      return "All";
  }
}

const isStepDisplayed = (step: Step, details: DetailLevel) => {
  if (details === DetailLevel.Everything) {
    return !step.hidden;
  } else if (details === DetailLevel.OnlyNotSuccess) {
    return (step.results == null) || (step.results !== SUCCESS);
  } else if (details === DetailLevel.None) {
    return false;
  }
}

const shouldExpandLog = (log: Log, logsToExpand: string) => {
  if (log.num_lines === 0) {
    return false;
  }
  return logsToExpand.toLowerCase().split(";").includes(log.name.toLowerCase());
};

const isSummaryLog = (log: Log)  => log.name.toLowerCase() === "summary";

// Returns the logs, sorted with the "Summary" log first, if it exists in the step's list of logs
const getStepLogsInDisplayOrder = (logs: DataCollection<Log>) => {
  const summaryLogs = logs.array.filter(log => isSummaryLog(log));
  return summaryLogs.concat(logs.array.filter(log => !isSummaryLog(log)));
};

type BuildSummaryStepLineProps = {
  build: Build;
  step: Step;
  logs: DataCollection<Log>;
  parentFullDisplay: boolean
}

function getTimeTextForStep(step: Step, now: number) {
  const lockDuration = step.locks_acquired_at !== null
    ? step.locks_acquired_at - step.started_at!
    : 0;

  if (step.complete) {
    const stepDurationText = durationFormat(step.complete_at! - step.started_at!);

    if (lockDuration > 1) {
      // Since lock delay includes general step setup overhead, then sometimes the started_at and locks_acquired_at
      // may fall into different seconds. However, it's unlikely that step setup would take more than one second.
      return `${stepDurationText} (${durationFormat(lockDuration)} spent waiting for locks)`
    }
    return stepDurationText;
  }

  const ongoingStepDurationText = durationFormat(now - step.started_at!);
  if (lockDuration > 1) {
    // Since lock delay includes general step setup overhead, then sometimes the started_at and locks_acquired_at
    // may fall into different seconds. However, it's unlikely that step setup would take more than one second.
    return `${ongoingStepDurationText} (${durationFormat(lockDuration)} spent waiting for locks)`
  }

  return ongoingStepDurationText;
}

const BuildSummaryStepLine = observer(({build, step, logs, parentFullDisplay}: BuildSummaryStepLineProps) => {
  const config = useContext(ConfigContext);
  const now = useCurrentTime();

  const logsToExpand = buildbotGetSettings().getStringSetting("LogPreview.expand_logs");
  const showUrls = buildbotGetSettings().getBooleanSetting("Build.show_urls");

  const baseUrls = config.buildbotURLs || [config.buildbotURL];
  const stepUrlAnalyzer = useStepUrlAnalyzer(baseUrls);

  const [fullDisplay, setFullDisplay] = useStateWithParentTrackingWithDefaultIfNotSet(
    parentFullDisplay, () => !step.complete || (step.results !== SUCCESS));

  const renderState = () => {
    if (step.started_at === null) {
      return <></>;
    }

    return (
      <span className="bb-build-summary-time">
          {getTimeTextForStep(step, now)}
        &nbsp;
        {step.state_string}
        </span>
    );
  }

  const stepInfo = analyzeStepUrls(stepUrlAnalyzer, step.urls);

  const maybeRenderArrowExpander = () => {
    if ( logs.array.length > 0 || stepInfo.buildrequests.length > 0 ||
        (stepInfo.otherUrls.length > 0 && !showUrls)) {
      return <ArrowExpander isExpanded={fullDisplay}/>;
    }
    return null;
  }

  const maybeRenderPendingBuildCount = () => {
    if (stepInfo.buildrequests.length === 0) {
      return null;
    }
    return (
      <span>
        {stepInfo.builds.length} builds,
        {stepInfo.buildrequests.length - stepInfo.builds.length} pending builds
      </span>
    );
  }

  const renderStepUrls = () => {
    const urlElements = stepInfo.otherUrls.map((url, index) => {
      return (
        <li key={index}>
          <a href={url.url} rel="noreferrer" target="_blank">
            {url.name}
          </a>
        </li>
      );
    });

    return <ul>{urlElements}</ul>;
  }

  const renderStepLogs = () => {
    return getStepLogsInDisplayOrder(logs).map(log => {
      const initialFullDisplay = logs.array.length === 1 || shouldExpandLog(log, logsToExpand);
      return (
        <LogPreview key={log.id} builderid={build.builderid} buildnumber={build.number}
                    stepnumber={step.number} log={log} initialFullDisplay={initialFullDisplay}/>
      );
    });
  }

  const renderFullInfo = () => {
    // TODO implement pagination of build requests
    return (
      <div className="anim-stepdetails">
        {!showUrls ? renderStepUrls() : <></>}
        <ul className="list-unstyled group-results">
          {stepInfo.buildrequests.map(brInfo => (
            <li key={brInfo.buildrequestid}>
              <BuildRequestSummary buildrequestid={brInfo.buildrequestid}/>
            </li>
          ))}
        </ul>
        {renderStepLogs()}
      </div>
    );
  }

  return (
    <li key={step.id} className="list-group-item">
      <div onClick={() => setFullDisplay(!fullDisplay)}>
        <BadgeRound className={results2class(step, 'pulse')}>{step.number.toString()}</BadgeRound>
        &nbsp;
        {maybeRenderArrowExpander()}
        &nbsp;
        {step.name}
        {renderState()}
        {maybeRenderPendingBuildCount()}
      </div>
      {showUrls ? renderStepUrls() : <></>}
      {fullDisplay ? renderFullInfo() : <></>}
    </li>
  )
})

type BuildSummaryProps = {
  build: Build;
  parentBuild: Build | null;
  parentRelationship: string | null;
  condensed: boolean;
}

export const BuildSummary = observer(({build, parentBuild, parentRelationship,
                                       condensed}: BuildSummaryProps) => {
  const accessor = useDataAccessor([build.id]);
  const now = useCurrentTime();

  const propertiesQuery = useDataApiQuery(() => build.getProperties());
  const stepsQuery = useDataApiQuery(() => build.getSteps());
  const builderQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: build.builderid.toString()}));
  const builderBuilderQuery = useDataApiDynamicQuery([parentBuild !== null],
    () => parentBuild === null
      ? new DataCollection<Builder>()
      : Builder.getAll(accessor, {id: parentBuild.builderid.toString()}));
  const logsQuery = useDataApiQuery(() => stepsQuery.getRelated(step => step.getLogs()));

  const [detailLevel, setDetailLevel] =
    useState<DetailLevel>(condensed ? DetailLevel.None : DetailLevel.Everything);

  const builder = builderQuery.getNthOrNull(0);
  const parentBuilder = builderBuilderQuery.getNthOrNull(0);
  const stepsToDisplay = stepsQuery.array.filter(step => isStepDisplayed(step, detailLevel));

  const reason = getPropertyValueOrDefault(propertiesQuery.properties, "reason", null);

  // FIXME: implement trigger URL pagination

  const [fullDisplay, setFullDisplay] = useState(false);

  const toggleDetails = () => {
    setDetailLevel(level => (level + 1) % DetailLevel.Count);
  };

  const renderParentBuildLink = () => {
    if (parentBuild === null || parentBuilder === null) {
      return <></>
    }

    const relationship = parentRelationship === null ? "" : parentRelationship;
    return (
      <span>
        <Link to={`/builders/${parentBuild.builderid}/builds/${parentBuild.number}`}>
          <BadgeStatus className={results2class(parentBuild, null)}>
            <>{relationship}:{parentBuilder.name}/{parentBuild.number}</>
          </BadgeStatus>
        </Link>
      </span>
    );
  }

  const stepElements = stepsToDisplay.map(step => (
    <BuildSummaryStepLine key={step.id} build={build} step={step}
                          logs={logsQuery.getParentCollectionOrEmpty(step.id)}
                          parentFullDisplay={fullDisplay}/>
  ));

  return (
    <Card className={"bb-build-summary " + results2class(build, null)}>
      <Card.Header>
        <div onClick={() => setFullDisplay(!fullDisplay)} title="Expand all step logs"
             className="btn btn-xs btn-default">
          <ArrowExpander isExpanded={fullDisplay}/>
        </div>
        <div onClick={toggleDetails} title="Show steps according to their importance"
             className="btn btn-xs btn-default">
          <FaExpand/>
          {detailLevelToString(detailLevel)}
        </div>
        { builder !== null
          ? <Link to={`/builders/${build.builderid}/builds/${build.number}`}>
              &nbsp;
              {builder.name}/{build.number}
            </Link>
          : <></>
        }
        {reason !== null ? <span>| {reason}</span> : <></>}
        <div className={"bb-build-summary-details"}>
          {
            build.complete
              ? <span>{durationFormat(build.complete_at! - build.started_at)}&nbsp;</span>
              : <span>{durationFormat(now - build.started_at)}&nbsp;</span>
          }
          <span>{build.state_string}&nbsp;</span>
          <BadgeStatus className={results2class(build, null)}>{results2text(build)}</BadgeStatus>
          {renderParentBuildLink()}
        </div>
      </Card.Header>
      <ul className="list-group">
        {stepElements}
      </ul>
    </Card>
  );
});
