const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  createSessionDirectory,
  removeSessionDirectory,
  validateSessionDirectory,
} = require("../src/session");

test("creates a private session directory and removes it", () => {
  const runnerTemp = fs.mkdtempSync(path.join(os.tmpdir(), "runner-temp-"));
  try {
    const environment = { RUNNER_TEMP: runnerTemp };
    const sessionDirectory = createSessionDirectory(environment);
    assert.equal(fs.statSync(sessionDirectory).mode & 0o777, 0o700);
    removeSessionDirectory(sessionDirectory, environment);
    assert.equal(fs.existsSync(sessionDirectory), false);
  } finally {
    fs.rmSync(runnerTemp, { recursive: true, force: true });
  }
});

test("refuses to remove paths outside the runner temp session namespace", () => {
  const runnerTemp = fs.mkdtempSync(path.join(os.tmpdir(), "runner-temp-"));
  try {
    assert.throws(
      () => validateSessionDirectory(path.join(runnerTemp, "unrelated"), { RUNNER_TEMP: runnerTemp }),
      /Refusing to remove unexpected session path/,
    );
    assert.throws(
      () => validateSessionDirectory(path.dirname(runnerTemp), { RUNNER_TEMP: runnerTemp }),
      /Refusing to remove unexpected session path/,
    );
  } finally {
    fs.rmSync(runnerTemp, { recursive: true, force: true });
  }
});
