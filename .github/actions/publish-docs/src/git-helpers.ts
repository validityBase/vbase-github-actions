import * as core from '@actions/core';
import { run } from './process-helpers';
import { Constants } from './constants';

const docsRepoAccessToken = core.getInput('docs-repo-access-token');
const docsRepository = core.getInput('target-repository');
const env = process.env as any;
const maxPushAttempts = 3;

type RemoteBranchState = 'advanced' | 'already-pushed' | 'unchanged';

let targetBranch = core.getInput('target-repository-branch') as string;
            if(!targetBranch) {
                console.log('No target-repository-branch provided. We will use the current product branch name.');
                targetBranch = env.GITHUB_REF_NAME;
            }

export async function cloneDocsRepository(): Promise<void> {
    console.log(`Cloning the docs repository: "${docsRepository}"...`);
    await run("git", ["clone", "-b", getTargetBranch(), `https://${docsRepoAccessToken}@github.com/${docsRepository}.git`, Constants.MainDocsDirectory], null);
    console.log('Cloning the docs repository done.');
}

export async function commitAndPushDocsRepository(productDocsSubDirectory: string): Promise<void> {
    console.log('Committing and pushing the changes to the docs repository...');
    
    await run("git", ["config", "user.name", "github-actions[bot]"], Constants.MainDocsDirectory);
    await run("git", ["config", "user.email", "github-actions[bot]@users.noreply.github.com"], Constants.MainDocsDirectory);
    await run("git", ["add", productDocsSubDirectory], Constants.MainDocsDirectory);
    await run("git", ["diff-index", "--quiet", "HEAD"], Constants.MainDocsDirectory)
        .then(() => {
            // no changes
            console.log('No changes in the docs repository.');
        })
        .catch(async () => {
            // there are changes
            console.log('Committing the changes to the docs repository...');

            var currentRepo = env.GITHUB_REPOSITORY.split('/')[1];
            await run("git", ["commit", "-m", `Update ${currentRepo} documentation from automated build`], Constants.MainDocsDirectory);
            await pushDocsRepository();

            console.log('Committing the changes to the docs repository done.');
        });
}

async function pushDocsRepository(): Promise<void> {
    const targetBranch = getTargetBranch();

    for(let attempt = 1; attempt <= maxPushAttempts; attempt++) {
        try {
            await run("git", ["push", "origin", targetBranch], Constants.MainDocsDirectory);
            return;
        }
        catch(error) {
            if(attempt === maxPushAttempts) {
                throw error;
            }

            const remoteBranchState = await getRemoteBranchState(targetBranch, error);
            if(remoteBranchState === 'already-pushed') {
                console.log(`The push may have succeeded before the connection was closed. ${targetBranch} already contains the local commit.`);
                return;
            }

            if(remoteBranchState === 'unchanged') {
                throw error;
            }

            console.log(`Push attempt ${attempt} found new commits on ${targetBranch}. Rebasing before retrying...`);
            await run("git", ["rebase", `origin/${targetBranch}`], Constants.MainDocsDirectory);
        }
    }
}

async function getRemoteBranchState(targetBranch: string, pushError: unknown): Promise<RemoteBranchState> {
    try {
        await run("git", ["fetch", "origin", targetBranch], Constants.MainDocsDirectory);
        const revisionCounts = (await run(
            "git",
            ["rev-list", "--left-right", "--count", `HEAD...origin/${targetBranch}`],
            Constants.MainDocsDirectory))
            .trim()
            .split(/\s+/)
            .map(Number);

        if(revisionCounts.length !== 2 || revisionCounts.some(Number.isNaN)) {
            throw new Error(`Unexpected revision count output: ${revisionCounts.join(' ')}`);
        }

        const [localOnlyCommits, remoteOnlyCommits] = revisionCounts;
        if(remoteOnlyCommits > 0) {
            return 'advanced';
        }

        if(localOnlyCommits === 0) {
            return 'already-pushed';
        }

        return 'unchanged';
    }
    catch {
        console.log('Unable to inspect the remote branch after the push failed. Re-throwing the original push error.');
        throw pushError;
    }
}

function getTargetBranch(): string {
    let targetBranch = core.getInput('target-repository-branch') as string;
    if(!targetBranch) {
        targetBranch = env.GITHUB_REF_NAME;
        console.log(`No target-repository-branch provided. We will use the current product branch name - ${targetBranch}.`);
    }
    return targetBranch;
}
