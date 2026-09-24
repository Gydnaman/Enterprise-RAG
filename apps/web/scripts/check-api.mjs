import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const webRoot = fileURLToPath(new URL('..', import.meta.url))
const temp = mkdtempSync(join(webRoot, '.openapi-check-'))
let exitCode = 0
try {
  const result = spawnSync('pnpm', ['exec', 'openapi-ts', '-f', 'openapi-ts.config.ts'], {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    env: { ...process.env, OPENAPI_OUTPUT_PATH: temp },
  })
  if (result.status !== 0) {
    exitCode = result.status ?? 1
  } else {
    const actual = readFileSync(resolve(temp, 'types.gen.ts'), 'utf8')
    const expected = readFileSync(resolve(webRoot, 'src/api/generated/types.gen.ts'), 'utf8')
    if (actual !== expected) {
      console.error('Generated API types differ from src/api/generated/types.gen.ts. Run pnpm api:generate and commit the result.')
      exitCode = 1
    } else {
      console.log('Generated API types match docs/api/openapi.json.')
    }
  }
} finally {
  rmSync(temp, { recursive: true, force: true })
}
process.exitCode = exitCode
