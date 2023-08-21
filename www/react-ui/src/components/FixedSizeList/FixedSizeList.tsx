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
/*
  The code is based on the react-window project: https://github.com/bvaughn/react-window
  version  1.8.9 (6ff5694ac810617515acf74401ba68fe2951133b)

  The MIT License (MIT)

  Copyright (c) 2018 Brian Vaughn

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
*/

type InstanceProps = any;

import {
  createElement,
  PureComponent,
  ReactElement,
  Ref,
  SyntheticEvent
} from 'react';
import { cancelTimeout, requestTimeout } from './timer';
import { getScrollbarSize, getRTLOffsetType } from './domHelpers';

import type { TimeoutID } from './timer';

export type ScrollToAlign = 'auto' | 'smart' | 'center' | 'start' | 'end';

// TODO Deprecate directions "horizontal" and "vertical"
type Direction = 'ltr' | 'rtl' | 'horizontal' | 'vertical';
type Layout = 'horizontal' | 'vertical';

type RenderComponentProps<T> = {
  data: T,
  index: number,
  isScrolling?: boolean,
  style: Object,
};

type RenderComponent<T> = React.ComponentType<RenderComponentProps<T>>;

type ScrollDirection = 'forward' | 'backward';

export type ListOnItemsRenderedProps = {
  overscanStartIndex: number;
  overscanStopIndex: number;
  visibleStartIndex: number;
  visibleStopIndex: number;
};

export type ListOnScrollProps = {
  scrollDirection: ScrollDirection;
  scrollOffset: number;
  scrollUpdateWasRequested: boolean;
};

type onItemsRenderedCallback = (info: ListOnItemsRenderedProps) => void;
type onScrollCallback = (info: ListOnScrollProps) => void;

type ScrollEvent = SyntheticEvent<HTMLDivElement>;
type ItemStyleCache = {[index: number]: Object};

type OuterProps = {
  children: React.ReactNode,
  className: string | undefined,
  onScroll: (e: ScrollEvent) => void,
  style: {
    [key: string]: any,
  },
  ref?: Ref<any>;
};

type InnerProps = {
  children: React.ReactNode,
  style: {
    [key: string]: any,
  },
  ref?: Ref<any>;
};

export type FixedSizeListProps<T> = {
  children: RenderComponent<T>,
  className?: string,
  direction: Direction,
  height: number | string,
  initialScrollOffset?: number,
  innerRef?: Ref<HTMLElement>,
  innerElementType?: string | React.ComponentType<InnerProps>,
  itemCount: number,
  itemData: T,
  itemKey?: (index: number, data: T) => any,
  itemSize: number,
  layout: Layout,
  onItemsRendered?: onItemsRenderedCallback,
  onScroll?: onScrollCallback,
  outerRef?: Ref<HTMLElement>,
  outerElementType?: string | React.ComponentType<OuterProps>,
  overscanCount: number,
  style?: Object,
  useIsScrolling: boolean,
  width: number | string,
};

type State = {
  instance: any,
  isScrolling: boolean,
  scrollDirection: ScrollDirection,
  scrollOffset: number,
  scrollUpdateWasRequested: boolean,
};

const IS_SCROLLING_DEBOUNCE_INTERVAL = 150;

const defaultItemKey = (index: number, data: any) => index;

// In DEV mode, this Set helps us only log a warning once per component instance.
// This avoids spamming the console every time a render happens.
let devWarningsDirection: WeakSet<object>|null = null;
let devWarningsTagName: WeakSet<object>|null = null;
if (process.env.NODE_ENV !== 'production') {
  if (typeof window !== 'undefined' && typeof window.WeakSet !== 'undefined') {
    devWarningsDirection = new WeakSet();
    devWarningsTagName = new WeakSet();
  }
}


// NOTE: I considered further wrapping individual items with a pure ListItem component.
// This would avoid ever calling the render function for the same index more than once,
// But it would also add the overhead of a lot of components/fibers.
// I assume people already do this (render function returning a class component),
// So my doing it would just unnecessarily double the wrappers.

const validateSharedProps = (
  {
    children,
    direction,
    height,
    layout,
    width,
  }: FixedSizeListProps<any>,
  { instance }: State
): void => {
  if (process.env.NODE_ENV !== 'production') {
    // TODO Deprecate direction "horizontal"
    const isHorizontal = direction === 'horizontal' || layout === 'horizontal';

    switch (direction) {
      case 'horizontal':
      case 'vertical':
        if (devWarningsDirection && !devWarningsDirection.has(instance)) {
          devWarningsDirection.add(instance);
          console.warn(
            'The direction prop should be either "ltr" (default) or "rtl". ' +
            'Please use the layout prop to specify "vertical" (default) or "horizontal" orientation.'
          );
        }
        break;
      case 'ltr':
      case 'rtl':
        // Valid values
        break;
      default:
        throw Error(
          'An invalid "direction" prop has been specified. ' +
          'Value should be either "ltr" or "rtl". ' +
          `"${direction}" was specified.`
        );
    }

    switch (layout) {
      case 'horizontal':
      case 'vertical':
        // Valid values
        break;
      default:
        throw Error(
          'An invalid "layout" prop has been specified. ' +
          'Value should be either "horizontal" or "vertical". ' +
          `"${layout}" was specified.`
        );
    }

    if (children == null) {
      throw Error(
        'An invalid "children" prop has been specified. ' +
        'Value should be a React component. ' +
        `"${children === null ? 'null' : typeof children}" was specified.`
      );
    }

    if (isHorizontal && typeof width !== 'number') {
      throw Error(
        'An invalid "width" prop has been specified. ' +
        'Horizontal lists must specify a number for width. ' +
        `"${width === null ? 'null' : typeof width}" was specified.`
      );
    } else if (!isHorizontal && typeof height !== 'number') {
      throw Error(
        'An invalid "height" prop has been specified. ' +
        'Vertical lists must specify a number for height. ' +
        `"${height === null ? 'null' : typeof height}" was specified.`
      );
    }
  }
};

export class FixedSizeList<T> extends PureComponent<FixedSizeListProps<T>, State> {
  _instanceProps: any = {};
  _outerRef?: HTMLElement;
  _resetIsScrollingTimeoutId: TimeoutID | null = null;

  static defaultProps = {
    direction: 'ltr',
    itemData: undefined,
    layout: 'vertical',
    overscanCount: 2,
    useIsScrolling: false,
  };

  state: State = {
    instance: this,
    isScrolling: false,
    scrollDirection: 'forward',
    scrollOffset:
      typeof this.props.initialScrollOffset === 'number'
        ? this.props.initialScrollOffset
        : 0,
    scrollUpdateWasRequested: false,
  };

  // Always use explicit constructor for React components.
  // It produces less code after transpilation. (#26)
  // eslint-disable-next-line no-useless-constructor
  constructor(props: FixedSizeListProps<T>) {
    super(props);
  }

  getItemOffset({ itemSize }: FixedSizeListProps<any>, index: number): number {
    return index * itemSize;
  }

  getItemSize({ itemSize }: FixedSizeListProps<any>, index: number): number {
    return itemSize;
  }

  getEstimatedTotalSize({ itemCount, itemSize }: FixedSizeListProps<any>) {
    return itemSize * itemCount;
  }

  getOffsetForIndexAndAlignment({ direction, height, itemCount, itemSize, layout, width }: FixedSizeListProps<any>,
                                index: number,
                                align: ScrollToAlign,
                                scrollOffset: number,
                                instanceProps: InstanceProps,
                                scrollbarSize: number): number {
    // TODO Deprecate direction "horizontal"
    const isHorizontal = direction === 'horizontal' || layout === 'horizontal';
    const size = (isHorizontal ? width : height) as number;
    const lastItemOffset = Math.max(0, itemCount * itemSize - size);
    const maxOffset = Math.min(lastItemOffset, index * itemSize);
    const minOffset = Math.max(
      0,
      index * itemSize - size + itemSize +
      scrollbarSize
    );

    if (align === 'smart') {
      if (scrollOffset >= minOffset - size && scrollOffset <= maxOffset + size) {
        align = 'auto';
      } else {
        align = 'center';
      }
    }

    switch (align) {
      case 'start':
        return maxOffset;
      case 'end':
        return minOffset;
      case 'center': {
        // "Centered" offset is usually the average of the min and max.
        // But near the edges of the list, this doesn't hold true.
        const middleOffset = Math.round(
          minOffset + (maxOffset - minOffset) / 2
        );
        if (middleOffset < Math.ceil(size / 2)) {
          return 0; // near the beginning
        } else if (middleOffset > lastItemOffset + Math.floor(size / 2)) {
          return lastItemOffset; // near the end
        } else {
          return middleOffset;
        }
      }
      case 'auto':
      default:
        if (scrollOffset >= minOffset && scrollOffset <= maxOffset) {
          return scrollOffset;
        } else if (scrollOffset < minOffset) {
          return minOffset;
        } else {
          return maxOffset;
        }
    }
  }

  getStartIndexForOffset({ itemCount, itemSize }: FixedSizeListProps<any>, offset: number) {
    return Math.max(
      0,
      Math.min(itemCount - 1, Math.floor(offset / itemSize))
    );
  }

  getStopIndexForStartIndex({ direction, height, itemCount, itemSize, layout, width }: FixedSizeListProps<any>,
                            startIndex: number,
                            scrollOffset: number): number {
    // TODO Deprecate direction "horizontal"
    const isHorizontal = direction === 'horizontal' || layout === 'horizontal';
    const offset = startIndex * itemSize;
    const size = (isHorizontal ? width : height) as number;
    const numVisibleItems = Math.ceil((size + scrollOffset - offset) / itemSize);

    return Math.max(0, Math.min(itemCount - 1, startIndex + numVisibleItems - 1 // -1 is because stop index is inclusive
      ));
  }

  static getDerivedStateFromProps(
    nextProps: FixedSizeListProps<any>,
    prevState: State
  ): null {
    validateSharedProps(nextProps, prevState);
    return null;
  }

  scrollTo(scrollOffset: number): void {
    scrollOffset = Math.max(0, scrollOffset);

    this.setState(prevState => {
      if (prevState.scrollOffset === scrollOffset) {
        return null;
      }
      return {
        scrollDirection:
          prevState.scrollOffset < scrollOffset ? 'forward' : 'backward',
        scrollOffset: scrollOffset,
        scrollUpdateWasRequested: true,
      };
    }, () => this._resetIsScrollingDebounced());
  }

  scrollToItem(index: number, align: ScrollToAlign = 'auto'): void {
    const { itemCount, layout } = this.props;
    const { scrollOffset } = this.state;

    index = Math.max(0, Math.min(index, itemCount - 1));

    // The scrollbar size should be considered when scrolling an item into view, to ensure it's fully visible.
    // But we only need to account for its size when it's actually visible.
    // This is an edge case for lists; normally they only scroll in the dominant direction.
    let scrollbarSize = 0;
    if (this._outerRef) {
      const outerRef = this._outerRef;
      if (layout === 'vertical') {
        scrollbarSize =
          outerRef.scrollWidth > outerRef.clientWidth
            ? getScrollbarSize()
            : 0;
      } else {
        scrollbarSize =
          outerRef.scrollHeight > outerRef.clientHeight
            ? getScrollbarSize()
            : 0;
      }
    }

    this.scrollTo(
      this.getOffsetForIndexAndAlignment(
        this.props,
        index,
        align,
        scrollOffset,
        this._instanceProps,
        scrollbarSize
      )
    );
  }

  componentDidMount() {
    const { direction, initialScrollOffset, layout } = this.props;

    if (typeof initialScrollOffset === 'number' && this._outerRef != null) {
      const outerRef = this._outerRef;
      // TODO Deprecate direction "horizontal"
      if (direction === 'horizontal' || layout === 'horizontal') {
        outerRef.scrollLeft = initialScrollOffset;
      } else {
        outerRef.scrollTop = initialScrollOffset;
      }
    }

    this._callPropsCallbacks();
  }

  componentDidUpdate() {
    const { direction, layout } = this.props;
    const { scrollOffset, scrollUpdateWasRequested } = this.state;

    if (scrollUpdateWasRequested && this._outerRef != null) {
      const outerRef = this._outerRef;

      // TODO Deprecate direction "horizontal"
      if (direction === 'horizontal' || layout === 'horizontal') {
        if (direction === 'rtl') {
          // TRICKY According to the spec, scrollLeft should be negative for RTL aligned elements.
          // This is not the case for all browsers though (e.g. Chrome reports values as positive, measured relative to the left).
          // So we need to determine which browser behavior we're dealing with, and mimic it.
          switch (getRTLOffsetType()) {
            case 'negative':
              outerRef.scrollLeft = -scrollOffset;
              break;
            case 'positive-ascending':
              outerRef.scrollLeft = scrollOffset;
              break;
            default:
              const { clientWidth, scrollWidth } = outerRef;
              outerRef.scrollLeft = scrollWidth - clientWidth - scrollOffset;
              break;
          }
        } else {
          outerRef.scrollLeft = scrollOffset;
        }
      } else {
        outerRef.scrollTop = scrollOffset;
      }
    }

    this._callPropsCallbacks();
  }

  componentWillUnmount() {
    if (this._resetIsScrollingTimeoutId !== null) {
      cancelTimeout(this._resetIsScrollingTimeoutId);
    }
  }

  render() {
    const {
      children,
      className,
      direction,
      height,
      innerRef,
      innerElementType,
      itemCount,
      itemData,
      itemKey = defaultItemKey,
      layout,
      outerElementType,
      style,
      useIsScrolling,
      width,
    } = this.props;
    const { isScrolling } = this.state;

    // TODO Deprecate direction "horizontal"
    const isHorizontal =
      direction === 'horizontal' || layout === 'horizontal';

    const onScroll = isHorizontal
      ? (e: ScrollEvent) => this._onScrollHorizontal(e)
      : (e: ScrollEvent) => this._onScrollVertical(e);

    const [startIndex, stopIndex] = this._getRangeToRender();

    const items: ReactElement[] = [];
    if (itemCount > 0) {
      for (let index = startIndex; index <= stopIndex; index++) {
        const Children = children;
        items.push(
          <Children
            data={itemData}
            key={itemKey(index, itemData)}
            index={index}
            isScrolling={useIsScrolling ? isScrolling : undefined}
            style={this._getItemStyle(index)}
          />
        );
      }
    }

    // Read this value AFTER items have been created,
    // So their actual sizes (if variable) are taken into consideration.
    const estimatedTotalSize = this.getEstimatedTotalSize(
      this.props,
    );

    return createElement(
      outerElementType || "div",
      {
        className,
        onScroll,
        ref: (ref: HTMLElement) => this._outerRefSetter(ref),
        style: {
          position: 'relative',
          height,
          width,
          overflow: 'auto',
          WebkitOverflowScrolling: 'touch',
          willChange: 'transform',
          direction,
          ...style,
        },
        children: createElement(
          innerElementType || "div",
          {
            ref: innerRef,
            style: {
              height: isHorizontal ? '100%' : estimatedTotalSize,
              pointerEvents: isScrolling ? 'none' : undefined,
              width: isHorizontal ? estimatedTotalSize : '100%',
            },
            children: items
          }
        )
      },
    );
  }

  private lastOverscanStartIndex?: number = undefined;
  private lastOverscanStopIndex?: number = undefined;
  private lastVisibleStartIndex?: number = undefined;
  private lastVisibleStopIndex?: number = undefined;

  _callOnItemsRendered(overscanStartIndex: number,
                       overscanStopIndex: number,
                       visibleStartIndex: number,
                       visibleStopIndex: number) {
    if (this.lastOverscanStartIndex !== overscanStartIndex ||
      this.lastOverscanStopIndex !== overscanStopIndex ||
      this.lastVisibleStartIndex !== visibleStartIndex ||
      this.lastVisibleStopIndex !== visibleStopIndex) {

      this.lastOverscanStartIndex = overscanStartIndex;
      this.lastOverscanStopIndex = overscanStopIndex;
      this.lastVisibleStartIndex = visibleStartIndex;
      this.lastVisibleStopIndex = visibleStopIndex;

      this.props.onItemsRendered!({
        overscanStartIndex,
        overscanStopIndex,
        visibleStartIndex,
        visibleStopIndex,
      });
    }
  }

  private lastScrollDirection?: ScrollDirection = undefined;
  private lastScrollOffset?: number = undefined;
  private lastScrollUpdateWasRequested?: boolean = undefined;

  _callOnScroll(scrollDirection: ScrollDirection,
                scrollOffset: number,
                scrollUpdateWasRequested: boolean) {
    if (this.lastScrollDirection !== scrollDirection ||
      this.lastScrollOffset !== scrollOffset ||
      this.lastScrollUpdateWasRequested !== scrollUpdateWasRequested) {

      this.lastScrollDirection = scrollDirection;
      this.lastScrollOffset = scrollOffset;
      this.lastScrollUpdateWasRequested = scrollUpdateWasRequested;

      this.props.onScroll!({
        scrollDirection,
        scrollOffset,
        scrollUpdateWasRequested,
      });
    }
  }

  _callPropsCallbacks() {
    if (typeof this.props.onItemsRendered === 'function') {
      const { itemCount } = this.props;
      if (itemCount > 0) {
        const [
          overscanStartIndex,
          overscanStopIndex,
          visibleStartIndex,
          visibleStopIndex,
        ] = this._getRangeToRender();
        this._callOnItemsRendered(
          overscanStartIndex,
          overscanStopIndex,
          visibleStartIndex,
          visibleStopIndex
        );
      }
    }

    if (typeof this.props.onScroll === 'function') {
      const {
        scrollDirection,
        scrollOffset,
        scrollUpdateWasRequested,
      } = this.state;
      this._callOnScroll(
        scrollDirection,
        scrollOffset,
        scrollUpdateWasRequested
      );
    }
  }

  // Lazily create and cache item styles while scrolling,
  // So that pure component sCU will prevent re-renders.
  // We maintain this cache, and pass a style prop rather than index,
  // So that List can clear cached styles and force item re-render if necessary.
  _getItemStyle(index: number): object {
    const { direction, itemSize, layout } = this.props;

    const itemStyleCache = this._getItemStyleCache(
      itemSize,
      layout,
      direction
    );

    let style;
    if (itemStyleCache.hasOwnProperty(index)) {
      style = itemStyleCache[index];
    } else {
      const offset = this.getItemOffset(this.props, index);
      const size = this.props.itemSize;

      // TODO Deprecate direction "horizontal"
      const isHorizontal =
        direction === 'horizontal' || layout === 'horizontal';

      const isRtl = direction === 'rtl';
      const offsetHorizontal = isHorizontal ? offset : 0;
      itemStyleCache[index] = style = {
        position: 'absolute',
        left: isRtl ? undefined : offsetHorizontal,
        right: isRtl ? offsetHorizontal : undefined,
        top: !isHorizontal ? offset : 0,
        height: !isHorizontal ? size : '100%',
        width: isHorizontal ? size : '100%',
      };
    }

    return style;
  };

  private _itemStyleCache: ItemStyleCache = {}
  private _itemStyleCacheLastItemSize?: number = undefined;
  private _itemStyleCacheLastLayout?: Layout = undefined;
  private _itemStyleCacheLastDirection?: Direction = undefined;

  private _getItemStyleCache(itemSize: number, layout: Layout, direction: Direction): ItemStyleCache {
    if (this._itemStyleCacheLastItemSize !== itemSize ||
      this._itemStyleCacheLastLayout !== layout ||
      this._itemStyleCacheLastDirection !== direction) {

      this._itemStyleCacheLastItemSize = itemSize;
      this._itemStyleCacheLastLayout = layout;
      this._itemStyleCacheLastDirection = direction;
      this._itemStyleCache = {};
    }
    return this._itemStyleCache;
  }

  _getRangeToRender(): [number, number, number, number] {
    const { itemCount, overscanCount } = this.props;
    const { isScrolling, scrollDirection, scrollOffset } = this.state;

    if (itemCount === 0) {
      return [0, 0, 0, 0];
    }

    const startIndex = this.getStartIndexForOffset(
      this.props,
      scrollOffset,
    );
    const stopIndex = this.getStopIndexForStartIndex(
      this.props,
      startIndex,
      scrollOffset,
    );

    // Overscan by one item in each direction so that tab/focus works.
    // If there isn't at least one extra item, tab loops back around.
    const overscanBackward =
      !isScrolling || scrollDirection === 'backward'
        ? Math.max(1, overscanCount)
        : 1;
    const overscanForward =
      !isScrolling || scrollDirection === 'forward'
        ? Math.max(1, overscanCount)
        : 1;

    return [
      Math.max(0, startIndex - overscanBackward),
      Math.max(0, Math.min(itemCount - 1, stopIndex + overscanForward)),
      startIndex,
      stopIndex,
    ];
  }

  _onScrollHorizontal(event: ScrollEvent): void {
    const { clientWidth, scrollLeft, scrollWidth } = event.currentTarget;
    this.setState(prevState => {
      if (prevState.scrollOffset === scrollLeft) {
        // Scroll position may have been updated by cDM/cDU,
        // In which case we don't need to trigger another render,
        // And we don't want to update state.isScrolling.
        return null;
      }

      const { direction } = this.props;

      let scrollOffset = scrollLeft;
      if (direction === 'rtl') {
        // TRICKY According to the spec, scrollLeft should be negative for RTL aligned elements.
        // This is not the case for all browsers though (e.g. Chrome reports values as positive, measured relative to the left).
        // It's also easier for this component if we convert offsets to the same format as they would be in for ltr.
        // So the simplest solution is to determine which browser behavior we're dealing with, and convert based on it.
        switch (getRTLOffsetType()) {
          case 'negative':
            scrollOffset = -scrollLeft;
            break;
          case 'positive-descending':
            scrollOffset = scrollWidth - clientWidth - scrollLeft;
            break;
        }
      }

      // Prevent Safari's elastic scrolling from causing visual shaking when scrolling past bounds.
      scrollOffset = Math.max(
        0,
        Math.min(scrollOffset, scrollWidth - clientWidth)
      );

      return {
        isScrolling: true,
        scrollDirection:
          prevState.scrollOffset < scrollLeft ? 'forward' : 'backward',
        scrollOffset,
        scrollUpdateWasRequested: false,
      };
    }, () => this._resetIsScrollingDebounced());
  };

  _onScrollVertical(event: ScrollEvent): void {
    const { clientHeight, scrollHeight, scrollTop } = event.currentTarget;
    this.setState(prevState => {
      if (prevState.scrollOffset === scrollTop) {
        // Scroll position may have been updated by cDM/cDU,
        // In which case we don't need to trigger another render,
        // And we don't want to update state.isScrolling.
        return null;
      }

      // Prevent Safari's elastic scrolling from causing visual shaking when scrolling past bounds.
      const scrollOffset = Math.max(
        0,
        Math.min(scrollTop, scrollHeight - clientHeight)
      );

      return {
        isScrolling: true,
        scrollDirection:
          prevState.scrollOffset < scrollOffset ? 'forward' : 'backward',
        scrollOffset,
        scrollUpdateWasRequested: false,
      };
    }, () => this._resetIsScrollingDebounced());
  }

  _outerRefSetter(ref: HTMLElement): void {
    const { outerRef } = this.props;

    this._outerRef = ref;

    if (typeof outerRef === 'function') {
      outerRef(ref);
    } else if (
      outerRef != null &&
      typeof outerRef === 'object' &&
      outerRef.hasOwnProperty('current')
    ) {
      // @ts-ignore
      outerRef.current = ref;
    }
  }

  _resetIsScrollingDebounced() {
    if (this._resetIsScrollingTimeoutId !== null) {
      cancelTimeout(this._resetIsScrollingTimeoutId);
    }

    this._resetIsScrollingTimeoutId = requestTimeout(
      () => this._resetIsScrolling(),
      IS_SCROLLING_DEBOUNCE_INTERVAL
    );
  }

  _resetIsScrolling() {
    this._resetIsScrollingTimeoutId = null;

    this.setState({ isScrolling: false }, () => {
      // Clear style cache after state update has been committed.
      // This way we don't break pure sCU for items that don't use isScrolling param.
      this._itemStyleCache = {};
    });
  }
};
