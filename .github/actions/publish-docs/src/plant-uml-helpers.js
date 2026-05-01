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
exports.replacePlantUmlDiagramsInFile = void 0;
const fs = __importStar(require("fs"));
const plantuml_encoder_1 = __importDefault(require("plantuml-encoder"));
function replacePlantUmlDiagramsInFile(filePath) {
    return __awaiter(this, void 0, void 0, function* () {
        const content = fs.readFileSync(filePath, 'utf8');
        let lines = content.split('\n');
        let numberOfDiagrams = 0;
        let diagramStart = findDiagramStart(0, lines);
        while (diagramStart !== -1) {
            numberOfDiagrams++;
            const diagramOpeningTag = lines[diagramStart];
            const diagramEnd = findDiagramEnd(diagramStart + 1, lines);
            if (diagramEnd === -1) {
                throw new Error(`No closing \`\`\` found for PlantUml diagram ${diagramOpeningTag}`);
            }
            const diagramContent = lines
                .slice(diagramStart + 1, diagramEnd)
                .join('\n');
            // build diagram url
            const encodedPuml = plantuml_encoder_1.default.encode(diagramContent);
            let plantUmlUrl = `https://img.plantuml.biz/plantuml/png/${encodedPuml}`;
            lines = lines.slice(0, diagramStart)
                .concat([`![${getDiagramName(lines[diagramStart])}](${plantUmlUrl})`])
                .concat(lines.slice(diagramEnd + 1));
            diagramStart = findDiagramStart(diagramStart, lines);
        }
        if (numberOfDiagrams > 0) {
            console.log(`Replaced ${numberOfDiagrams} PlantUml diagrams in ${filePath}`);
            fs.writeFileSync(filePath, lines.join('\n'));
        }
        else {
            console.log(`No PlantUml diagrams found in ${filePath}`);
        }
    });
}
exports.replacePlantUmlDiagramsInFile = replacePlantUmlDiagramsInFile;
function findDiagramStart(startFrom, lines) {
    const diagramStartPattern = /```plantuml/g;
    for (let i = 0; i < lines.length; i++) {
        if (diagramStartPattern.test(lines[i])) {
            return i;
        }
    }
    return -1;
}
function findDiagramEnd(startFrom, lines) {
    const diagramEndPattern = /```/g;
    for (let i = startFrom + 1; i < lines.length; i++) {
        if (diagramEndPattern.test(lines[i])) {
            return i;
        }
    }
    return -1;
}
function getDiagramName(openDiagramTag) {
    var groups = /(\()(.+)(\))/g.exec(openDiagramTag);
    if (groups && groups.length > 3) {
        return groups[2];
    }
    return 'Diagram';
}
