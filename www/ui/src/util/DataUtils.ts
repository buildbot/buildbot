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

import {Build, Builder, DataCollection, Master, Step} from "buildbot-data-js";
import {durationFormat} from "./Moment";

export function hasActiveMaster(builder: Builder, masters: DataCollection<Master>) {
  if ((builder.masterids == null)) {
    return false;
  }
  let active = false;
  for (let mid of builder.masterids) {
    const m = masters.getByIdOrNull(mid.toString());
    if (m !== null && m.active) {
      active = true;
    }
  }
  if (builder.tags.includes('_virtual_')) {
    active = true;
  }
  return active;
};

export function buildDurationFormatWithLocks(build: Build, now: number) {
  let res = build.complete
    ? durationFormat(build.complete_at! - build.started_at)
    : durationFormat(now - build.started_at);

  if (build.locks_duration_s > 0) {
    res += ` (locks: ${durationFormat(build.locks_duration_s!)})`;
  }
  return res;
}

export function stepDurationFormatWithLocks(step: Step, now: number) {
  const lockDuration = step.locks_acquired_at !== null
    ? step.locks_acquired_at - step.started_at!
    : 0;

  if (step.complete) {
    const stepDurationText = durationFormat(step.complete_at! - step.started_at!);

    if (lockDuration > 1) {
      // Since lock delay includes general step setup overhead, then sometimes the started_at and
      // locks_acquired_at may fall into different seconds. However, it's unlikely that step setup
      // would take more than one second.
      return `${stepDurationText} (locks: ${durationFormat(lockDuration)})`
    }
    return stepDurationText;
  }

  const ongoingStepDurationText = durationFormat(now - step.started_at!);
  if (lockDuration > 1) {
    // Since lock delay includes general step setup overhead, then sometimes the started_at and
    // locks_acquired_at may fall into different seconds. However, it's unlikely that step setup
    // would take more than one second.
    return `${ongoingStepDurationText} (locks: ${durationFormat(lockDuration)})`
  }

  return ongoingStepDurationText;
}
