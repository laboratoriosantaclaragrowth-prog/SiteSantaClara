import { copyFileSync, existsSync, mkdirSync, readdirSync, realpathSync, rmSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = realpathSync.native(fileURLToPath(new URL('../', import.meta.url)));
const output = join(root, '.vercel-static');
const publicFiles = [
  'index.html', 'logo.png', 'hero.png', 'santa-clara.css', 'informational.js',
  'site-config.js', 'robots.txt', 'sitemap.xml', 'llms.txt',
];
const publicSections = ['blog', 'contato', 'exames', 'santa-clara-ate-voce'];
const assetExtensions = new Set([
  '.css', '.js', '.avif', '.gif', '.ico', '.jpeg', '.jpg', '.png', '.svg',
  '.webp', '.otf', '.ttf', '.woff', '.woff2',
]);

function copyPublicFile(path) {
  const destination = join(output, path);
  mkdirSync(dirname(destination), { recursive: true });
  copyFileSync(join(root, path), destination);
}

function copyPublicTree(directory, includeFile) {
  for (const entry of readdirSync(join(root, directory), { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) copyPublicTree(path, includeFile);
    if (entry.isFile() && includeFile(entry.name)) copyPublicFile(path);
  }
}

if (existsSync(output)) {
  if (realpathSync.native(output) !== output) {
    throw new Error(`Unexpected Vercel output path: ${output}`);
  }
  rmSync(output, { recursive: true });
}
for (const file of publicFiles) copyPublicFile(file);
for (const section of publicSections) copyPublicTree(section, name => name.endsWith('.html'));
copyPublicTree('assets', name => assetExtensions.has(extname(name).toLowerCase()));
