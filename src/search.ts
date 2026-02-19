interface SearchAutocompleteState {
  isExpanded: boolean; // does the user want the menu to be open?
  itemCount: number;
  selectedIndex: number;
  items: () => HTMLElement[]; // list of items, as DOM elements
  menuVisible: () => boolean; // wants open, AND there is content to display
  onAfterSwap: (event: Event) => void;
  moveSelection: (direction: number) => void;
  submit: (index: number) => void;
  selectAndSubmit: (index: number) => void;
  closeMenu: () => void;
}

import Alpine from "alpinejs";
import "./search.css";

const createSearchAutocompleteState = (): SearchAutocompleteState => ({
  isExpanded: false,
  itemCount: 0,
  selectedIndex: -1,
  items() {
    /** Grabs the actual DOM elements as an array. */
    if (!this.$refs?.menu) {
      return [];
    }
    return Array.from(
      this.$refs.menu.querySelectorAll(".search-autocomplete-item"),
    );
  },
  menuVisible() {
    return this.isExpanded && this.itemCount > 0;
  },
  onAfterSwap(event: Event) {
    /**
     * Respond to HTMX content loads by resetting the selected index.
     *
     * Since we set the Alpine state on the whole search container, there are
     * multiple different HTMX requests flying around (one for getting search
     * results, one for getting autocomplete results). We have to filter to only
     * the autocomplete requests.
     */
    const target = event.target as HTMLElement | null;
    if (target?.id !== "search-autocomplete") {
      return;
    }
    const items = this.items();
    this.itemCount = items.length;
    this.selectedIndex = items.length > 0 ? 0 : -1;
  },
  moveSelection(direction: number) {
    /** Keyboard moves us up/down one selection - we want to wrap around at the ends.
     */
    if (this.itemCount === 0) {
      return;
    }
    this.isExpanded = true;
    if (this.selectedIndex < 0) {
      this.selectedIndex = 0;
    } else {
      this.selectedIndex += direction;
    }
    this.selectedIndex = (this.selectedIndex + this.itemCount) % this.itemCount;
  },
  submit(index: number) {
    /** Actually submit search.
     *
     * If we have a selected option, then update the input to that value before
     * submitting. Otherwise, just submit the dang form as is and reset UI state.
     */
    let query: string | undefined;
    if (this.menuVisible() && this.itemCount > 0) {
      const clampedIndex = Math.min(Math.max(index, 0), this.itemCount - 1);
      const items = this.items();
      query = items[clampedIndex]?.dataset.query;
    }
    if (query) {
      this.$refs.input.value = query;
    }
    this.closeMenu();
    this.$refs.form.requestSubmit();
  },
  selectAndSubmit(index: number) {
    /** Mouse click handler - select item, *then* submit the form.
     *
     * In most cases, the item should already have been selected via mouse
     * hover, but we keep the select in here in case of weird timings or
     * :shudder: touch events.
     */
    this.selectedIndex = index;
    this.submit(this.selectedIndex);
  },
  closeMenu() {
    /** Unexpand the menu, resets the selected index. */
    this.isExpanded = false;
    this.selectedIndex = -1;
  },
});

Alpine.data("searchAutocompleteState", createSearchAutocompleteState);

document.addEventListener("DOMContentLoaded", () => {
  Alpine.start();
});
