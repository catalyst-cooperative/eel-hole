interface AutocompleteOption {
  type: "search" | "autocomplete";
  label?: string;
  name?: string;
  query: string;
}

interface AutocompletePayload {
  suggestions?: string[];
}

declare const htmx: {
  ajax: (
    method: string,
    url: string,
    options: { target: string; swap: string },
  ) => void;
};

let autocompleteAbortController: AbortController | null = null;
let autocompleteDebounceTimer: number | null = null;
let autocompleteOptions: string[] = [];
let autocompleteSelectedIndex = 0;

function cancelPendingAutocomplete(): void {
  if (autocompleteDebounceTimer !== null) {
    window.clearTimeout(autocompleteDebounceTimer);
    autocompleteDebounceTimer = null;
  }
  if (autocompleteAbortController) {
    autocompleteAbortController.abort();
    autocompleteAbortController = null;
  }
}

function setAutocompleteOpenState(isOpen: boolean): void {
  const container = document.getElementById("search-autocomplete-container");
  if (!container) return;
  container.classList.toggle("is-autocomplete-open", isOpen);
}

function hideAutocomplete(): void {
  const menu = document.getElementById("search-autocomplete");
  if (menu) {
    menu.classList.add("is-hidden");
  }
  setAutocompleteOpenState(false);
}

function escapeHtml(text: string): string {
  const escaped = document.createElement("div");
  escaped.textContent = text;
  return escaped.innerHTML;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightQuery(text: string, query: string): string {
  const escapedText = escapeHtml(text);
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return escapedText;
  }

  const directRegex = new RegExp(`(${escapeRegExp(trimmedQuery)})`, "i");
  if (directRegex.test(escapedText)) {
    return escapedText.replace(directRegex, "<strong>$1</strong>");
  }

  const tokens = (trimmedQuery.toLowerCase().match(/[a-z0-9]+/g) || []).filter(
    (token) => token.length > 0,
  );
  if (tokens.length === 0) {
    return escapedText;
  }

  const tokenRegex = new RegExp(
    `(${tokens
      .sort((a, b) => b.length - a.length)
      .map((token) => escapeRegExp(token))
      .join("|")})`,
    "gi",
  );
  return escapedText.replace(tokenRegex, "<strong>$1</strong>");
}

function buildSearchUrl(query: string): URL {
  const url = new URL(window.location.href);
  url.pathname = "/search";
  if (query) {
    url.searchParams.set("q", query);
  } else {
    url.searchParams.delete("q");
  }
  return url;
}

function executeSearch(query: string): void {
  const searchInput =
    document.querySelector<HTMLInputElement>('input[name="q"]');
  if (!searchInput) return;

  cancelPendingAutocomplete();
  searchInput.value = query;
  hideAutocomplete();
  const url = buildSearchUrl(query);
  htmx.ajax("GET", `${url.pathname}${url.search}`, {
    target: "#search-results",
    swap: "innerHTML",
  });
  history.replaceState({}, "", `${url.pathname}${url.search}`);
}

function renderAutocompleteOptions(query: string): void {
  const menu = document.getElementById("search-autocomplete");
  if (!menu) return;

  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    hideAutocomplete();
    return;
  }

  const options: AutocompleteOption[] = [
    {
      type: "search",
      label: `Search for "${trimmedQuery}"`,
      query: trimmedQuery,
    },
    ...autocompleteOptions.map((name) => ({
      type: "autocomplete" as const,
      name,
      query: `name:${name}`,
    })),
  ];
  autocompleteSelectedIndex = Math.min(
    autocompleteSelectedIndex,
    options.length - 1,
  );

  menu.innerHTML = "";
  options.forEach((option, index) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "search-autocomplete-item";
    if (index === autocompleteSelectedIndex) {
      item.classList.add("is-selected");
    }
    item.setAttribute("data-index", index.toString());
    item.setAttribute("data-query", option.query);
    if (option.type === "autocomplete") {
      const nameLabel = highlightQuery(option.name || "", query);
      item.innerHTML = `<span class="has-text-grey">name:</span> ${nameLabel}`;
    } else {
      item.innerHTML = highlightQuery(option.label || "", query);
    }
    menu.appendChild(item);
  });

  menu.classList.remove("is-hidden");
  setAutocompleteOpenState(true);
}

function requestAutocomplete(query: string): void {
  if (autocompleteAbortController) {
    autocompleteAbortController.abort();
  }
  autocompleteAbortController = new AbortController();

  const url = new URL(window.location.origin);
  url.pathname = "/search/autocomplete";
  url.searchParams.set("q", query);

  // Preserve active feature-variant URL params for server-side filtering.
  const currentUrl = new URL(window.location.href);
  const variants = currentUrl.searchParams.get("variants");
  if (variants) {
    url.searchParams.set("variants", variants);
  }

  fetch(`${url.pathname}${url.search}`, {
    signal: autocompleteAbortController.signal,
  })
    .then((response) => {
      if (!response.ok) throw new Error("autocomplete request failed");
      return response.json() as Promise<AutocompletePayload>;
    })
    .then((payload) => {
      autocompleteOptions = payload.suggestions || [];
      renderAutocompleteOptions(query);
    })
    .catch((error: Error) => {
      if (error.name !== "AbortError") {
        autocompleteOptions = [];
        renderAutocompleteOptions(query);
      }
    });
}

function scheduleAutocomplete(query: string): void {
  if (autocompleteDebounceTimer !== null) {
    window.clearTimeout(autocompleteDebounceTimer);
  }
  autocompleteDebounceTimer = window.setTimeout(() => {
    autocompleteDebounceTimer = null;
    requestAutocomplete(query);
  }, 120);
}

function restoreSearchQuery(): void {
  const params = new URLSearchParams(window.location.search);
  const query = params.get("q");
  const searchInput =
    document.querySelector<HTMLInputElement>('input[name="q"]');
  if (searchInput && query) {
    searchInput.value = query;
  }
  hideAutocomplete();
}

function initializeAutocomplete(): void {
  const searchInput =
    document.querySelector<HTMLInputElement>('input[name="q"]');
  const menu = document.getElementById("search-autocomplete");
  if (!searchInput || !menu) return;

  searchInput.addEventListener("input", () => {
    autocompleteSelectedIndex = 0;
    scheduleAutocomplete(searchInput.value);
  });

  searchInput.addEventListener("keydown", (event) => {
    const hasMenu = !menu.classList.contains("is-hidden");
    const optionCount = menu.children.length;

    if (event.key === "ArrowDown" && hasMenu && optionCount > 0) {
      event.preventDefault();
      autocompleteSelectedIndex = (autocompleteSelectedIndex + 1) % optionCount;
      renderAutocompleteOptions(searchInput.value);
      return;
    }
    if (event.key === "ArrowUp" && hasMenu && optionCount > 0) {
      event.preventDefault();
      autocompleteSelectedIndex =
        (autocompleteSelectedIndex - 1 + optionCount) % optionCount;
      renderAutocompleteOptions(searchInput.value);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (hasMenu && optionCount > 0) {
        const selected = menu.children[autocompleteSelectedIndex];
        if (selected instanceof HTMLElement) {
          executeSearch(selected.dataset.query || searchInput.value);
        }
      } else {
        executeSearch(searchInput.value.trim());
      }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      hideAutocomplete();
    }
  });

  menu.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const clicked = event.target.closest("[data-query]");
    if (!(clicked instanceof HTMLElement)) return;
    const selectedIndex = Number(clicked.dataset.index || "0");
    autocompleteSelectedIndex = selectedIndex;
    executeSearch(clicked.dataset.query || searchInput.value);
  });

  document.addEventListener("click", (event) => {
    if (
      event.target instanceof HTMLElement &&
      !event.target.closest("#search-autocomplete-container")
    ) {
      hideAutocomplete();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  restoreSearchQuery();
  initializeAutocomplete();
});

document.addEventListener("htmx:historyRestore", restoreSearchQuery);
