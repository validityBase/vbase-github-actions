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
exports.replaceAbsoluteGitLinksInFile = void 0;
const fs = __importStar(require("fs"));
function replaceAbsoluteGitLinksInFile(filePath, reposToResolveStr) {
    return __awaiter(this, void 0, void 0, function* () {
        if (reposToResolveStr) {
            console.log(`Resolving absolute links pointing to \n ${reposToResolveStr}...`);
        }
        else {
            console.log('No repos to resolve provided. Skipping...');
            console.log('Please provide a list of repos to resolve in the action parameter resolve-absolute-links-repos');
            return;
        }
        console.log(`Resolving absolute links in ${filePath}...`);
        let content = fs.readFileSync(filePath, 'utf8');
        const linkRegex = /(?:https\:\/\/github\.com\/)([\w\-_]+)\/([\w\-_]+).*\/([\w\-_]+\.md)/gm;
        content = content.replace(linkRegex, (match, owner, repo, file) => {
            console.log(`Absolute link detected: ${match}`);
            console.log(`Owner: ${owner}, Repo: ${repo}, File: ${file}`);
            if (owner !== 'validityBase') {
                console.log(`Owner is not validityBase, skipping...`);
                return match;
            }
            if (!reposToResolveStr.includes(repo)) {
                console.log(`Repo ${repo} is not in the list of repos to resolve, skipping...`);
                return match;
            }
            const newLink = `../${repo}/${file}`;
            console.log(`Link replaced with ${newLink}`);
            return newLink;
        });
        fs.writeFileSync(filePath, content);
    });
}
exports.replaceAbsoluteGitLinksInFile = replaceAbsoluteGitLinksInFile;
