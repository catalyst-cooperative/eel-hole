const esbuild = require("esbuild");
const fs = require("fs");
const path = require("path");

function removeIfExists(filePath) {
  try {
    fs.unlinkSync(filePath);
  } catch (error) {
    if (error.code !== "ENOENT") {
      throw error;
    }
  }
}

function ensureRelativeSymlink({ target, linkPath }) {
  const linkDir = path.dirname(linkPath);
  fs.mkdirSync(linkDir, { recursive: true });
  removeIfExists(linkPath);
  const relativeTarget = path.relative(linkDir, target);
  fs.symlinkSync(relativeTarget, linkPath);
}

async function build() {
  await esbuild.build({
    entryPoints: ["src/preview.ts", "src/search.ts"],
    plugins: [],
    outdir: "dist",
    format: "esm",
    bundle: true,
    target: "es2022",
    assetNames: "[name]",
  });

  // Rename preview.css to index.css since base.html references index.css
  fs.renameSync("dist/preview.css", "dist/index.css");

  // Link compiled assets into Flask static directory.
  ensureRelativeSymlink({
    target: path.join(__dirname, "dist/index.css"),
    linkPath: path.join(__dirname, "eel_hole/static/index.css"),
  });
  ensureRelativeSymlink({
    target: path.join(__dirname, "dist/preview.js"),
    linkPath: path.join(__dirname, "eel_hole/static/preview.js"),
  });
  ensureRelativeSymlink({
    target: path.join(__dirname, "dist/search.js"),
    linkPath: path.join(__dirname, "eel_hole/static/search.js"),
  });
}

build();
