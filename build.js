const esbuild = require("esbuild");
const fs = require("fs");
const path = require("path");

async function build() {
    await esbuild.build({
        entryPoints: ["src/index.ts", "src/preview.ts"],
        plugins: [],
        outdir: "dist",
        format: "esm",
        bundle: true,
        target: "es2022",
        assetNames: "[name]",
    });
}

build();
