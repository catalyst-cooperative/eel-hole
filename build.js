const esbuild = require("esbuild");
const fs = require("fs");
const path = require("path");

async function build() {
  await esbuild.build({
    entryPoints: ["src/preview.ts"],
    plugins: [],
    outdir: "dist",
    format: "esm",
    bundle: true,
    target: "es2022",
    assetNames: "[name]",
  });

  // Rename preview.css to index.css since base.html references index.css
  fs.renameSync("dist/preview.css", "dist/index.css");
}

build();
