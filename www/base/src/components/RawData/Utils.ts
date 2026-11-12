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

import moment from 'moment';

export const displayBuildRequestEntry = (key: string, value: any): string => {
  if (key === 'claimed_at' || key === 'complete_at' || key === 'submitted_at') {
    try {
      return `${value} (${moment(Number.parseInt(value.toString()) * 1000).format()})`;
    } catch (_error) {
      return value.toString();
    }
  }
  return value.toString();
};

export const displayBuildsetEntry = (key: string, value: any): string => {
  if (key === 'complete_at' || key === 'created_at' || key === 'submitted_at') {
    // created_at is for dictionaries in sourcestamps list
    try {
      return `${value} (${moment(Number.parseInt(value.toString()) * 1000).format()})`;
    } catch (_error) {
      return value.toString();
    }
  }
  return value.toString();
};
