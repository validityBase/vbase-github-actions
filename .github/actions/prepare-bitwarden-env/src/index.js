const childProcess = require("node:child_process");
const path = require("node:path");
const core = require("@actions/core");
const { createAction } = require("./action");
const session = require("./session");

const action = createAction({
  core,
  spawnSync: childProcess.spawnSync,
  session,
  actionDirectory: path.join(__dirname, ".."),
  environment: process.env,
});

try {
  action.prepare();
} catch (error) {
  core.setFailed(error instanceof Error ? error.message : String(error));
}
