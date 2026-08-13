"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.commitAndPushDocsRepository = exports.cloneDocsRepository = void 0;
const core = __importStar(require("@actions/core"));
const process_helpers_1 = require("./process-helpers");
const constants_1 = require("./constants");
const docsRepoAccessToken = core.getInput('docs-repo-access-token');
const docsRepository = core.getInput('target-repository');
const env = process.env;
const maxPushAttempts = 3;
let targetBranch = core.getInput('target-repository-branch');
if (!targetBranch) {
    console.log('No target-repository-branch provided. We will use the current product branch name.');
    targetBranch = env.GITHUB_REF_NAME;
}
function cloneDocsRepository() {
    return __awaiter(this, void 0, void 0, function* () {
        console.log(`Cloning the docs repository: "${docsRepository}"...`);
        yield (0, process_helpers_1.run)("git", ["clone", "-b", getTargetBranch(), `https://${docsRepoAccessToken}@github.com/${docsRepository}.git`, constants_1.Constants.MainDocsDirectory], null);
        console.log('Cloning the docs repository done.');
    });
}
exports.cloneDocsRepository = cloneDocsRepository;
function commitAndPushDocsRepository(productDocsSubDirectory) {
    return __awaiter(this, void 0, void 0, function* () {
        console.log('Committing and pushing the changes to the docs repository...');
        yield (0, process_helpers_1.run)("git", ["config", "user.name", "github-actions[bot]"], constants_1.Constants.MainDocsDirectory);
        yield (0, process_helpers_1.run)("git", ["config", "user.email", "github-actions[bot]@users.noreply.github.com"], constants_1.Constants.MainDocsDirectory);
        yield (0, process_helpers_1.run)("git", ["add", productDocsSubDirectory], constants_1.Constants.MainDocsDirectory);
        yield (0, process_helpers_1.run)("git", ["diff-index", "--quiet", "HEAD"], constants_1.Constants.MainDocsDirectory)
            .then(() => {
            // no changes
            console.log('No changes in the docs repository.');
        })
            .catch(() => __awaiter(this, void 0, void 0, function* () {
            // there are changes
            console.log('Committing the changes to the docs repository...');
            var currentRepo = env.GITHUB_REPOSITORY.split('/')[1];
            yield (0, process_helpers_1.run)("git", ["commit", "-m", `Update ${currentRepo} documentation from automated build`], constants_1.Constants.MainDocsDirectory);
            yield pushDocsRepository();
            console.log('Committing the changes to the docs repository done.');
        }));
    });
}
exports.commitAndPushDocsRepository = commitAndPushDocsRepository;
function pushDocsRepository() {
    return __awaiter(this, void 0, void 0, function* () {
        const targetBranch = getTargetBranch();
        for (let attempt = 1; attempt <= maxPushAttempts; attempt++) {
            try {
                yield (0, process_helpers_1.run)("git", ["push", "origin", targetBranch], constants_1.Constants.MainDocsDirectory);
                return;
            }
            catch (error) {
                if (attempt === maxPushAttempts) {
                    throw error;
                }
                const remoteBranchState = yield getRemoteBranchState(targetBranch, error);
                if (remoteBranchState === 'already-pushed') {
                    console.log(`The push may have succeeded before the connection was closed. ${targetBranch} already contains the local commit.`);
                    return;
                }
                if (remoteBranchState === 'unchanged') {
                    throw error;
                }
                console.log(`Push attempt ${attempt} found new commits on ${targetBranch}. Rebasing before retrying...`);
                yield (0, process_helpers_1.run)("git", ["rebase", `origin/${targetBranch}`], constants_1.Constants.MainDocsDirectory);
            }
        }
    });
}
function getRemoteBranchState(targetBranch, pushError) {
    return __awaiter(this, void 0, void 0, function* () {
        try {
            yield (0, process_helpers_1.run)("git", ["fetch", "origin", targetBranch], constants_1.Constants.MainDocsDirectory);
            const revisionCounts = (yield (0, process_helpers_1.run)("git", ["rev-list", "--left-right", "--count", `HEAD...origin/${targetBranch}`], constants_1.Constants.MainDocsDirectory))
                .trim()
                .split(/\s+/)
                .map(Number);
            if (revisionCounts.length !== 2 || revisionCounts.some(Number.isNaN)) {
                throw new Error(`Unexpected revision count output: ${revisionCounts.join(' ')}`);
            }
            const [localOnlyCommits, remoteOnlyCommits] = revisionCounts;
            if (remoteOnlyCommits > 0) {
                return 'advanced';
            }
            if (localOnlyCommits === 0) {
                return 'already-pushed';
            }
            return 'unchanged';
        }
        catch (_a) {
            console.log('Unable to inspect the remote branch after the push failed. Re-throwing the original push error.');
            throw pushError;
        }
    });
}
function getTargetBranch() {
    let targetBranch = core.getInput('target-repository-branch');
    if (!targetBranch) {
        targetBranch = env.GITHUB_REF_NAME;
        console.log(`No target-repository-branch provided. We will use the current product branch name - ${targetBranch}.`);
    }
    return targetBranch;
}
