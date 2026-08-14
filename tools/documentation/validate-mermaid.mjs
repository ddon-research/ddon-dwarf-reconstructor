import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const toolDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryDirectory = resolve(toolDirectory, "../..");
const mmdcCli = join(
  toolDirectory,
  "node_modules",
  "@mermaid-js",
  "mermaid-cli",
  "src",
  "cli.js",
);
const markdownFiles = [
  join(repositoryDirectory, "README.md"),
  ...findMarkdownFiles(join(repositoryDirectory, "docs")),
];
const mermaidFence = /^```[ \t]*mermaid[ \t]*\r?\n([\s\S]*?)^```[ \t]*$/gim;
const temporaryDirectory = mkdtempSync(join(tmpdir(), "ddon-mermaid-"));
const puppeteerConfigPath = createPuppeteerConfig(temporaryDirectory);
let diagramCount = 0;
let failureCount = 0;

try {
  for (const markdownFile of markdownFiles) {
    const source = readFileSync(markdownFile, "utf8");
    let match;
    while ((match = mermaidFence.exec(source)) !== null) {
      diagramCount += 1;
      const diagramName = `${String(diagramCount).padStart(3, "0")}.mmd`;
      const inputPath = join(temporaryDirectory, diagramName);
      const outputPath = join(temporaryDirectory, `${diagramName}.svg`);
      writeFileSync(inputPath, `${match[1].trim()}\n`, "utf8");

      const cliArguments = [mmdcCli, "--input", inputPath, "--output", outputPath, "--quiet"];
      if (puppeteerConfigPath !== null) {
        cliArguments.push("--puppeteerConfigFile", puppeteerConfigPath);
      }
      const result = spawnSync(process.execPath, cliArguments, { encoding: "utf8" });
      if (result.status !== 0) {
        const line = source.slice(0, match.index).split(/\r?\n/).length;
        const detail = (
          result.error?.message ||
          result.stderr ||
          result.stdout ||
          "unknown Mermaid CLI error"
        ).trim();
        console.error(`${relative(repositoryDirectory, markdownFile)}:${line}: ${detail}`);
        failureCount += 1;
      }
    }
    mermaidFence.lastIndex = 0;
  }
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}

if (failureCount > 0) {
  console.error(`Mermaid validation failed for ${failureCount} of ${diagramCount} diagrams.`);
  process.exitCode = 1;
} else {
  console.log(`Validated ${diagramCount} Mermaid diagrams in ${markdownFiles.length} Markdown files.`);
}

function findMarkdownFiles(directory) {
  const files = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) {
      files.push(...findMarkdownFiles(path));
    } else if (path.endsWith(".md")) {
      files.push(path);
    }
  }
  return files.sort();
}

function createPuppeteerConfig(directory) {
  if (process.platform !== "linux" || !process.env.CI) {
    return null;
  }

  // GitHub-hosted Linux runners do not permit Chromium's setuid/user-namespace
  // sandbox. This validator processes repository Markdown only, so use the
  // documented CI workaround without weakening local developer runs.
  const configPath = join(directory, "puppeteer.json");
  writeFileSync(
    configPath,
    JSON.stringify({ args: ["--no-sandbox", "--disable-setuid-sandbox"] }),
    "utf8",
  );
  return configPath;
}
