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

import {Dispatch, SetStateAction, useState} from "react";

export function useStateWithDefaultIfNotSet<T>(
    defaultCallback: () => T): [T, Dispatch<SetStateAction<T|null>>] {
  const [explicitValue, setValue] = useState<T | null>(null);
  const value: T = explicitValue !== null ? explicitValue : defaultCallback();
  return [value, setValue];
}

// Just like useStateWithDefaultIfNotSet, however the current state is changed whenever a given
// "parent" state is changed. The current state can otherwise be changed independently
export function useStateWithParentTrackingWithDefaultIfNotSet<T>(
    parentValue: T, defaultCallback: () => T): [T, (v: T) => void] {
  const [lastParentValue, setLastParentValue] = useState(parentValue);
  const [explicitValue, setExplicitValue] = useState<T | null>(null);

  if (parentValue !== lastParentValue) {
    setLastParentValue(parentValue);
    setExplicitValue(parentValue);
    return [parentValue, t => setExplicitValue(t)];
  }

  const value: T = explicitValue !== null ? explicitValue : defaultCallback();
  return [value, t => setExplicitValue(t)];
}
