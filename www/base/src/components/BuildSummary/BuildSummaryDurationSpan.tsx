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

import './BuildSummaryDurationSpan.scss';
import {Build, Step} from "buildbot-data-js";
import {buildDurationFormatWithLocks, dateFormatSeconds, stepDurationFormatWithLocks} from "buildbot-ui";
import {OverlayTrigger, Tooltip} from "react-bootstrap";
import {OverlayInjectedProps} from "react-bootstrap/Overlay";

type BuildSummaryDurationSpanProps = {
  durationString: string;
  startedAt: number|null;
  completeAt: number|null
}

const BuildSummaryDurationSpan = ({durationString, startedAt, completeAt}: BuildSummaryDurationSpanProps) => {

  const renderTimeOverlay = (props: OverlayInjectedProps) => {
    const rows: JSX.Element[] = [];
    if (startedAt !== null) {
      rows.push(<tr key={"started-at"}><td>Started at: {dateFormatSeconds(startedAt)}</td></tr>)
    }
    if (completeAt !== null) {
      rows.push(<tr key={"complete-at"}><td>Completed at: {dateFormatSeconds(completeAt)}</td></tr>)
    }
    return (
      <Tooltip id="bb-build-summary-duration-tooltip" {...props}>
        <table><tbody>{rows}</tbody></table>
      </Tooltip>
    );
  }

  return (
    <OverlayTrigger placement="bottom"
                    overlay={renderTimeOverlay}>
      <span className={"bb-build-summary-duration"}>{durationString}</span>
    </OverlayTrigger>
  );
};

type BuildSummaryStepDurationSpanProps = {
  step: Step;
  now: number;
}

export const BuildSummaryStepDurationSpan = ({step, now}: BuildSummaryStepDurationSpanProps) => {
  const durationString = stepDurationFormatWithLocks(step, now);

  return <BuildSummaryDurationSpan durationString={durationString}
                                   startedAt={step.started_at}
                                   completeAt={step.complete_at}/>;
};

type BuildSummaryBuildDurationSpanProps = {
  build: Build;
  now: number;
}

export const BuildSummaryBuildDurationSpan = ({build, now}: BuildSummaryBuildDurationSpanProps) => {

  const durationString = buildDurationFormatWithLocks(build, now);

  return <BuildSummaryDurationSpan durationString={durationString}
                                   startedAt={build.started_at}
                                   completeAt={build.complete_at}/>;
};
