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

import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

export function useScrollToAnchor(dependencies: (string|number)[]) {
  const location = useLocation();
  const highlightedElement = useRef<HTMLElement|null>(null);

  const clearCurrentHighlightedElement = () => {
    if (highlightedElement.current !== null) {
      highlightedElement.current.className =
        highlightedElement.current.className.replaceAll(" bb-anchor-target", "");
      highlightedElement.current = null;
    }
  }

  useEffect(() => {
    var anchorName = '';
    if (location.hash) {
      anchorName = location.hash.slice(1);
    }

    if (anchorName === "") {
      clearCurrentHighlightedElement();
      return;
    }

    var el = document.getElementById(anchorName);
    if (el === null) {
      clearCurrentHighlightedElement();
      return;
    }

    if (el === highlightedElement.current) {
      return;
    }

    clearCurrentHighlightedElement();

    highlightedElement.current = el;
    el.className += " bb-anchor-target";

    setTimeout(() => {
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }, [location, dependencies.join("-")]);
}