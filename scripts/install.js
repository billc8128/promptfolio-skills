#!/usr/bin/env node

import { chmodSync, cpSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const HOME = homedir();
const SOURCE_DIR = new URL("..", import.meta.url).pathname;
const SKILLS = ["promptfolio-summarize", "promptfolio-search", "promptfolio-logout"];
const AUTH_HELPER_SRC = join(SOURCE_DIR, "promptfolio-summarize", "device-auth.sh");
const AUTH_HELPER_DEST = join(HOME, ".promptfolio", "device-auth.sh");

const skillTargets = [
  { label: "Claude Code", root: join(HOME, ".claude"), dir: join(HOME, ".claude", "skills") },
  { label: "Cursor", root: join(HOME, ".cursor"), dir: join(HOME, ".cursor", "skills") },
  { label: "Codex", root: join(HOME, ".codex"), dir: join(HOME, ".codex", "skills") },
  { label: "OpenClaw", root: join(HOME, ".openclaw"), dir: join(HOME, ".openclaw", "skills") },
];

function installSkillPack(targetDir) {
  for (const skill of SKILLS) {
    const src = join(SOURCE_DIR, skill);
    const dest = join(targetDir, skill);

    if (!existsSync(src)) {
      console.warn(`Skill source not found: ${src}`);
      continue;
    }

    mkdirSync(dest, { recursive: true });
    cpSync(src, dest, { recursive: true, force: true });
    console.log(`Installed skill: ${skill} -> ${dest}`);
  }
}

function installAntigravityWorkflows() {
  const antigravityRoot = join(HOME, ".gemini", "antigravity");
  const antigravityDetected =
    existsSync(antigravityRoot) ||
    existsSync(join(HOME, "Library", "Application Support", "Antigravity"));

  if (!antigravityDetected) {
    return false;
  }

  const workflowDir = join(antigravityRoot, "global_workflows");
  mkdirSync(workflowDir, { recursive: true });

  cpSync(
    join(SOURCE_DIR, "promptfolio-summarize", "SKILL.md"),
    join(workflowDir, "promptfolio-summarize.md"),
    { force: true },
  );
  cpSync(
    join(SOURCE_DIR, "promptfolio-summarize", "analysis-prompt.md"),
    join(workflowDir, "analysis-prompt.md"),
    { force: true },
  );
  cpSync(
    join(SOURCE_DIR, "promptfolio-search", "SKILL.md"),
    join(workflowDir, "promptfolio-search.md"),
    { force: true },
  );
  cpSync(
    join(SOURCE_DIR, "promptfolio-logout", "SKILL.md"),
    join(workflowDir, "promptfolio-logout.md"),
    { force: true },
  );

  console.log(`Installed workflows: Antigravity -> ${workflowDir}`);
  return true;
}

function installAuthHelper() {
  if (!existsSync(AUTH_HELPER_SRC)) {
    console.warn(`Auth helper source not found: ${AUTH_HELPER_SRC}`);
    return;
  }

  mkdirSync(join(HOME, ".promptfolio"), { recursive: true });
  cpSync(AUTH_HELPER_SRC, AUTH_HELPER_DEST, { force: true });
  chmodSync(AUTH_HELPER_DEST, 0o755);
  console.log(`Installed auth helper -> ${AUTH_HELPER_DEST}`);
}

let installedAny = false;
installAuthHelper();
for (const target of skillTargets) {
  if (!existsSync(target.root)) {
    continue;
  }
  installSkillPack(target.dir);
  installedAny = true;
}

if (installAntigravityWorkflows()) {
  installedAny = true;
}

if (!installedAny) {
  // Fallback for first-time setup: install to common default locations.
  for (const target of skillTargets) {
    installSkillPack(target.dir);
  }
  installAntigravityWorkflows();
}

console.log(
  "\npromptfolio installed for Claude/Cursor/Codex/OpenClaw (and Antigravity workflows when detected). Run /promptfolio-summarize in Claude/Cursor/Codex/OpenClaw. For Antigravity, open ~/.gemini/antigravity/global_workflows/promptfolio-summarize.md.",
);
