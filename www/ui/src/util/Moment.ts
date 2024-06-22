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

import moment from "moment";
import {useContext, useEffect} from "react";
import {TimeContext} from "../contexts/Time";

export function durationFormat(time: number) {
  if (time < 0) {
    return "";
  }

  const d = moment.duration(time * 1000);
  const m = moment.utc(d.asMilliseconds());
  const days = Math.floor(d.asDays());
  if (days) {
    let plural = "";
    if (days > 1) {
      plural = "s";
    }
    return `${days} day${plural} ` + m.format('H:mm:ss');
  }
  if (d.hours()) {
    return m.format('H:mm:ss');
  }
  if (d.minutes()) {
    return m.format('m:ss');
  } else {
    return m.format('s') + " s";
  }
}

export function dateFormat(time: number) {
  return moment.unix(time).format('LLL');
}

export function durationFromNowFormat(time: number, now: number) {
  return moment.unix(time).from(moment.unix(now), false);
}

export function useCurrentTime() {
  const timeStore = useContext(TimeContext);
  return timeStore.now;
}

export function useCurrentTimeSetupTimers() {
  const timeStore = useContext(TimeContext);
  useEffect(() => {
    const timer = setInterval(
      () => timeStore.setTime(moment().unix()),
      1000
    );
    return () => clearInterval(timer);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
