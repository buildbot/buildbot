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

import BaseClass from "./classes/BaseClass";
import DataCollection from "./DataCollection";
import {BasicDataMultiCollection} from "./BasicDataMultiCollection";

export default class DataMultiCollection<ParentDataType extends BaseClass,
    DataType extends BaseClass> extends BasicDataMultiCollection<ParentDataType, DataCollection<DataType>> {

  getRelated<ChildDataType extends BaseClass>(
    callback: (child: DataType) => DataCollection<ChildDataType>) {
    return new DataMultiCollection<DataType, ChildDataType>(this.accessor, null, this.byParentId,
      null, callback);
  }

  // Acquires nth element across all collections tracked by this multi collection. The iteration
  // order is in ascending order of parent IDs.
  getNthOrNull(index: number): DataType | null {
    for (const parentId of this.sortedParentIds) {
      const parent = this.byParentId.get(parentId);
      if (parent === undefined) {
        continue;
      }
      if (index < parent.array.length) {
        return parent.array[index];
      }
      index -= parent.array.length;
    }
    return null;
  }

  getAll(): DataType[] {
    const all: DataType[] = [];
    for (const parentId of this.sortedParentIds) {
      const parent = this.byParentId.get(parentId);
      if (parent === undefined) {
        continue;
      }
      all.push(...parent.array);
    }
    return all;
  }

  getNthOfParentOrNull(parentId: string, index: number): DataType | null {
    const collection = this.byParentId.get(parentId);
    if (collection === undefined) {
      return null;
    }
    if (index >= collection.array.length) {
      return null;
    }
    return collection.array[index];
  }

  getParentCollectionOrEmpty(parentId: string): DataCollection<DataType> {
    const collection = this.byParentId.get(parentId);
    if (collection === undefined) {
      return new DataCollection<DataType>();
    }
    return collection;
  }
}
