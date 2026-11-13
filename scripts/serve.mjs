// Production server: built web app at / and API at /api (see deploy/README.md).
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const python = process.platform === 'win32'
  ? join(rootDir, '.venv', 'Scripts', 'python.exe')
  : join(rootDir, '.venv', 'bin', 'python');
if (!existsSync(join(rootDir, 'frontend', 'dist', 'index.html'))) {
  console.error('frontend/dist is missing. Run `npm run build` first.');
  process.exit(1);
}
const port = process.env.PORT || '8000';
const host = process.env.HOST || '127.0.0.1';
const child = spawn(python, ['-m', 'uvicorn', 'app.server:application', '--host', host, '--port', port,
  '--workers', '1', '--proxy-headers', '--forwarded-allow-ips', process.env.FORWARDED_ALLOW_IPS || '127.0.0.1'],
  { cwd: join(rootDir, 'backend'), stdio: 'inherit' });
child.on('exit', code => process.exit(code ?? 0));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
