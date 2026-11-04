// Generate TypeScript types from the contract JSON Schemas (DESIGN.md §3.1, §6.4).
//
//   node scripts/gen-contract-types.mjs           write src/contracts/schemas/*.ts
//   node scripts/gen-contract-types.mjs --check   exit 1 if the files on disk are stale
//
// Source: packages/flywheel-contracts/schemas/*.json. One output file per schema,
// because several schemas define $defs with the same name (Cost, Unavailable, ...)
// and one combined file would collide.
import { readdir, readFile, writeFile, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { compile } from "json-schema-to-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const schemaDir = path.resolve(here, "../../../packages/flywheel-contracts/schemas");
const outDir = path.resolve(here, "../src/contracts/schemas");
const check = process.argv.includes("--check");

const banner = [
  "// File sinh ra. Không sửa tay.",
  "// Nguồn: packages/flywheel-contracts/schemas/*.json · sinh lại: npm run gen:types",
].join("\n");

const normalise = (text) => text.replace(/\r\n/g, "\n");

async function render() {
  const names = (await readdir(schemaDir)).filter((f) => f.endsWith(".json")).sort();
  const files = new Map();
  for (const file of names) {
    const name = path.basename(file, ".json");
    const schema = JSON.parse(await readFile(path.join(schemaDir, file), "utf8"));
    // The type name is the file name, not the schema title, so imports are predictable.
    const ts = await compile({ ...schema, title: name }, name, {
      bannerComment: banner,
      additionalProperties: false,
      unreachableDefinitions: true,
      format: true,
      style: { singleQuote: false, printWidth: 100 },
    });
    files.set(`${name}.ts`, normalise(ts));
  }
  const index = [banner, ...[...files.keys()].map((f) => {
    const name = path.basename(f, ".ts");
    return `export type { ${name} } from "./${name}";`;
  })].join("\n") + "\n";
  files.set("index.ts", index);
  return files;
}

const files = await render();

if (check) {
  const stale = [];
  for (const [file, text] of files) {
    let current = null;
    try {
      current = normalise(await readFile(path.join(outDir, file), "utf8"));
    } catch {
      current = null;
    }
    if (current !== text) stale.push(file);
  }
  const extra = (await readdir(outDir).catch(() => [])).filter((f) => !files.has(f));
  if (stale.length || extra.length) {
    console.error(`contract types are stale: ${[...stale, ...extra].join(", ")}`);
    console.error("run: npm run gen:types");
    process.exit(1);
  }
  console.log(`contract types up to date (${files.size} files)`);
} else {
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  for (const [file, text] of files) await writeFile(path.join(outDir, file), text);
  console.log(`wrote ${files.size} files to ${path.relative(process.cwd(), outDir)}`);
}
