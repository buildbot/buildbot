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

// Tracks child state that can be set independently, but whenever parent state changes, the child
// state changes too.
export function useStateWithParentTracking<T>(
    parentValue: T, defaultValue: T): [T, Dispatch<SetStateAction<T>>] {
  const [lastParentValue, setLastParentValue] = useState(parentValue);
  const [explicitValue, setExplicitValue] = useState(defaultValue);

  if (parentValue !== lastParentValue) {
    setLastParentValue(parentValue);
    setExplicitValue(parentValue);
    return [parentValue, setExplicitValue];
  }

  return [explicitValue, setExplicitValue];
}
