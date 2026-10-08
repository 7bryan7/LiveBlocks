// Own both local processes so Ctrl+C/failure stops the whole application.
import {existsSync} from 'node:fs';
import {loadEnvFile} from 'node:process';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
for(const file of [path.join(root,'.env.local'),path.join(root,'.env'),path.join(root,'../.env')])if(existsSync(file))loadEnvFile(file);
const mode=process.argv[2];
if(!['dev','start'].includes(mode))throw new Error('Expected dev or start.');
const python=process.env.PYTHON_BIN || path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
if(!existsSync(python)&&!process.env.PYTHON_BIN){console.error('Run npm run setup:python first.');process.exit(1);}
const children=[];
let stopping=false;
function stop(code=0){if(stopping)return;stopping=true;for(const child of children)child.kill('SIGTERM');setTimeout(()=>{for(const child of children)child.kill('SIGKILL');process.exit(code);},1500).unref();process.exitCode=code;}
for(const [bin,args] of [[python,['-m','python_backend.local']],[process.execPath,[path.join(root,'node_modules/next/dist/bin/next'),mode,'--port','5173',...process.argv.slice(3)]]]){
 const child=spawn(bin,args,{cwd:root,stdio:'inherit',env:process.env});children.push(child);
 child.on('error',()=>{console.error('Unable to start local '+(bin===python?'Python backend':'Next.js frontend'));stop(1);});
 child.on('exit',code=>{if(!stopping)stop(code??1);});
}
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
