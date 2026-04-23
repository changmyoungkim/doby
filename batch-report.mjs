#!/usr/bin/env node

/**
 * Stop hook — reads stmemory-pending.txt and reports accumulated changes.
 * Only injects a reminder if there ARE pending changes. Zero cost otherwise.
 *
 * Auto-detects project root by walking up from cwd to find .omc/ directory.
 */

import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { cwd } from "process";

/**
 * Walk up from a given path to find the project root by locating .omc/ directory.
 * @param {string} startPath - Starting path (file or directory)
 * @returns {string|null} - Project root path or null if not found
 */
function findProjectRoot(startPath) {
  let current = startPath;

  // Walk up the directory tree
  while (current !== "/" && current !== "") {
    const omcPath = join(current, ".omc");
    if (existsSync(omcPath)) {
      return current;
    }
    current = dirname(current);
  }

  return null;
}

const projectRoot = findProjectRoot(cwd());
if (!projectRoot) {
  process.exit(0);
}

const PENDING_FILE = join(projectRoot, ".omc/state/stmemory-pending.txt");

if (!existsSync(PENDING_FILE)) {
  process.exit(0);
}

const content = readFileSync(PENDING_FILE, "utf8").trim();
if (!content) process.exit(0);

const lines = content.split("\n");
const plans = lines.filter((l) => l.includes("\tplan\t"));
const codes = lines.filter((l) => l.includes("\tcode\t"));

const parts = [];
if (plans.length > 0) {
  parts.push(
    `plan docs ${plans.length}: ${plans.map((l) => l.split("\t")[2]).join(", ")}`
  );
}
if (codes.length > 0) {
  parts.push(
    `code ${codes.length}: ${codes.map((l) => l.split("\t")[2]).join(", ")}`
  );
}

const msg = `[stmemory] Files changed during session ${lines.length} — ${parts.join(" / ")}. Run /stmemory update in the next session.`;

process.stdout.write(JSON.stringify({ additionalContext: msg }));
