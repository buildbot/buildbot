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

type ArrowExpanderProps = {
  isExpanded: boolean;
  setIsExpanded?: (expanded: boolean) => void;
}

const ArrowExpander = ({isExpanded, setIsExpanded}: ArrowExpanderProps) => {
  const callback = setIsExpanded === undefined ? undefined : () => setIsExpanded(!isExpanded);

  return (
    <i onClick={callback}
       className={"fa fa-chevron-circle-right rotate clickable" + (isExpanded ? " fa-rotate-90" : "")}>
    </i>
  );
}

export default ArrowExpander;
