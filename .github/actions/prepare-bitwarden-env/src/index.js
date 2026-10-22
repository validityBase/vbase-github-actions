const childProcess = require("node:child_process");
const path = require("node:path");
const core = require("@actions/core");
const {
  createSessionDirectory,
  removeSessionDirectory,
} = require("./session");

const SESSION_STATE = "session-directory";

function cleanup() {
  const sessionDirectory = core.getState(SESSION_STATE);
  if (sessionDirectory) {
    removeSessionDirectory(sessionDirectory);
  }
}

function prepare() {
  const sessionDirectory = createSessionDirectory();
  core.saveState(SESSION_STATE, sessionDirectory);

  const manifestPath = path.join(sessionDirectory, "session.json");
  const helper = path.join(__dirname, "..", "scripts", "prepare_session.py");
  const result = childProcess.spawnSync("python", [helper], {
    env: {
      ...process.env,
      BTENV_BACKEND: core.getInput("backend", { required: true }),
      BTENV_ORG_ID: core.getInput("org-id"),
      BTENV_PROJECTS_JSON: core.getInput("projects-json", { required: true }),
      BTENV_SESSION_DIRECTORY: sessionDirectory,
      BTENV_SESSION_MANIFEST: manifestPath,
    },
    stdio: "inherit",
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`Bitwarden session preparation failed with exit code ${result.status}`);
  }
  core.setOutput("session-manifest", manifestPath);
}

try {
  if (core.getState(SESSION_STATE)) {
    cleanup();
  } else {
    prepare();
  }
} catch (error) {
  core.setFailed(error instanceof Error ? error.message : String(error));
}
