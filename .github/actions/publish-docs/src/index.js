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
const path_1 = __importDefault(require("path"));
const core = __importStar(require("@actions/core"));
const link_helper_1 = require("./link-helper");
const git_helpers_1 = require("./git-helpers");
const md_helpers_1 = require("./md-helpers");
const constants_1 = require("./constants");
const plant_uml_helpers_1 = require("./plant-uml-helpers");
console.log('Publishing user documentation to the central docs repository...');
(0, git_helpers_1.cloneDocsRepository)()
    .then(() => {
    return (0, md_helpers_1.copyDocs)();
})
    // replace PlantUml diagrams with images
    .then((prodDocsDirectoryInTheMainDocs) => {
    if (core.getInput('preprocess-plant-uml') === 'true') {
        return (0, md_helpers_1.preprocessMdsInDirectory)(path_1.default.join(constants_1.Constants.MainDocsDirectory, prodDocsDirectoryInTheMainDocs), plant_uml_helpers_1.replacePlantUmlDiagramsInFile)
            .then(() => prodDocsDirectoryInTheMainDocs);
    }
    else {
        return prodDocsDirectoryInTheMainDocs;
    }
})
    // replace absolute links to the GitHub repositories with relative links
    // the relatives links are only valid within the central docs repository
    .then((prodDocsDirectoryInTheMainDocs) => {
    if (core.getInput('resolve-absolute-links-repos')) {
        return (0, md_helpers_1.preprocessMdsInDirectory)(path_1.default.join(constants_1.Constants.MainDocsDirectory, prodDocsDirectoryInTheMainDocs), (mdFile) => __awaiter(void 0, void 0, void 0, function* () { return yield (0, link_helper_1.replaceAbsoluteGitLinksInFile)(mdFile, core.getInput('resolve-absolute-links-repos')); }))
            .then(() => prodDocsDirectoryInTheMainDocs);
    }
    else {
        return prodDocsDirectoryInTheMainDocs;
    }
})
    .then((prodDocsDirectoryInTheMainDocs) => {
    return (0, git_helpers_1.commitAndPushDocsRepository)(prodDocsDirectoryInTheMainDocs);
})
    .then(() => {
    console.log('Publishing user documentation is done.');
});
