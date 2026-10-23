const path = require("node:path");

const SESSION_STATE = "session-directory";

function createAction({ core, spawnSync, session, actionDirectory, environment }) {
  function cleanup() {
    const sessionDirectory = core.getState(SESSION_STATE);
    if (sessionDirectory) {
      session.removeSessionDirectory(sessionDirectory, environment);
    }
  }

  function prepare() {
    const sessionDirectory = session.createSessionDirectory(environment);
    core.saveState(SESSION_STATE, sessionDirectory);

    const manifestPath = path.join(sessionDirectory, "session.json");
    const helper = path.join(actionDirectory, "scripts", "prepare_session.py");
    try {
      const result = spawnSync("python", [helper], {
        env: {
          ...environment,
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
        throw new Error(
          `Bitwarden session preparation failed with exit code ${result.status}`,
        );
      }
      core.setOutput("session-manifest", manifestPath);
    } catch (error) {
      session.removeSessionDirectory(sessionDirectory, environment);
      throw error;
    }
  }

  return { cleanup, prepare };
}

module.exports = { createAction, SESSION_STATE };
