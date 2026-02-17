const esbuild = require("esbuild");
const fs = require("fs");
const path = require("path");

function findTsEntryPoints(dirPath) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...findTsEntryPoints(fullPath));
      continue;
    }
    // NOTE 2026-02-17: *.d.ts are declaration files - will break the build if
    // included. We probably won't use them but if we don't add this safeguard
    // we'll have annoying debugging if we ever add them.
    if (
      entry.isFile() &&
      entry.name.endsWith(".ts") &&
      !entry.name.endsWith(".d.ts")
    ) {
      files.push(fullPath);
    }
  }
  return files.sort();
}

async function build() {
  const entryPoints = findTsEntryPoints(path.join(__dirname, "src"));

  await esbuild.build({
    entryPoints,
    plugins: [],
    outdir: "eel_hole/static",
    format: "esm",
    bundle: true,
    target: "es2022",
    assetNames: "[name]",
  });

  // Rename preview.css to index.css since base.html references index.css
  fs.renameSync("eel_hole/static/preview.css", "eel_hole/static/index.css");
}

build();
