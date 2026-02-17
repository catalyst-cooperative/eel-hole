import "./search.css";
import Alpine from "alpinejs";

type AutocompleteOption =
  | { kind: "search"; label: string; query: string }
  | { kind: "name"; name: string; query: string };

/** JSON shape returned by the `/search/autocomplete` endpoint. */
interface AutocompletePayload {
  suggestions?: string[];
}

interface AutocompleteState {
  isOpen: boolean;
  selectedIndex: number;
  suggestions: string[];
  query: string;
}

Alpine.data("searchAutocomplete", () => ({
  state: Alpine.reactive<AutocompleteState>({
    isOpen: false,
    selectedIndex: 0,
    suggestions: [],
    query: "",
  }),
  abortController: null,
  debounceTimer: null as number | null,

  init() {
    /**
     * Initialize the autocomplete:
     *
     * - define a debounced version of the autocomplete request
     * - update CSS classes on open-state change so we know how to style when autocomplete is open
     * - update CSS classes on selected-item change
     * - update autocomplete suggestions on query change
     * - close the autocomplete when the user clicks outside of it
     * - make sure the URL and search query match up
     */
    this.$watch("state.query", (query: string) => {
      if (this.debounceTimer !== null) {
        window.clearTimeout(this.debounceTimer);
        this.debounceTimer = null;
      }

      const trimmedQuery = query.trim();
      if (!trimmedQuery) {
        this.menu().innerHTML = "";
        this.state.selectedIndex = 0;
        this.state.isOpen = false;
        return;
      }

      // Only fetch while actively interacting with the input.
      if (document.activeElement !== this.searchInput()) return;

      this.debounceTimer = window.setTimeout(() => {
        this.debounceTimer = null;
        void this.requestAutocomplete(trimmedQuery);
      }, 120);
    });
    this.$watch("state.isOpen", (isOpen: boolean) => {
      this.$el.classList.toggle("is-autocomplete-open", isOpen);
    });
    this.$watch("state.selectedIndex", (selectedIndex: number) => {
      if (!this.state.isOpen) return;
      this.highlightSelectedOption(selectedIndex);
    });

    document.addEventListener("click", (event) => {
      if (
        event.target instanceof HTMLElement &&
        !event.target.closest("#search-autocomplete-container")
      ) {
        this.hide();
      }
    });

    document.addEventListener("htmx:historyRestore", () => {
      this.restoreSearchQuery();
    });

    this.restoreSearchQuery();
  },

  /** couple helpers to grab DOM elements */
  searchInput() {
    return this.$refs.searchInput as HTMLInputElement;
  },

  searchForm() {
    return this.$refs.searchForm as HTMLFormElement;
  },

  menu() {
    return this.$refs.menu as HTMLElement;
  },

  /** input handlers */
  onInput() {
    this.state.query = this.searchInput().value;
    this.state.selectedIndex = 0;
  },

  onInputFocus() {
    if (!this.searchInput().value.trim()) return;
    this.state.isOpen = true;
  },

  onKeyDown(event: KeyboardEvent) {
    const hasMenu = this.state.isOpen;
    const optionCount = this.menu().children.length;

    if (event.key === "ArrowDown" && hasMenu && optionCount > 0) {
      event.preventDefault();
      this.state.selectedIndex = (this.state.selectedIndex + 1) % optionCount;
      return;
    }

    if (event.key === "ArrowUp" && hasMenu && optionCount > 0) {
      event.preventDefault();
      this.state.selectedIndex =
        (this.state.selectedIndex - 1 + optionCount) % optionCount;
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const query =
        hasMenu && optionCount > 0
          ? this.getOptionQuery(this.state.selectedIndex) ||
            this.searchInput().value
          : this.searchInput().value.trim();
      this.executeSearch(query);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      this.hide();
    }
  },

  onMenuClick(event: Event) {
    if (!(event.target instanceof Element)) return;
    const clicked = event.target.closest<HTMLElement>("[data-query]");
    if (!clicked) return;
    this.state.selectedIndex = Number(clicked.dataset.index || "0");
    this.executeSearch(clicked.dataset.query || this.searchInput().value);
  },

  onMenuMouseOver(event: Event) {
    if (!(event.target instanceof Element)) return;
    const hovered = event.target.closest<HTMLElement>("[data-index]");
    if (!hovered) return;
    const hoveredIndex = Number(hovered.dataset.index || "-1");
    if (hoveredIndex < 0 || hoveredIndex === this.state.selectedIndex) return;
    this.state.selectedIndex = hoveredIndex;
  },

  /* Make sure the search query is restored on page load */
  restoreSearchQuery() {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) {
      this.searchInput().value = query;
      this.state.query = query;
    } else {
      this.searchInput().value = "";
      this.state.query = "";
    }
    this.state.isOpen = false;
  },

  /* When you click outside or hit escape, clear in-flight stuff and close the menu */
  hide() {
    this.cancelPendingAutocomplete();
    this.state.isOpen = false;
  },

  cancelPendingAutocomplete() {
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  },

  /** Render the actual suggestions in the box.
   *
   * Turn the list of suggestions into AutocompleteOptions, then pass off to
   * _renderAutocompleteMenu to transform those into DOM elements.
   */
  renderAutocomplete(query: string) {
    this.state.query = query;
    const trimmedQuery = query.trim();

    const options: AutocompleteOption[] = !trimmedQuery
      ? []
      : [
          {
            kind: "search",
            label: `Search for "${trimmedQuery}"`,
            query: trimmedQuery,
          },
          ...this.state.suggestions.map((name) => ({
            kind: "name" as const,
            name,
            query: `name:${name}`,
          })),
        ];

    if (options.length === 0) {
      this.menu().innerHTML = "";
      this.state.selectedIndex = 0;
      this.state.isOpen = false;
      return;
    }

    this.state.selectedIndex = Math.min(
      this.state.selectedIndex,
      options.length - 1,
    );
    this._renderAutocompleteMenu(options);
    this.state.isOpen = true;
  },

  /** Turn AutocompleteOptions into DOM elements
   *
   * They're buttons, and we add some data-x attributes for easy identification
   * down the line. We also highlight the matched text.
   */
  _renderAutocompleteMenu(options: AutocompleteOption[]) {
    const menu = this.menu();
    menu.innerHTML = "";

    options.forEach((option, index) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "search-autocomplete-item px-3 py-2";
      if (index === this.state.selectedIndex) {
        item.classList.add("is-selected");
      }
      item.dataset.index = index.toString();
      item.dataset.query = option.query;
      const highlightSource =
        option.kind === "name" ? option.name : option.label;

      if (option.kind === "name") {
        const prefix = document.createElement("span");
        prefix.className = "has-text-grey";
        prefix.textContent = "name:";
        item.append(prefix, " ");
      }
      item.append(
        this.buildHighlightedContent(highlightSource, this.state.query),
      );

      menu.appendChild(item);
    });
  },

  highlightSelectedOption(index: number) {
    const old = this.menu().querySelector(
      ".search-autocomplete-item.is-selected",
    );
    if (old instanceof HTMLElement) {
      old.classList.remove("is-selected");
    }

    const new_ = this.menu().children[index];
    if (new_ instanceof HTMLElement) {
      new_.classList.add("is-selected");
    }
  },

  getOptionQuery(index: number) {
    const selected = this.menu().children[index];
    if (!(selected instanceof HTMLElement)) return null;
    return selected.dataset.query || null;
  },

  executeSearch(query: string) {
    this.cancelPendingAutocomplete();
    this.searchInput().value = query;
    this.state.isOpen = false;
    this.searchForm().requestSubmit();
  },

  async requestAutocomplete(query: string) {
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();

    const url = new URL(window.location.href);
    url.pathname = "/search/autocomplete";
    url.searchParams.set("q", query);

    try {
      const response = await fetch(`${url.pathname}${url.search}`, {
        signal: this.abortController.signal,
      });
      if (!response.ok) throw new Error("autocomplete request failed");

      const payload = (await response.json()) as AutocompletePayload;
      if (this.searchInput().value !== query) return;
      this.state.suggestions = payload.suggestions || [];
      this.renderAutocomplete(query);
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      if (this.searchInput().value !== query) return;
      this.state.suggestions = [];
      this.renderAutocomplete(query);
    }
  },

  buildHighlightedContent(text: string, query: string) {
    const fragment = document.createDocumentFragment();
    const needle = query.trim();
    if (!needle) {
      fragment.append(text);
      return fragment;
    }

    const start = text.toLowerCase().indexOf(needle.toLowerCase());
    if (start < 0) {
      fragment.append(text);
      return fragment;
    }

    const end = start + needle.length;
    const strong = document.createElement("strong");
    strong.textContent = text.slice(start, end);
    fragment.append(text.slice(0, start), strong, text.slice(end));
    return fragment;
  },
}));

document.addEventListener("DOMContentLoaded", () => {
  Alpine.start();
});
