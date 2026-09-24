import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const here = fileURLToPath(new URL('.', import.meta.url))

export default {
  input: resolve(here, '../../docs/api/openapi.json'),
  output: {
    path: process.env.OPENAPI_OUTPUT_PATH ?? resolve(here, 'src/api/generated'),
    tsConfigPath: resolve(here, 'tsconfig.json'),
  },
  plugins: ['@hey-api/typescript'],
}
