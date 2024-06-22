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
  SyntheticEvent,
  WheelEvent
} from 'react';
import { cancelTimeout, requestTimeout } from './timer';
import { getScrollbarSize } from './domHelpers';

import type { TimeoutID } from './timer';

export type ScrollToAlign = 'auto' | 'smart' | 'center' | 'start' | 'end';

type Direction = 'ltr' | 'rtl';

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

type GetRangeToRenderOverrideCallback = (overscanStartIndex: number,
                                         overscanStopIndex: number,
                                         visibleStartIndex: number,
                                         visibleStopIndex: number) => [number, number, number, number];

type ScrollEvent = SyntheticEvent<HTMLDivElement>;
type ItemStyleCache = {[index: number]: Object};

export type FixedSizeListOuterProps = {
  children: React.ReactNode,
  className: string | undefined,
  onScroll: (e: ScrollEvent) => void,
  onWheel: (e: WheelEvent) => void,
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
  height: number,
  initialScrollOffset?: number,
  innerRef?: Ref<HTMLElement>,
  innerElementType?: string | React.ComponentType<InnerProps>,
  itemCount: number,
  itemData: T,
  itemKey?: (index: number, data: T) => any,
  itemSize: number,
  largeListSizeLimit?: number;
  largeListScrollbarInaccuracyNotScrolling?: number;
  largeListScrollbarInaccuracyScrolling?: number;
  largeListEndsBufferRelSize?: number;
  onItemsRendered?: onItemsRenderedCallback,
  onScroll?: onScrollCallback,
  onCacheClear?: () => void;
  getRangeToRenderOverride?: GetRangeToRenderOverrideCallback,
  outerRef?: Ref<HTMLElement>,
  outerElementType?: string | React.ForwardRefExoticComponent<React.PropsWithoutRef<FixedSizeListOuterProps>>,
  overscanCount: number,
  style?: Object,
  useIsScrolling: boolean,
  width: number | string,
};

type State = {
  isScrolling: boolean,
  isScrollingByMouse: boolean,
  scrollDirection: ScrollDirection,
  scrollOffset: number,
  scrollUpdateWasRequested: boolean,
  largeListModeEnabled: boolean;
  largeListLastTotalHeight: number;
  largeListLastSubWindowOffset: number;
};

const IS_SCROLLING_DEBOUNCE_INTERVAL = 150;
const WHEEL_TO_SCROLL_EVENT_MS = 1000;

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

const validateSharedProps = (
  {
    children,
    direction,
    height,
  }: FixedSizeListProps<any>
): void => {
  if (process.env.NODE_ENV !== 'production') {
    switch (direction) {
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

    if (children == null) {
      throw Error(
        'An invalid "children" prop has been specified. ' +
        'Value should be a React component. ' +
        `"${children === null ? 'null' : typeof children}" was specified.`
      );
    }
  }
};

export class FixedSizeList<T> extends PureComponent<FixedSizeListProps<T>, State> {
  _instanceProps: any = {};
  _outerRef?: HTMLElement;
  _resetIsScrollingTimeoutId: TimeoutID | null = null;
  _lastWheelEvent: number = 0;

  static defaultProps = {
    direction: 'ltr',
    itemData: undefined,
    overscanCount: 2,
    useIsScrolling: false,
    largeListSizeLimit: 1000000,
    largeListScrollbarInaccuracyNotScrolling: 0.005,
    largeListScrollbarInaccuracyScrolling: 0.01,
    largeListEndsBufferRelSize: 0.01,
  };

  state: State = {
    isScrolling: false,
    isScrollingByMouse: false,
    scrollDirection: 'forward',
    scrollOffset:
      typeof this.props.initialScrollOffset === 'number'
        ? this.props.initialScrollOffset
        : 0,
    scrollUpdateWasRequested: false,
    largeListModeEnabled: false,
    largeListLastTotalHeight: -1,
    largeListLastSubWindowOffset: 0,
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

  getEstimatedTotalSize({itemCount, itemSize, largeListSizeLimit}: FixedSizeListProps<any>,
                        {largeListModeEnabled}: State) {
    return largeListModeEnabled ? largeListSizeLimit : itemSize * itemCount;
  }

  getGlobalScrollOffset() {
    const {
      scrollOffset,
      largeListLastSubWindowOffset
    } = this.state;

    return scrollOffset + largeListLastSubWindowOffset;
  }

  getOffsetForIndexAndAlignment({ direction, height, itemCount, itemSize, width }: FixedSizeListProps<any>,
                                index: number,
                                align: ScrollToAlign,
                                globalScrollOffset: number,
                                instanceProps: InstanceProps,
                                scrollbarSize: number): number {
    const size = height;
    const lastItemOffset = Math.max(0, itemCount * itemSize - size);
    const maxOffset = Math.min(lastItemOffset, index * itemSize);
    const minOffset = Math.max(
      0,
      index * itemSize - size + itemSize +
      scrollbarSize
    );

    if (align === 'smart') {
      if (globalScrollOffset >= minOffset - size && globalScrollOffset <= maxOffset + size) {
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
        if (globalScrollOffset >= minOffset && globalScrollOffset <= maxOffset) {
          return globalScrollOffset;
        } else if (globalScrollOffset < minOffset) {
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

  getStopIndexForStartIndex({ direction, height, itemCount, itemSize, width }: FixedSizeListProps<any>,
                            startIndex: number,
                            globalScrollOffset: number): number {
    const offset = startIndex * itemSize;
    const size = height;
    const numVisibleItems = Math.ceil((size + globalScrollOffset - offset) / itemSize);

    return Math.max(0, Math.min(itemCount, startIndex + numVisibleItems));
  }

  static getDerivedStateFromProps(
    nextProps: FixedSizeListProps<any>,
    prevState: State
  ): State|null {
    validateSharedProps(nextProps);

    const totalHeight = nextProps.itemCount * nextProps.itemSize;
    const useLargeListMode = (totalHeight > nextProps.largeListSizeLimit!);
    const largeListModeEnabled = prevState.largeListModeEnabled;

    if (useLargeListMode === largeListModeEnabled) {
      return null;
    }

    if (useLargeListMode) {
      const [scrollOffset, subWindowOffset] = FixedSizeList._calculateSubWindowOffset(
        nextProps,
        prevState.scrollOffset
      );

      return {
        ...prevState,
        largeListModeEnabled: true,
        scrollOffset,
        largeListLastSubWindowOffset: subWindowOffset,
      }
    } else {
      return {
        ...prevState,
        largeListModeEnabled: false,
        scrollOffset: prevState.scrollOffset + prevState.largeListLastSubWindowOffset,
        largeListLastSubWindowOffset: 0,
      }
    }
  }

  scrollTo(globalScrollOffset: number): void {
    globalScrollOffset = Math.max(0, globalScrollOffset);

    this.setState(prevState => {
      if (!prevState.largeListModeEnabled) {
        const scrollOffset = globalScrollOffset;
        if (prevState.scrollOffset === scrollOffset) {
          return null;
        }

        return {
          ...prevState,
          isScrolling: false,
          isScrollingByMouse: false,
          scrollDirection:
            prevState.scrollOffset < scrollOffset ? 'forward' : 'backward',
          scrollOffset: scrollOffset,
          scrollUpdateWasRequested: true,
        };
      }

      const [scrollOffset, subWindowOffset] = FixedSizeList._calculateSubWindowOffset(
        this.props,
        globalScrollOffset
      );

      if (prevState.scrollOffset === scrollOffset &&
        prevState.largeListLastSubWindowOffset === subWindowOffset) {
        return null;
      }

      return {
        ...prevState,
        isScrolling: false,
        isScrollingByMouse: false,
        scrollDirection:
          prevState.scrollOffset < scrollOffset ? 'forward' : 'backward',
        scrollOffset: scrollOffset,
        scrollUpdateWasRequested: true,
        largeListLastSubWindowOffset: subWindowOffset,
      };
    }, () => this._resetIsScrollingDebounced());
  }

  scrollToItem(index: number, align: ScrollToAlign = 'auto'): void {
    const { itemCount } = this.props;
    const globalScrollOffset = this.getGlobalScrollOffset();

    index = Math.max(0, Math.min(index, itemCount - 1));

    // The scrollbar size should be considered when scrolling an item into view, to ensure it's fully visible.
    // But we only need to account for its size when it's actually visible.
    // This is an edge case for lists; normally they only scroll in the dominant direction.
    let scrollbarSize = 0;
    if (this._outerRef) {
      const outerRef = this._outerRef;
      scrollbarSize =
        outerRef.scrollWidth > outerRef.clientWidth
          ? getScrollbarSize()
          : 0;
    }

    this.scrollTo(
      this.getOffsetForIndexAndAlignment(
        this.props,
        index,
        align,
        globalScrollOffset,
        this._instanceProps,
        scrollbarSize
      )
    );
  }

  componentDidMount() {
    const { initialScrollOffset } = this.props;

    if (typeof initialScrollOffset === 'number' && this._outerRef != null) {
      const outerRef = this._outerRef;
      outerRef.scrollTop = initialScrollOffset;
    }

    this._callPropsCallbacks();
  }

  _onCacheClearLargeListLastSubWindowOffset: number = -1;

  componentDidUpdate() {
    const { scrollOffset, scrollUpdateWasRequested } = this.state;

    if (scrollUpdateWasRequested && this._outerRef != null) {
      this._outerRef.scrollTop = scrollOffset;
    }

    if (this.state.largeListLastSubWindowOffset !== this._onCacheClearLargeListLastSubWindowOffset) {
      this._onCacheClearLargeListLastSubWindowOffset = this.state.largeListLastSubWindowOffset;
      if (this.props.onCacheClear !== undefined) {
        this.props.onCacheClear();
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
      outerElementType,
      style,
      useIsScrolling,
      width,
    } = this.props;
    const { isScrolling } = this.state;

    const [startIndex, stopIndex] = this._getRangeToRender();

    const items: ReactElement[] = [];
    if (itemCount > 0) {
      for (let index = startIndex; index < stopIndex; index++) {
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
    const estimatedTotalSize = this.getEstimatedTotalSize(this.props, this.state);

    return createElement(
      outerElementType || "div",
      {
        className,
        onScroll: (e) => this._onScrollVertical(e),
        onWheel: (e) => this._onWheel(),
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
              height: estimatedTotalSize,
              pointerEvents: isScrolling ? 'none' : undefined,
              width: '100%',
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
  private lastScrollLargeListLastSubWindowOffset?: number = undefined;
  private lastScrollUpdateWasRequested?: boolean = undefined;

  _callOnScroll() {
    const {
      scrollDirection,
      scrollOffset,
      scrollUpdateWasRequested,
      largeListLastSubWindowOffset,
    } = this.state;

    if (this.lastScrollDirection !== scrollDirection ||
      this.lastScrollOffset !== scrollOffset ||
      this.lastScrollUpdateWasRequested !== scrollUpdateWasRequested ||
      this.lastScrollLargeListLastSubWindowOffset !== largeListLastSubWindowOffset) {

      this.lastScrollDirection = scrollDirection;
      this.lastScrollOffset = scrollOffset;
      this.lastScrollUpdateWasRequested = scrollUpdateWasRequested;
      this.lastScrollLargeListLastSubWindowOffset = largeListLastSubWindowOffset;

      this.props.onScroll!({
        scrollDirection,
        scrollOffset: this.getGlobalScrollOffset(),
        scrollUpdateWasRequested
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
      this._callOnScroll();
    }
  }

  // Lazily create and cache item styles while scrolling,
  // So that pure component sCU will prevent re-renders.
  // We maintain this cache, and pass a style prop rather than index,
  // So that List can clear cached styles and force item re-render if necessary.
  _getItemStyle(index: number): object {
    const { direction, itemSize } = this.props;

    const itemStyleCache = this._getItemStyleCache(
      itemSize,
      direction,
      this.state.largeListLastSubWindowOffset,
    );

    let style;
    if (itemStyleCache.hasOwnProperty(index)) {
      style = itemStyleCache[index];
    } else {
      const offset = this.getItemOffset(this.props, index) - this.state.largeListLastSubWindowOffset;
        const size = this.props.itemSize;

      const isRtl = direction === 'rtl';
      itemStyleCache[index] = style = {
        position: 'absolute',
        left: isRtl ? undefined : 0,
        right: isRtl ? 0 : undefined,
        top: offset,
        height: size,
        width: '100%',
      };
    }

    return style;
  };

  private _itemStyleCache: ItemStyleCache = {}
  private _itemStyleCacheShouldClear: boolean = false;
  private _itemStyleCacheLastItemSize?: number = undefined;
  private _itemStyleCacheLastDirection?: Direction = undefined;
  private _itemStyleCacheLargeListSubWindowOffset?: number = undefined;

  private _getItemStyleCache(itemSize: number, direction: Direction,
                             largeListSubWindowOffset: number): ItemStyleCache {
    if (this._itemStyleCacheShouldClear ||
      this._itemStyleCacheLastItemSize !== itemSize ||
      this._itemStyleCacheLastDirection !== direction ||
      this._itemStyleCacheLargeListSubWindowOffset !== largeListSubWindowOffset) {

      this._itemStyleCacheShouldClear = false;
      this._itemStyleCacheLastItemSize = itemSize;
      this._itemStyleCacheLastDirection = direction;
      this._itemStyleCacheLargeListSubWindowOffset = largeListSubWindowOffset;

      this._itemStyleCache = {};
    }
    return this._itemStyleCache;
  }

  _getRangeToRenderImpl(): [number, number, number, number] {
    const { itemCount, overscanCount } = this.props;
    const { isScrolling, scrollDirection } = this.state;

    if (itemCount === 0) {
      return [0, 0, 0, 0];
    }

    const globalScrollOffset = this.getGlobalScrollOffset();
    const startIndex = this.getStartIndexForOffset(
      this.props,
      globalScrollOffset,
    );
    const stopIndex = this.getStopIndexForStartIndex(
      this.props,
      startIndex,
      globalScrollOffset,
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
      Math.max(0, Math.min(itemCount, stopIndex + overscanForward)),
      startIndex,
      stopIndex,
    ];
  }

  _getRangeToRender(): [number, number, number, number] {
    const [
      overscanStartIndex,
      overscanStopIndex,
      visibleStartIndex,
      visibleStopIndex,
    ] = this._getRangeToRenderImpl();

    if (this.props.getRangeToRenderOverride !== undefined) {
      return this.props.getRangeToRenderOverride(
        overscanStartIndex,
        overscanStopIndex,
        visibleStartIndex,
        visibleStopIndex);
    }

    return [
      overscanStartIndex,
      overscanStopIndex,
      visibleStartIndex,
      visibleStopIndex,
    ];
  }

  _onScrollVertical(event: ScrollEvent): void {
    const { clientHeight, scrollHeight, scrollTop } = event.currentTarget;
    const thisScrollByMouse = (Date.now() - this._lastWheelEvent) < WHEEL_TO_SCROLL_EVENT_MS;
    this.setState(prevState => {
      if (prevState.scrollOffset === scrollTop) {
        // Scroll position may have been updated by cDM/cDU,
        // In which case we don't need to trigger another render,
        // And we don't want to update state.isScrolling.
        return null;
      }

      const isScrollingByMouse = prevState.isScrolling
        ? prevState.isScrollingByMouse
        : thisScrollByMouse;

      // Prevent Safari's elastic scrolling from causing visual shaking when scrolling past bounds.
      const scrollOffsetUnadjusted = Math.max(
        0,
        Math.min(scrollTop, scrollHeight - clientHeight)
      );

      const [changed, scrollOffset, subWindowOffset] =
        this._maybeAdjustSubWindowOffset(
          prevState.largeListModeEnabled,
          scrollOffsetUnadjusted,
          prevState.largeListLastSubWindowOffset,
          true,
          isScrollingByMouse);

      return {
        isScrolling: true,
        isScrollingByMouse,
        scrollDirection:
          prevState.scrollOffset < scrollOffset ? 'forward' : 'backward',
        scrollOffset,
        scrollUpdateWasRequested: changed,
        largeListLastTotalHeight: prevState.largeListLastTotalHeight,
        largeListLastSubWindowOffset: subWindowOffset,
      };
    }, () => this._resetIsScrollingDebounced());
  }

  _onWheel(): void {
    this._lastWheelEvent = Date.now();
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

    this.setState(prevState => {
      const [changed, scrollOffset, subWindowOffset] =
        this._maybeAdjustSubWindowOffset(
          prevState.largeListModeEnabled,
          prevState.scrollOffset,
          prevState.largeListLastSubWindowOffset,
          false,
          false);

      // Item style cache is used only during scrolling. Clear it so that items that don't use
      // isScrolling param are updated
      this._itemStyleCacheShouldClear = true;

      if (prevState.isScrollingByMouse) {
        // Sometimes scrolling resets and in such case any subsequest scroll events should
        // continue using previous scroll type.
        this._lastWheelEvent = Date.now();
      }

      return {
        ...prevState,
        isScrolling: false,
        isScrollingByMouse: false,
        scrollOffset,
        scrollUpdateWasRequested: changed,
        largeListLastSubWindowOffset: subWindowOffset,
      };
    });
  }

  _maybeAdjustSubWindowOffset(largeListModeEnabled: boolean,
                              scrollOffset: number,
                              lastSubWindowOffset: number,
                              isScrolling: boolean,
                              isScrollingByMouse: boolean): [boolean, number, number] {
    if (!largeListModeEnabled) {
      return [false, scrollOffset, lastSubWindowOffset];
    }

    const totalHeight = this.props.itemCount * this.props.itemSize;
    const viewportHeight = this.props.height;
    const forcedHeight = this.props.largeListSizeLimit!;
    const endsBufferRelSize = this.props.largeListEndsBufferRelSize!
      * (forcedHeight - viewportHeight) / (totalHeight - viewportHeight);

    const currentScrollbarRelPos = scrollOffset / (forcedHeight - viewportHeight);

    if (isScrolling && !isScrollingByMouse) {
      // When scrolling is done by mouse the scrollbar position needs to be updated according
      // to the contents on the screen.
      // When scrolling is done by scrollbar the contents on the screen need to be updated
      // according to the scrollbar position.
      const rawNewSubWindowOffset = Math.floor(currentScrollbarRelPos * (totalHeight - viewportHeight))
        - scrollOffset;
      const newSubWindowOffset = Math.max(0, Math.min(rawNewSubWindowOffset, totalHeight - forcedHeight));

      return [true, scrollOffset, newSubWindowOffset];
    }

    const targetRelPos = (lastSubWindowOffset + scrollOffset) / (totalHeight - viewportHeight);

    if (targetRelPos < endsBufferRelSize || currentScrollbarRelPos < endsBufferRelSize) {
      return [lastSubWindowOffset !== 0, scrollOffset + lastSubWindowOffset, 0];
    }

    if (targetRelPos > (1 - endsBufferRelSize) || currentScrollbarRelPos > (1 - endsBufferRelSize)) {
      const newSubWindowOffset = totalHeight - forcedHeight;
      return [lastSubWindowOffset !== newSubWindowOffset, scrollOffset + lastSubWindowOffset - newSubWindowOffset, newSubWindowOffset];
    }

    const relPosDiffLimit = isScrolling
      ? this.props.largeListScrollbarInaccuracyScrolling!
      : this.props.largeListScrollbarInaccuracyNotScrolling!

    if (Math.abs(targetRelPos - currentScrollbarRelPos) <= relPosDiffLimit) {
      return [false, scrollOffset, lastSubWindowOffset];
    }

    const newScrollOffset = Math.floor(targetRelPos * (forcedHeight - viewportHeight));
    const newSubWindowOffset = lastSubWindowOffset + scrollOffset - newScrollOffset;
    // Note that subWindowOffset + scrollOffset does not change, thus the new values match the
    // current targetRelPos exactly.

    return [true, newScrollOffset, newSubWindowOffset];
  }

  static _calculateSubWindowOffset(props: FixedSizeListProps<any>,
                                   globalScrollOffset: number): [number, number] {
    const totalHeight = props.itemCount * props.itemSize;
    const viewportHeight = props.height;
    const forcedHeight = props.largeListSizeLimit!;
    const endsBufferRelSize = props.largeListEndsBufferRelSize!
      * (forcedHeight - viewportHeight) / (totalHeight - viewportHeight);

    const targetRelPos = globalScrollOffset / (totalHeight - viewportHeight);

    if (targetRelPos < endsBufferRelSize) {
      return [globalScrollOffset, 0];
    }
    if (targetRelPos > (1 - endsBufferRelSize)) {
      const newSubWindowOffset = totalHeight - forcedHeight;
      return [globalScrollOffset - newSubWindowOffset, newSubWindowOffset];
    }

    const newScrollOffset = Math.floor(targetRelPos * (forcedHeight - viewportHeight));
    const newSubWindowOffset = globalScrollOffset - newScrollOffset;

    return [newScrollOffset, newSubWindowOffset];
  }
};
