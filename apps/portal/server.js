const express = require('express');
const fs = require('fs');
const path = require('path');
const { marked } = require('marked');

const app = express();
const PORT = 3001;
const BRAIN_PATH = '/root/jarvis-workspace/brain';
const WORKSPACE_PATH = '/root/jarvis-workspace';

app.use(express.json());
app.use(express.static('public'));

// Get all documents
app.get('/api/documents', (req, res) => {
  const documents = [];
  const categories = ['concepts', 'journals', 'research', 'workflows'];
  
  for (const category of categories) {
    const categoryPath = path.join(BRAIN_PATH, category);
    if (fs.existsSync(categoryPath)) {
      const files = fs.readdirSync(categoryPath);
      for (const file of files) {
        if (file.endsWith('.md')) {
          const filePath = path.join(categoryPath, file);
          const stat = fs.statSync(filePath);
          const content = fs.readFileSync(filePath, 'utf-8');
          
          documents.push({
            path: category + '/' + file,
            name: file.replace('.md', '').replace(/-/g, ' '),
            category: category.charAt(0).toUpperCase() + category.slice(1),
            content,
            modified: stat.mtime.toISOString()
          });
        }
      }
    }
  }
  
  documents.sort((a, b) => new Date(b.modified) - new Date(a.modified));
  res.json(documents);
});

// Get single document
app.get('/api/documents/:category/:file', (req, res) => {
  const filePath = path.join(BRAIN_PATH, req.params.category, req.params.file + '.md');
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    res.json({ content, html: marked(content) });
  } else {
    res.status(404).json({ error: 'Document not found' });
  }
});

// Create/Update document
app.post('/api/documents/:category/:file', (req, res) => {
  const { content } = req.body;
  const categoryPath = path.join(BRAIN_PATH, req.params.category);
  
  if (!fs.existsSync(categoryPath)) {
    fs.mkdirSync(categoryPath, { recursive: true });
  }
  
  const filePath = path.join(categoryPath, req.params.file + '.md');
  fs.writeFileSync(filePath, content);
  res.json({ success: true, path: req.params.category + '/' + req.params.file });
});

// Delete document
app.delete('/api/documents/:category/:file', (req, res) => {
  const filePath = path.join(BRAIN_PATH, req.params.category, req.params.file + '.md');
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
    res.json({ success: true });
  } else {
    res.status(404).json({ error: 'Document not found' });
  }
});

// Get workspace files (MEMORY.md, CONSTITUTION.md, etc.)
app.get('/api/workspace', (req, res) => {
  const files = ['MEMORY.md', 'CONSTITUTION.md', 'ENGINEERING_COMMANDMENTS.md', 'AGENTS.md', 'SOUL.md', 'USER.md'];
  const docs = [];
  
  for (const file of files) {
    const filePath = path.join(WORKSPACE_PATH, file);
    if (fs.existsSync(filePath)) {
      const stat = fs.statSync(filePath);
      const content = fs.readFileSync(filePath, 'utf-8');
      docs.push({
        path: file,
        name: file.replace('.md', ''),
        content,
        modified: stat.mtime.toISOString()
      });
    }
  }
  
  res.json(docs);
});

// System status
app.get('/api/status', (req, res) => {
  const exec = require('child_process').execSync;
  
  try {
    const uptime = fs.readFileSync('/proc/uptime', 'utf-8').split(' ')[0];
    const meminfo = fs.readFileSync('/proc/meminfo', 'utf-8');
    const memTotal = parseInt(meminfo.match(/MemTotal:\s+(\d+)/)[1]) / 1024;
    const memAvail = parseInt(meminfo.match(/MemAvailable:\s+(\d+)/)[1]) / 1024;
    
    let services = {};
    try {
      services.plcCopilot = exec('systemctl is-active plc-copilot 2>/dev/null').toString().trim();
    } catch { services.plcCopilot = 'inactive'; }
    try {
      services.secondBrain = exec('systemctl is-active second-brain 2>/dev/null').toString().trim();
    } catch { services.secondBrain = 'inactive'; }
    try {
      services.docker = exec('docker ps --format "{{.Names}}" 2>/dev/null').toString().trim().split('\n').filter(Boolean);
    } catch { services.docker = []; }
    
    res.json({
      uptime: Math.floor(parseFloat(uptime) / 3600) + 'h',
      memory: {
        total: Math.round(memTotal) + 'MB',
        available: Math.round(memAvail) + 'MB',
        used: Math.round(((memTotal - memAvail) / memTotal) * 100) + '%'
      },
      services
    });
  } catch (error) {
    res.json({ error: error.message });
  }
});

// Main page
app.get('/', (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🧠 Jarvis Portal</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
  <style>
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0f0f17; }
    ::-webkit-scrollbar-thumb { background: #3d3d5c; border-radius: 4px; }
    ::selection { background: rgba(139, 92, 246, 0.3); }
    .prose h1 { font-size: 1.875rem; font-weight: 700; margin-top: 1.5rem; margin-bottom: 0.75rem; color: white; }
    .prose h2 { font-size: 1.5rem; font-weight: 600; margin-top: 1.25rem; margin-bottom: 0.5rem; color: #c4b5fd; }
    .prose h3 { font-size: 1.25rem; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; color: #a78bfa; }
    .prose p { margin-bottom: 0.75rem; line-height: 1.7; }
    .prose ul, .prose ol { margin-left: 1.5rem; margin-bottom: 0.75rem; }
    .prose li { margin-bottom: 0.25rem; }
    .prose code { background: #1e1e2e; padding: 0.15rem 0.35rem; border-radius: 4px; font-size: 0.85rem; color: #a6e3a1; }
    .prose pre { background: #1e1e2e; padding: 1rem; border-radius: 8px; overflow-x: auto; margin-bottom: 1rem; }
    .prose pre code { background: none; padding: 0; }
    .prose blockquote { border-left: 3px solid #8b5cf6; padding-left: 1rem; color: #9ca3af; font-style: italic; margin: 1rem 0; }
    .prose table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; font-size: 0.9rem; }
    .prose th, .prose td { border: 1px solid #374151; padding: 0.5rem; text-align: left; }
    .prose th { background: #1f2937; color: white; }
    .prose strong { color: white; }
    .prose a { color: #a78bfa; }
    .prose hr { border-color: #374151; margin: 1.5rem 0; }
    .tab-active { background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%); }
    .glow { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); }
    @keyframes pulse-glow { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    .status-active { animation: pulse-glow 2s infinite; }
  </style>
</head>
<body class="bg-[#0a0a0f] text-gray-300 min-h-screen">
  <div class="flex h-screen">
    <!-- Sidebar -->
    <div id="sidebar" class="w-64 bg-[#12121a] border-r border-gray-800/50 flex flex-col">
      <!-- Logo -->
      <div class="p-4 border-b border-gray-800/50">
        <h1 class="text-xl font-bold text-white flex items-center gap-2">
          <span class="text-2xl">🧠</span> Jarvis
        </h1>
        <p class="text-xs text-gray-500 mt-1">Second Brain Portal</p>
      </div>

      <!-- Navigation -->
      <nav class="p-2">
        <button onclick="setTab('documents')" id="tab-documents" class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-800/50 tab-active text-white mb-1">
          📄 Documents
        </button>
        <button onclick="setTab('workspace')" id="tab-workspace" class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-800/50 text-gray-400 mb-1">
          ⚙️ Workspace
        </button>
        <button onclick="setTab('status')" id="tab-status" class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-800/50 text-gray-400 mb-1">
          📊 Status
        </button>
      </nav>

      <!-- Search -->
      <div class="p-2">
        <input type="text" id="search" placeholder="Search..." 
          class="w-full bg-gray-900/50 border border-gray-800 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-purple-500/50">
      </div>

      <!-- Document List -->
      <div id="docList" class="flex-1 overflow-y-auto p-2"></div>

      <!-- Footer -->
      <div class="p-3 border-t border-gray-800/50 text-xs text-gray-600">
        <span id="docCount">0</span> docs • <span id="lastRefresh">--</span>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col">
      <!-- Top Bar -->
      <div class="h-12 border-b border-gray-800/50 flex items-center justify-between px-4 bg-[#12121a]/50">
        <div class="flex items-center gap-2">
          <span id="currentIcon" class="text-purple-400">📄</span>
          <span id="currentDoc" class="font-medium text-white text-sm">Select a document</span>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="toggleEdit()" id="editBtn" class="px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 rounded-lg hidden">
            ✏️ Edit
          </button>
          <button onclick="newDoc()" class="px-3 py-1 text-xs bg-purple-600 hover:bg-purple-500 rounded-lg text-white">
            + New
          </button>
        </div>
      </div>

      <!-- Content Area -->
      <div id="content" class="flex-1 overflow-y-auto p-6">
        <div class="max-w-4xl mx-auto prose"></div>
      </div>

      <!-- Editor (hidden by default) -->
      <div id="editor" class="flex-1 overflow-hidden hidden flex flex-col">
        <textarea id="editorArea" class="flex-1 bg-[#0a0a0f] p-6 text-gray-300 font-mono text-sm resize-none focus:outline-none"></textarea>
        <div class="p-3 border-t border-gray-800/50 flex justify-end gap-2 bg-[#12121a]">
          <button onclick="cancelEdit()" class="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg">Cancel</button>
          <button onclick="saveDoc()" class="px-4 py-2 text-sm bg-purple-600 hover:bg-purple-500 rounded-lg text-white">Save</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let documents = [];
    let workspaceFiles = [];
    let currentDoc = null;
    let currentTab = 'documents';
    let isEditing = false;

    async function loadDocuments() {
      const res = await fetch('/api/documents');
      documents = await res.json();
      if (currentTab === 'documents') renderDocList();
      document.getElementById('docCount').textContent = documents.length;
      document.getElementById('lastRefresh').textContent = new Date().toLocaleTimeString();
    }

    async function loadWorkspace() {
      const res = await fetch('/api/workspace');
      workspaceFiles = await res.json();
      if (currentTab === 'workspace') renderWorkspaceList();
    }

    async function loadStatus() {
      const res = await fetch('/api/status');
      const status = await res.json();
      
      const content = document.querySelector('#content .prose');
      content.innerHTML = \`
        <h1>📊 System Status</h1>
        <div class="grid grid-cols-2 gap-4 mt-6">
          <div class="bg-gray-900/50 p-4 rounded-xl border border-gray-800/50">
            <div class="text-xs text-gray-500 mb-1">Uptime</div>
            <div class="text-2xl font-bold text-white">\${status.uptime || 'N/A'}</div>
          </div>
          <div class="bg-gray-900/50 p-4 rounded-xl border border-gray-800/50">
            <div class="text-xs text-gray-500 mb-1">Memory</div>
            <div class="text-2xl font-bold text-white">\${status.memory?.used || 'N/A'}</div>
            <div class="text-xs text-gray-500">\${status.memory?.available || ''} available</div>
          </div>
        </div>
        <h2 class="mt-6">Services</h2>
        <div class="space-y-2 mt-4">
          <div class="flex items-center justify-between bg-gray-900/50 p-3 rounded-lg border border-gray-800/50">
            <span>PLC Copilot</span>
            <span class="\${status.services?.plcCopilot === 'active' ? 'text-green-400' : 'text-red-400'}">\${status.services?.plcCopilot || 'unknown'}</span>
          </div>
          <div class="flex items-center justify-between bg-gray-900/50 p-3 rounded-lg border border-gray-800/50">
            <span>Second Brain</span>
            <span class="\${status.services?.secondBrain === 'active' ? 'text-green-400' : 'text-red-400'}">\${status.services?.secondBrain || 'unknown'}</span>
          </div>
          <div class="flex items-center justify-between bg-gray-900/50 p-3 rounded-lg border border-gray-800/50">
            <span>Docker Containers</span>
            <span class="text-blue-400">\${status.services?.docker?.length || 0} running</span>
          </div>
        </div>
        <h2 class="mt-6">Docker</h2>
        <ul class="mt-2">
          \${(status.services?.docker || []).map(c => '<li class="text-green-400">✓ ' + c + '</li>').join('') || '<li class="text-gray-500">No containers</li>'}
        </ul>
      \`;
    }

    function renderDocList(filter = '') {
      const filtered = documents.filter(d => 
        d.name.toLowerCase().includes(filter.toLowerCase()) ||
        d.content.toLowerCase().includes(filter.toLowerCase())
      );
      
      const categories = [...new Set(filtered.map(d => d.category))];
      let html = '';
      
      for (const cat of categories) {
        html += '<div class="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-2 py-1 mt-2">' + cat + '</div>';
        filtered.filter(d => d.category === cat).forEach(doc => {
          const active = currentDoc?.path === doc.path ? 'bg-purple-600/20 border-l-2 border-purple-500' : 'hover:bg-gray-800/50';
          const date = new Date(doc.modified).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          html += '<button onclick="selectDoc(\\'' + doc.path + '\\')" class="w-full text-left px-2 py-1.5 text-sm rounded-r ' + active + '">' +
            '<div class="font-medium text-gray-200 truncate text-xs">' + doc.name.charAt(0).toUpperCase() + doc.name.slice(1) + '</div>' +
            '</button>';
        });
      }
      
      document.getElementById('docList').innerHTML = html;
    }

    function renderWorkspaceList() {
      let html = '<div class="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-2 py-1 mt-2">Core Files</div>';
      
      workspaceFiles.forEach(doc => {
        const active = currentDoc?.path === doc.path ? 'bg-purple-600/20 border-l-2 border-purple-500' : 'hover:bg-gray-800/50';
        html += '<button onclick="selectWorkspaceFile(\\'' + doc.path + '\\')" class="w-full text-left px-2 py-1.5 text-sm rounded-r ' + active + '">' +
          '<div class="font-medium text-gray-200 truncate text-xs">' + doc.name + '</div>' +
          '</button>';
      });
      
      document.getElementById('docList').innerHTML = html;
    }

    async function selectDoc(docPath) {
      currentDoc = documents.find(d => d.path === docPath);
      if (!currentDoc) return;
      
      document.getElementById('currentDoc').textContent = currentDoc.name.charAt(0).toUpperCase() + currentDoc.name.slice(1);
      document.getElementById('editBtn').classList.remove('hidden');
      
      const [cat, file] = docPath.split('/');
      const res = await fetch('/api/documents/' + cat + '/' + file.replace('.md', ''));
      const data = await res.json();
      
      document.querySelector('#content .prose').innerHTML = data.html;
      hljs.highlightAll();
      renderDocList(document.getElementById('search').value);
      
      if (isEditing) cancelEdit();
    }

    function selectWorkspaceFile(path) {
      currentDoc = workspaceFiles.find(d => d.path === path);
      if (!currentDoc) return;
      
      document.getElementById('currentDoc').textContent = currentDoc.name;
      document.getElementById('editBtn').classList.add('hidden'); // Don't allow editing core files from here
      
      const html = marked.parse(currentDoc.content);
      document.querySelector('#content .prose').innerHTML = html;
      hljs.highlightAll();
      renderWorkspaceList();
    }

    function setTab(tab) {
      currentTab = tab;
      currentDoc = null;
      
      // Update tab styles
      document.querySelectorAll('[id^="tab-"]').forEach(el => {
        el.classList.remove('tab-active', 'text-white');
        el.classList.add('text-gray-400');
      });
      document.getElementById('tab-' + tab).classList.add('tab-active', 'text-white');
      document.getElementById('tab-' + tab).classList.remove('text-gray-400');
      
      // Reset view
      document.getElementById('editBtn').classList.add('hidden');
      document.getElementById('currentDoc').textContent = 'Select a document';
      document.querySelector('#content .prose').innerHTML = '';
      
      if (tab === 'documents') {
        renderDocList();
      } else if (tab === 'workspace') {
        loadWorkspace();
        renderWorkspaceList();
      } else if (tab === 'status') {
        document.getElementById('docList').innerHTML = '';
        loadStatus();
      }
    }

    function toggleEdit() {
      if (!currentDoc) return;
      isEditing = true;
      document.getElementById('content').classList.add('hidden');
      document.getElementById('editor').classList.remove('hidden');
      document.getElementById('editorArea').value = currentDoc.content;
      document.getElementById('editBtn').textContent = '👁️ Preview';
    }

    function cancelEdit() {
      isEditing = false;
      document.getElementById('content').classList.remove('hidden');
      document.getElementById('editor').classList.add('hidden');
      document.getElementById('editBtn').textContent = '✏️ Edit';
    }

    async function saveDoc() {
      if (!currentDoc) return;
      const content = document.getElementById('editorArea').value;
      const [cat, file] = currentDoc.path.split('/');
      
      await fetch('/api/documents/' + cat + '/' + file.replace('.md', ''), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
      });
      
      currentDoc.content = content;
      cancelEdit();
      await loadDocuments();
      selectDoc(currentDoc.path);
    }

    function newDoc() {
      const name = prompt('Document name (e.g., my-notes):');
      if (!name) return;
      
      const category = prompt('Category (concepts, journals, research, workflows):', 'concepts');
      if (!category) return;
      
      const path = category + '/' + name.toLowerCase().replace(/\\s+/g, '-');
      currentDoc = { path: path + '.md', name, category, content: '# ' + name + '\\n\\nWrite your content here...' };
      
      document.getElementById('currentDoc').textContent = name;
      document.getElementById('editBtn').classList.remove('hidden');
      toggleEdit();
    }

    // Marked configuration
    marked.setOptions({ breaks: true, gfm: true });

    document.getElementById('search').addEventListener('input', (e) => {
      if (currentTab === 'documents') renderDocList(e.target.value);
    });

    // Initial load
    loadDocuments();
    setInterval(loadDocuments, 30000);
  </script>
</body>
</html>`);
});

app.listen(PORT, '0.0.0.0', () => {
  console.log('🧠 Jarvis Portal running at http://localhost:' + PORT);
});
