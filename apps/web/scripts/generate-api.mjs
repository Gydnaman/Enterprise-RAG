import { spawnSync } from 'node:child_process'

const result = spawnSync('pnpm', ['exec', 'openapi-ts', '-f', 'openapi-ts.config.ts'], {
  stdio: 'inherit',
  shell: process.platform === 'win32',
})
process.exit(result.status ?? 1)
