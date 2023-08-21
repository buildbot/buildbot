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

import {FixedSizeListProps} from "buildbot-ui";
import {FixedSizeList} from 'buildbot-ui';

export type CustomFixedSizeListProps<T = any> = FixedSizeListProps<T> & {
  getRangeToRenderOverride: (overscanStartIndex: number,
                             overscanStopIndex: number,
                             visibleStartIndex: number,
                             visibleStopIndex: number) => [number, number, number, number]
}

// react-virtualized provided a way to adjust range to be rendered. react-window removed this
// capability. As a workaround this functionality is patched back in.
export class CustomFixedSizeList<T = any> extends FixedSizeList<T> {
  // @ts-ignore
  readonly props: Readonly<CustomFixedSizeListProps<T>>;

  // eslint-disable-next-line @typescript-eslint/no-useless-constructor
  constructor(props: CustomFixedSizeListProps<T>) {
    super(props);
  }

  _getRangeToRender() {
    const [
      overscanStartIndex,
      overscanStopIndex,
      visibleStartIndex,
      visibleStopIndex,
    ] = ((FixedSizeList<T>) as any).prototype._getRangeToRender.call(this);
    return (this.props as any).getRangeToRenderOverride(overscanStartIndex, overscanStopIndex,
      visibleStartIndex, visibleStopIndex);
  }
}
