const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const SESSION_PREFIX = "vbase-btenv-";

function resolveRunnerTemp(environment = process.env) {
  return path.resolve(environment.RUNNER_TEMP || os.tmpdir());
}

function createSessionDirectory(environment = process.env) {
  const runnerTemp = resolveRunnerTemp(environment);
  fs.mkdirSync(runnerTemp, { recursive: true });
  const sessionDirectory = fs.mkdtempSync(path.join(runnerTemp, SESSION_PREFIX));
  fs.chmodSync(sessionDirectory, 0o700);
  return sessionDirectory;
}

function validateSessionDirectory(sessionDirectory, environment = process.env) {
  if (!sessionDirectory) {
    throw new Error("Bitwarden session directory state is empty");
  }
  const runnerTemp = resolveRunnerTemp(environment);
  const resolved = path.resolve(sessionDirectory);
  if (
    path.dirname(resolved) !== runnerTemp ||
    !path.basename(resolved).startsWith(SESSION_PREFIX)
  ) {
    throw new Error(`Refusing to remove unexpected session path: ${resolved}`);
  }
  return resolved;
}

function removeSessionDirectory(sessionDirectory, environment = process.env) {
  const validated = validateSessionDirectory(sessionDirectory, environment);
  fs.rmSync(validated, { recursive: true, force: true });
}

module.exports = {
  createSessionDirectory,
  removeSessionDirectory,
  resolveRunnerTemp,
  validateSessionDirectory,
};
