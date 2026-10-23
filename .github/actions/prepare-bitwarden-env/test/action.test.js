const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { createAction, SESSION_STATE } = require("../src/action");
const session = require("../src/session");

function fakeCore(inputs) {
  const state = new Map();
  const outputs = new Map();
  return {
    getInput: (name) => inputs[name] || "",
    getState: (name) => state.get(name) || "",
    saveState: (name, value) => state.set(name, value),
    setOutput: (name, value) => outputs.set(name, value),
    state,
    outputs,
  };
}

test("main prepares output and post removes it without another subprocess", () => {
  const runnerTemp = fs.mkdtempSync(path.join(os.tmpdir(), "runner-temp-"));
  try {
    const environment = { RUNNER_TEMP: runnerTemp, TOKEN: "machine-token" };
    const core = fakeCore({
      backend: "api",
      "org-id": "organization-id",
      "projects-json": "[]",
    });
    const calls = [];
    const action = createAction({
      core,
      spawnSync: (...args) => {
        calls.push(args);
        return { status: 0 };
      },
      session,
      actionDirectory: "/action",
      environment,
    });

    action.prepare();

    const sessionDirectory = core.state.get(SESSION_STATE);
    assert.equal(fs.existsSync(sessionDirectory), true);
    assert.equal(
      core.outputs.get("session-manifest"),
      path.join(sessionDirectory, "session.json"),
    );
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], "python");
    assert.equal(calls[0][1][0], "/action/scripts/prepare_session.py");
    assert.equal(calls[0][2].env.BTENV_SESSION_DIRECTORY, sessionDirectory);

    action.cleanup();

    assert.equal(fs.existsSync(sessionDirectory), false);
    assert.equal(calls.length, 1);
  } finally {
    fs.rmSync(runnerTemp, { recursive: true, force: true });
  }
});

test("failed preparation removes the partial session immediately", () => {
  const runnerTemp = fs.mkdtempSync(path.join(os.tmpdir(), "runner-temp-"));
  try {
    const environment = { RUNNER_TEMP: runnerTemp };
    const core = fakeCore({ backend: "api", "projects-json": "[]" });
    const action = createAction({
      core,
      spawnSync: () => ({ status: 17 }),
      session,
      actionDirectory: "/action",
      environment,
    });

    assert.throws(
      () => action.prepare(),
      /Bitwarden session preparation failed with exit code 17/,
    );
    assert.equal(fs.existsSync(core.state.get(SESSION_STATE)), false);
  } finally {
    fs.rmSync(runnerTemp, { recursive: true, force: true });
  }
});

test("post cleanup is a no-op when main fails before saving state", () => {
  const core = fakeCore({ backend: "api", "projects-json": "[]" });
  let createCalls = 0;
  let removeCalls = 0;
  let spawnCalls = 0;
  const action = createAction({
    core,
    spawnSync: () => {
      spawnCalls += 1;
      return { status: 0 };
    },
    session: {
      createSessionDirectory: () => {
        createCalls += 1;
        throw new Error("cannot create session directory");
      },
      removeSessionDirectory: () => {
        removeCalls += 1;
      },
    },
    actionDirectory: "/action",
    environment: {},
  });

  assert.throws(
    () => action.prepare(),
    /cannot create session directory/,
  );
  action.cleanup();

  assert.equal(core.state.has(SESSION_STATE), false);
  assert.equal(createCalls, 1);
  assert.equal(removeCalls, 0);
  assert.equal(spawnCalls, 0);
});
