const { contextBridge } = require('electron');

const backendUrlArg = process.argv.find((arg) => arg.startsWith('--sm-backend-url='));
const backendUrl = backendUrlArg
  ? backendUrlArg.slice('--sm-backend-url='.length)
  : 'http://127.0.0.1:8000';

contextBridge.exposeInMainWorld('desktopMeta', {
  backendUrl,
  apiBaseUrl: `${backendUrl}/api`,
  platform: process.platform,
  versions: {
    chrome: process.versions.chrome,
    electron: process.versions.electron,
    node: process.versions.node,
  },
});
