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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.preprocessMdsInDirectory = exports.copyDocs = void 0;
const core = __importStar(require("@actions/core"));
const constants_1 = require("./constants");
const fs = __importStar(require("fs"));
const path_1 = __importDefault(require("path"));
const env = process.env;
// copy the markdown files from the build directory to the docs repository
function copyDocs() {
    return __awaiter(this, void 0, void 0, function* () {
        let docsSubDirectory = core.getInput('target-docs-path');
        if (!docsSubDirectory) {
            console.log('No target-docs-path provided. We will use the current repository name as a docs sub-directory.');
            docsSubDirectory = env.GITHUB_REPOSITORY.split('/')[1];
        }
        const sourceDirectory = core.getInput('source-docs-path') + "/";
        const targetDirectory = `${constants_1.Constants.MainDocsDirectory}/${docsSubDirectory}`;
        console.log(`Copying the files from ${sourceDirectory} to ${targetDirectory}...`);
        if (fs.existsSync(targetDirectory)) {
            console.log(`The target directory ${targetDirectory} already exists. Deleting it...`);
            fs.rmSync(targetDirectory, { recursive: true });
        }
        fs.mkdirSync(targetDirectory);
        // copy all files recursively
        fs.cpSync(sourceDirectory, targetDirectory, { recursive: true, filter: (src) => {
                // we use this filter to log the files being copied
                console.log(`Copying ${src}`);
                return true; // copy all files
            } });
        return docsSubDirectory;
    });
}
exports.copyDocs = copyDocs;
function preprocessMdsInDirectory(directory, mdHandler) {
    return __awaiter(this, void 0, void 0, function* () {
        // iterate over all markdown files in the directory and preprocess them
        console.log(`Preprocessing markdown files in ${directory}...`);
        const files = getFiles(directory);
        for (let i = 0; i < files.length; i++) {
            if (path_1.default.extname(files[i]) !== '.md') {
                console.log(`Skipping ${files[i]}`);
                continue;
            }
            console.log(`Preprocessing ${files[i]}...`);
            yield mdHandler(files[i]);
        }
    });
}
exports.preprocessMdsInDirectory = preprocessMdsInDirectory;
function getFiles(dir) {
    const fsEntries = fs.readdirSync(dir, { withFileTypes: true });
    let res = [];
    for (let i = 0; i < fsEntries.length; i++) {
        if (fsEntries[i].isDirectory()) {
            res = res.concat(getFiles(path_1.default.join(dir, fsEntries[i].name)));
        }
        else {
            res = res.concat([path_1.default.join(dir, fsEntries[i].name)]);
        }
    }
    return res;
}
