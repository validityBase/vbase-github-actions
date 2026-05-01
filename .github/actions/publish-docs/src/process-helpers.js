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
Object.defineProperty(exports, "__esModule", { value: true });
exports.run = void 0;
const child_process = __importStar(require("node:child_process"));
const utils_1 = require("./utils");
function run(cmd, args, cwd) {
    var command = cmd + ' ' + args.join(' ');
    console.log(`Running command: ${command}`);
    return new Promise((resolve, reject) => {
        var options = {};
        if (cwd) {
            options.cwd = cwd;
        }
        let output = '';
        const process = child_process.spawn(cmd, args, options);
        process.stdout.on('data', (data) => {
            if (data) {
                console.log(`stdout: ${data}`);
                output += data;
            }
        });
        process.stderr.on('data', (data) => {
            if (data) {
                console.error(`stderr: ${data}`);
            }
        });
        process.on('close', (code) => {
            if (code !== 0) {
                reject(`Command [${command}] execution error. Exit code: ${code}`);
            }
            // wait for 5 seconds to flush the output
            (0, utils_1.wait)(5 * 1000).then(() => { resolve(output); });
        });
    });
}
exports.run = run;
