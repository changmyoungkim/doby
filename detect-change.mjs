#!/usr/bin/env node

/**
 * PostToolUse hook for doby — zero-token change tracking.
 * Appends changed file paths to a pending list. No LLM involvement.
 * Batch-processed later by /doby update or Stop hook.
 *
 * Auto-detects project root by walking up from file_path to find .omc/ directory.
 */

import { readFileSync, appendFileSync, existsSync, mkdirSync } from "fs";
import { join, dirname } from "path";

/**
 * Walk up from a given path to find the project root by locating .omc/ directory.
 * @param {string} startPath - Starting path (file or directory)
 * @returns {string|null} - Project root path or null if not found
 */
function findProjectRoot(startPath) {
  let current = startPath;

  // If it's a file, start from its directory
  if (!current.endsWith("/") && !current.endsWith(".omc") && !current.endsWith(".omc/")) {
    current = dirname(current);
  }

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

let input;
try {
  input = JSON.parse(readFileSync("/dev/stdin", "utf8"));
} catch {
  process.exit(0);
}

const toolName = input.tool_name || "";
if (toolName !== "Write" && toolName !== "Edit") {
  process.exit(0);
}

const filePath = input.tool_params?.file_path || input.tool_params?.path || "";
if (!filePath) process.exit(0);

// Auto-detect project root
const projectRoot = findProjectRoot(filePath);
if (!projectRoot) {
  process.exit(0);
}

const PLANS_DIR = join(projectRoot, ".omc/plans");
const STATE_DIR = join(projectRoot, ".omc/state");
const PENDING_FILE = join(STATE_DIR, "doby-pending.txt");
const CODEMAP_FILE = join(PLANS_DIR, "INDEX-codemap.md");

const relPath = filePath.startsWith(projectRoot)
  ? filePath.slice(projectRoot.length + 1)
  : filePath;

let shouldTrack = false;
let changeType = "";

// Check if it's a plan doc (but not INDEX files)
if (relPath.startsWith(".omc/plans/") && relPath.endsWith(".md")) {
  if (relPath.startsWith(".omc/plans/INDEX")) {
    process.exit(0);
  }
  shouldTrack = true;
  changeType = "plan";
}

// Check if it's a tracked code file
if (!shouldTrack && existsSync(CODEMAP_FILE)) {
  try {
    const codemap = readFileSync(CODEMAP_FILE, "utf8");
    if (codemap.includes(relPath)) {
      shouldTrack = true;
      changeType = "code";
    }
  } catch {
    // codemap not built yet
  }
}

if (!shouldTrack) process.exit(0);

if (!existsSync(STATE_DIR)) {
  mkdirSync(STATE_DIR, { recursive: true });
}

const timestamp = new Date().toISOString().slice(0, 19);
const line = `${timestamp}\t${changeType}\t${relPath}\n`;

if (existsSync(PENDING_FILE)) {
  const existing = readFileSync(PENDING_FILE, "utf8");
  if (existing.includes(relPath)) {
    process.exit(0);
  }
}

appendFileSync(PENDING_FILE, line);
process.exit(0);
