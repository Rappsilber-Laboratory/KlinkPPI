import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const pythonCommand = process.platform === 'win32'
  ? join(rootDir, '.venv', 'Scripts', 'python.exe')
  : join(rootDir, '.venv', 'bin', 'python');
const backendDir = join(rootDir, 'backend');
const frontendDir = join(rootDir, 'frontend');
const viteCli = join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js');
const frontendArgs = process.argv.slice(2);

if (!existsSync(pythonCommand)) {
  console.error('Backend virtual environment is missing. Run `npm install` or `npm run setup` first.');
  process.exit(1);
}

if (!existsSync(viteCli)) {
  console.error('Frontend dependencies are missing. Run `npm install` or `npm run setup` first.');
  process.exit(1);
}

const children = [];
let shuttingDown = false;

function prefixStream(stream, name) {
  const lines = createInterface({ input: stream });
  lines.on('line', (line) => {
    console.log(`[${name}] ${line}`);
  });
}

function start(name, command, args, cwd = rootDir) {
  const child = spawn(command, args, {
    cwd,
    env: process.env,
    shell: false,
    stdio: ['inherit', 'pipe', 'pipe'],
  });

  children.push(child);
  prefixStream(child.stdout, name);
  prefixStream(child.stderr, name);

  child.on('exit', (code, signal) => {
    if (shuttingDown) return;

    shuttingDown = true;
    stopChildren();
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

async function waitForBackend() {
  const healthUrl = 'http://127.0.0.1:8000/health';
  const timeoutMs = 120000;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    if (shuttingDown) return;

    try {
      const response = await fetch(healthUrl);
      if (response.ok) {
        return;
      }
    } catch {
      // Backend is still starting.
    }

    await new Promise(resolve => setTimeout(resolve, 500));
  }

  console.error('[dev] Backend did not become ready at http://127.0.0.1:8000/health within 2 minutes.');
  shuttingDown = true;
  stopChildren();
  process.exit(1);
}

function stopChildren() {
  for (const child of children) {
    if (!child.killed) {
      child.kill('SIGTERM');
    }
  }
}

process.on('SIGINT', () => {
  shuttingDown = true;
  stopChildren();
  process.exit(130);
});

process.on('SIGTERM', () => {
  shuttingDown = true;
  stopChildren();
  process.exit(143);
});

async function main() {
  start('backend', pythonCommand, [
    '-m',
    'uvicorn',
    'app.main:app',
    '--reload',
    '--host',
    '127.0.0.1',
    '--port',
    '8000',
  ], backendDir);

  await waitForBackend();

  if (!shuttingDown) {
    start('frontend', process.execPath, [
      viteCli,
      '--host',
      '127.0.0.1',
      ...frontendArgs,
    ], frontendDir);
  }
}

main();
