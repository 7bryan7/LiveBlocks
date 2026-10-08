import {existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const python=process.env.PYTHON_BIN || path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
if(!existsSync(python) && !process.env.PYTHON_BIN){console.error('Run npm run setup:python first, or set PYTHON_BIN to your Python environment.');process.exit(1);}
const mode=process.argv[2];
const args=mode==='test'?['-m','unittest','discover','-s','tests_python','-v']:mode==='inspect'?['-m','python_backend.inspect']:null;
if(!args)throw new Error('Expected test or inspect.');
const result=spawnSync(python,args,{cwd:root,stdio:'inherit',env:process.env});
if(result.error)throw result.error;
process.exit(result.status??1);
