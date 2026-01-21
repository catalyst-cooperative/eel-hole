import * as duckdb from "@duckdb/duckdb-wasm";
import * as arrow from "apache-arrow";

import {
  DATE_TS_TYPE_IDS,
  DATE_TYPE_IDS,
  TIMESTAMP_TYPE_IDS,
} from "./constants";
import {
  createGrid,
  themeQuartz,
  colorSchemeDark,
  ModuleRegistry,
  AllCommunityModule,
  GridApi,
  GridOptions,
} from "ag-grid-community";
import Alpine, { AlpineComponent } from "alpinejs";

import "./index.css";

ModuleRegistry.registerModules([AllCommunityModule]);

interface Filter {
  /**
   * Describe one column filter. Mirrors FilterRule in the Python code.
   *
   * TODO 2025-01-15: Define these interfaces in one place - maybe with JSONSchema?
   */
  fieldName: string;
  fieldType: string;
  operation: string;
  value: any;
  valueTo: any;
}

interface QuerySpec {
  /**
   * What we need to send a query to duckdb.
   */
  statement: string;
  count_statement: string;
  values: Array<any>;
}

interface QueryEndpointPayload {
  /**
   * This is what we need to actually get a query back from the server.
   *
   * TODO 2025-02-13: conn probably shouldn't be in here.
   */
  conn: duckdb.AsyncDuckDBConnection;
  tableName: string;
  filters: Array<Filter>;
  page: number;
  perPage: number;
}

interface PreviewTableState extends AlpineComponent<{}> {
  /**
   * Table state for the preview page Alpine component.
   *
   * Properties that remain nullable are set after first data load.
   */
  // Set on construction - table name is fixed for preview pages
  tableName: string;

  // Set after first data load
  numRowsMatched: number | null;

  // Set during construction
  numRowsDisplayed: number;
  addedTables: Set<string>;
  csvExportPageSize: number;
  exporting: boolean;
  loading: boolean;
  darkMode: boolean;

  // Initialized in init() - guaranteed non-null after Alpine starts
  gridApi: GridApi;
  db: duckdb.AsyncDuckDB;
  conn: duckdb.AsyncDuckDBConnection;

  init(): Promise<void>;
  exportCsv: () => Promise<void>;
  csvAllowed: () => boolean;
  csvText: () => string;
}

Alpine.data("previewTableState", (tableName: string) => ({
  tableName,
  numRowsMatched: null,
  numRowsDisplayed: 0,
  addedTables: new Set(),
  csvExportPageSize: 1_000_000,
  exporting: false,
  loading: true, // Start as loading since we load data immediately in init()
  darkMode: window.matchMedia("(prefers-color-scheme: dark)").matches,
  gridApi: null as any, // Initialized in init()
  db: null as any, // Initialized in init()
  conn: null as any, // Initialized in init()

  async init() {
    /**
     * Alpine will automatically call this before rendering the component -
     * see https://alpinejs.dev/globals/alpine-data#init-functions
     *
     * - makes an AG Grid with loading overlay showing
     * - initializes duckDB (slow, loading overlay shows during this)
     * - loads the table data immediately
     */
    console.log("Initializing preview for table:", this.tableName);

    const gridOptions: GridOptions = {
      onFilterChanged: async () => refreshTable(this),
      tooltipShowDelay: 500,
      tooltipHideDelay: 15000,
    };
    const host = document.getElementById("data-table")!;
    this.gridApi = createGrid(host, gridOptions);
    this.gridApi.setGridOption("loading", true);

    this.db = await _initializeDuckDB();
    this.conn = await this.db.connect();
    await this.conn.query("SET default_collation='nocase';");

    await refreshTable(this);
    this.loading = false;

    const setTheme = () => {
      console.log("setting theme");
      const darkMode = window.matchMedia(
        "(prefers-color-scheme: dark)",
      ).matches;
      const theme = darkMode
        ? themeQuartz.withPart(colorSchemeDark)
        : themeQuartz;
      this.gridApi.setGridOption("theme", theme);
    };
    setTheme();
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", setTheme);
  },

  async exportCsv() {
    /**
     * Download data one giant page at a time, and then export to CSV.
     */
    const { conn, tableName, gridApi, csvExportPageSize, numRowsMatched } =
      this;
    if (!tableName || !numRowsMatched) return;

    this.exporting = true;
    const numPages = Math.ceil(numRowsMatched / csvExportPageSize);

    for (let i = 1; i <= numPages; i++) {
      const filename = numPages === 1 ? tableName : `${tableName}_part${i}`;
      await exportPage(gridApi, filename, {
        conn,
        tableName,
        page: i,
        perPage: csvExportPageSize,
        filters: getFilters(gridApi),
      });
    }
    this.exporting = false;
  },

  csvAllowed() {
    return (
      this.numRowsMatched !== null &&
      this.numRowsMatched <= 5 * this.csvExportPageSize
    );
  },

  csvText() {
    if (!this.numRowsMatched) return "No data to export";

    const numPages = Math.ceil(this.numRowsMatched / this.csvExportPageSize);
    if (!this.csvAllowed()) {
      return "Over export limit (5M rows) - try filtering!";
    }
    if (numPages === 1) {
      return `Export ${this.numRowsMatched.toLocaleString()} rows as CSV`;
    }
    return `Export ${this.numRowsMatched.toLocaleString()} rows as ${numPages.toLocaleString()} CSVs`;
  },
}));

Alpine.start();

async function refreshTable(state: PreviewTableState) {
  /**
   * Re-query the data given the current table state.
   *
   * TODO 2025-02-13 - since this mutates table state, maybe it should live in
   * the table state object too?
   *
   * - check if the table has been registered - if not, register it.
   * - grab filters, table name, and get arrowData + a count back.
   * - turn arrowData into gridOptions.
   * - update the counters.
   * - throw the gridOptions at the gridApi.
   */
  const { tableName, conn, db, gridApi, addedTables } = state;

  gridApi.setGridOption("loading", true);

  if (!tableName) {
    gridApi.setGridOption("loading", false);
    return;
  }

  if (!addedTables.has(tableName)) {
    await _addTableToDuckDB(db, tableName);
    addedTables.add(tableName);
  }
  const filters = getFilters(gridApi);
  const { arrowData, numRowsMatched } = await getAndCountData({
    conn,
    tableName,
    filters,
    page: 1,
    perPage: 10_000,
  });
  const gridOptions = arrowTableToAgGridOptions(arrowData);
  gridApi.updateGridOptions(gridOptions);

  state.numRowsMatched = numRowsMatched;
  state.numRowsDisplayed = arrowData.numRows;
  gridApi.setGridOption("loading", false);
}

function getFilters(gridApi: GridApi): Array<Filter> {
  /**
   * Convert GridApi filter model to a list of Filters.
   *
   * TODO 2025-02-13: if we start getting multiple filter conditions on each
   * column we will have to handle this differently - i.e. we'll have to retool
   * the Filter type altogether.
   */
  console.log(gridApi.getFilterModel());
  return Object.entries(gridApi.getFilterModel()).map(
    ([
      fieldName,
      { filterType, type, filter, filterTo, dateFrom, dateTo },
    ]) => ({
      fieldName,
      fieldType: filterType,
      operation: type,
      value: filter || dateFrom,
      valueTo: filterTo || dateTo,
    }),
  );
}

async function getAndCountData(params: QueryEndpointPayload) {
  /**
   * Get the data, and also count how many the full result would be.
   *
   * - get the DuckDB query
   * - run the main query and the count query on DuckDB
   * - return both
   */
  const { conn, tableName, filters, page, perPage } = params;
  const {
    statement,
    count_statement: countStatement,
    values: filterVals,
  } = await _getDuckDBQuery({ tableName, filters: filters, page, perPage });
  const stmt = await conn.prepare(statement);
  const counter = await conn.prepare(countStatement);
  const [countResult, arrowData] = await Promise.all([
    counter.query(...filterVals),
    stmt.query(...filterVals),
  ]);
  const numRowsMatched = parseInt(
    countResult?.getChild("count_star()")?.get(0),
  );

  return { arrowData, numRowsMatched };
}

async function getData(params: QueryEndpointPayload) {
  /**
   * Get the data, and also count how many the full result would be.
   *
   * - get the DuckDB query
   * - run the main query on DuckDB
   */
  const { conn, tableName, filters, page, perPage } = params;
  const { statement, values: filterVals } = await _getDuckDBQuery({
    tableName,
    filters: filters,
    page,
    perPage,
  });
  const stmt = await conn.prepare(statement);
  const arrowData = await stmt.query(...filterVals);
  return arrowData;
}

async function exportPage(
  gridApi: GridApi,
  filename: string,
  params: QueryEndpointPayload,
) {
  /**
   * Actually do the downloading/CSV export for a single page.
   *
   * - get data
   * - reshape it into CSV
   * - make a blob
   * - download it
   */
  const arrowTable = await getData(params);
  const { rowData } = arrowTableToAgGridOptions(arrowTable);

  const columns = gridApi.getColumns()?.map((col) => col.colId) ?? [];
  const headers = columns.join(",");

  // get row values in the order of the columns passed in, then do one big string conversion using JSON.stringify.
  const rows = JSON.stringify(
    rowData!.map((row) => columns.map((col) => row[col])),
  )
    .replace(/\],\[/g, "\n")
    .replace(/\[\[|\]\]/g, "");

  // make a binary file to download.
  const blob = new Blob([`${headers}\n${rows}`], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${filename}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function arrowTableToAgGridOptions(table: arrow.Table): GridOptions {
  /**
   * Convert an Arrow table into something AG Grid can understand - a list of
   * records and a funny bespoke schema object (columnDefs).
   *
   * We have to set some different options based on the type information in
   * Arrow - i.e. date formatting.
   *
   * TODO 2025-02-13: If we want to make a custom filter UI for specific types
   * (i.e. datetimes, categoricals) we'll need to set them in typeOpts.
   */
  const utcComparator = (filter, cell) => {
    const filterUTC = filter.getTime() - filter.getTimezoneOffset() * 60_000;
    return cell.getTime() - filterUTC;
  };
  const timestampOpts = new Map(
    [...TIMESTAMP_TYPE_IDS].map((tid) => [
      tid,
      {
        valueFormatter: (p) => `${p.value?.toISOString().split(".")[0]}`,
        filterParams: {
          maxNumConditions: 1,
          buttons: ["apply", "clear", "reset"],
          comparator: utcComparator,
          browserDatePicker: false,
          dateFormat: "yyyy-MM-dd",
        },
      },
    ]),
  );

  const dateOpts = new Map(
    [...DATE_TYPE_IDS].map((tid) => [
      tid,
      {
        valueFormatter: (p) => p.value?.toISOString().split("T")[0],
        filterParams: {
          maxNumConditions: 1,
          buttons: ["apply", "clear", "reset"],
          comparator: utcComparator,
          browserDatePicker: false,
          dateFormat: "yyyy-MM-dd",
        },
      },
    ]),
  );
  const typeOpts = new Map([...timestampOpts, ...dateOpts]);

  // TODO 2025-02-19: it would be nice to add the column descriptions into the header tooltip. might want to grab the datapackage.json for that.
  const defaultOpts = {
    filter: true,
    filterParams: { maxNumConditions: 1, buttons: ["apply", "clear", "reset"] },
    tooltipValueGetter: ({ value }) => {
      const isLongString = typeof value === "string" && value.length > 20;
      return isLongString ? value : null;
    },
  };

  const schema = table.schema;
  const columnDefs = schema.fields.map((f) => ({
    ...defaultOpts,
    ...(typeOpts.get(f.type.typeId) ?? {}),
    field: f.name,
    headerName: f.name,
  }));
  const timestampColumns = schema.fields
    .filter((f) => DATE_TS_TYPE_IDS.has(f.type.typeId))
    .map((f) => f.name);
  const rowData = table
    .toArray()
    .map((row) => convertDatetimes(timestampColumns, row.toJSON()));
  return { columnDefs, rowData };
}

function convertDatetimes(
  timestampColumns: Array<string>,
  row: Object,
): Object {
  /**
   * Convert the integer timestamps that Arrow uses into JS Date objects.
   */
  timestampColumns.forEach((col) => {
    row[col] = new Date(row[col]);
  });
  return row;
}

async function _initializeDuckDB(): Promise<duckdb.AsyncDuckDB> {
  /**
   * Get the duckdb library that works best for your system, then spin up a web
   * worker for it.
   */
  const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();

  // Select a bundle based on browser checks
  const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);

  const worker_url = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], {
      type: "text/javascript",
    }),
  );

  // Instantiate the asynchronous version of DuckDB-wasm
  const worker = new Worker(worker_url);
  const logger = new duckdb.ConsoleLogger();
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  URL.revokeObjectURL(worker_url);
  return db;
}

async function _addTableToDuckDB(db: duckdb.AsyncDuckDB, tableName: string) {
  /**
   * Register the table in DuckDB so that it can cache useful metadata etc.
   */
  const baseUrl =
    "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/eel-hole/";
  const filename = `${tableName}.parquet`;
  const url = `${baseUrl}${filename}`;
  await db.registerFileURL(
    filename,
    url,
    duckdb.DuckDBDataProtocol.HTTP,
    false,
  );
}

async function _getDuckDBQuery({
  tableName,
  filters,
  page = 1,
  perPage = 10000,
}: {
  tableName: string;
  filters: Array<Filter>;
  page?: number;
  perPage?: number;
}): Promise<QuerySpec> {
  /**
   * Get DuckDB query from the backend, based on the filter rules & what table we're looking at.
   */
  const params = new URLSearchParams({
    name: `${tableName}.parquet`,
    filters: JSON.stringify(filters),
    page: page.toString(),
    perPage: perPage.toString(),
  });
  const resp = await fetch("/api/duckdb?" + params);
  const query = await resp.json();
  console.log("QuerySpec:", query);
  return query;
}
