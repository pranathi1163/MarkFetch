// State Management
let pdfDoc = null;
let currentPageNum = 1;
let zoomScale = 1.25;
let highlights = [];
let pagesMeta = {};
let activeHighlightId = null;
let pdfUrlPath = "";
let currentRenderTask = null;

// Configure PDF.js Worker
const pdfjsLib = window['pdfjs-dist/build/pdf'];
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

// DOM Elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const emptyState = document.getElementById('empty-state');
const highlightsList = document.getElementById('highlights-list');
const highlightCount = document.getElementById('highlight-count');
const viewerToolbar = document.getElementById('viewer-toolbar');
const pdfTitle = document.getElementById('pdf-title');
const pdfViewportContainer = document.getElementById('pdf-viewport-container');
const pdfCanvas = document.getElementById('pdf-canvas');
const highlightOverlayLayer = document.getElementById('highlight-overlay-layer');
const loadingOverlay = document.getElementById('loading-overlay');
const pdfContainerWrapper = document.getElementById('pdf-container-wrapper');

// Navigation Controls
const prevPageBtn = document.getElementById('prev-page-btn');
const nextPageBtn = document.getElementById('next-page-btn');
const currentPageNumSpan = document.getElementById('current-page-num');
const totalPagesCountSpan = document.getElementById('total-pages-count');
const zoomInBtn = document.getElementById('zoom-in-btn');
const zoomOutBtn = document.getElementById('zoom-out-btn');
const zoomLevelText = document.getElementById('zoom-level-text');

// Initialize event listeners
function init() {
  // Drag and Drop listeners
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());
  
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drop-active');
  });
  
  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drop-active');
  });
  
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drop-active');
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type === 'application/pdf') {
      handlePdfUpload(files[0]);
    } else {
      alert("Please drop a valid PDF file.");
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handlePdfUpload(e.target.files[0]);
    }
  });

  // Navigation listeners
  prevPageBtn.addEventListener('click', showPrevPage);
  nextPageBtn.addEventListener('click', showNextPage);
  zoomInBtn.addEventListener('click', zoomIn);
  zoomOutBtn.addEventListener('click', zoomOut);
}

// Upload & Process PDF
async function handlePdfUpload(file) {
  showLoading(true);
  
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Failed to process PDF");
    }
    
    const data = await response.json();
    
    // Store data in local state
    pdfUrlPath = data.pdf_url_path;
    highlights = data.highlights;
    pagesMeta = data.pages;
    currentPageNum = 1;
    activeHighlightId = null;
    
    pdfTitle.textContent = file.name;
    
    // Load PDF in frontend using PDF.js
    await loadPdfViewer(`/api/pdf/${pdfUrlPath}`);
    
    // Render the sidebar highlights
    renderSidebarHighlights();
    
  } catch (error) {
    console.error(error);
    alert(`Error: ${error.message}`);
    showLoading(false);
  }
}

// Load PDF Document
async function loadPdfViewer(url) {
  try {
    const loadingTask = pdfjsLib.getDocument(url);
    pdfDoc = await loadingTask.promise;
    
    totalPagesCountSpan.textContent = pdfDoc.numPages;
    viewerToolbar.style.display = 'flex';
    emptyState.style.display = 'none';
    highlightsList.style.display = 'flex';
    pdfViewportContainer.style.display = 'block';
    
    await renderPage(currentPageNum);
  } catch (error) {
    console.error("PDF loading error:", error);
    alert("Error loading PDF preview in viewer.");
  } finally {
    showLoading(false);
  }
}

// Render PDF Page
async function renderPage(pageNum) {
  if (!pdfDoc) return;
  
  // Cancel any ongoing rendering
  if (currentRenderTask) {
    currentRenderTask.cancel();
  }
  
  showLoading(true);
  currentPageNum = pageNum;
  currentPageNumSpan.textContent = pageNum;
  
  try {
    const page = await pdfDoc.getPage(pageNum);
    
    // Determine canvas dimensions according to zoomScale
    const viewport = page.getViewport({ scale: zoomScale });
    const ctx = pdfCanvas.getContext('2d');
    
    pdfCanvas.width = viewport.width;
    pdfCanvas.height = viewport.height;
    
    // Center the viewport container matching canvas size
    pdfViewportContainer.style.width = `${viewport.width}px`;
    pdfViewportContainer.style.height = `${viewport.height}px`;
    
    const renderContext = {
      canvasContext: ctx,
      viewport: viewport
    };
    
    currentRenderTask = page.render(renderContext);
    await currentRenderTask.promise;
    currentRenderTask = null;
    
    // Render highlight overlays on top
    renderHighlightOverlays(viewport, pageNum - 1);
    
  } catch (error) {
    if (error.name !== 'HeadingTaskCancelledException' && error.name !== 'RenderingCancelledException') {
      console.error("Rendering error:", error);
    }
  } finally {
    showLoading(false);
  }
}

// Render Highlights on Sidebar
function renderSidebarHighlights() {
  highlightsList.innerHTML = '';
  highlightCount.textContent = `${highlights.length} annotation${highlights.length === 1 ? '' : 's'}`;
  
  if (highlights.length === 0) {
    highlightsList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📝</div>
        <h3>No Highlights Found</h3>
        <p>There are no highlighted text sections in this PDF document.</p>
      </div>
    `;
    return;
  }
  
  // Group highlights by page_index
  const grouped = {};
  highlights.forEach(h => {
    if (!grouped[h.page_index]) {
      grouped[h.page_index] = [];
    }
    grouped[h.page_index].push(h);
  });
  
  // Create sidebar HTML — each highlight is collapsed by default
  Object.keys(grouped).sort((a, b) => a - b).forEach(pageIdx => {
    const pageNum = parseInt(pageIdx) + 1;
    const groupDiv = document.createElement('div');
    groupDiv.className = 'highlight-group';
    
    const groupTitle = document.createElement('div');
    groupTitle.className = 'page-group-title';
    groupTitle.textContent = `Page ${pageNum}`;
    groupDiv.appendChild(groupTitle);
    
    grouped[pageIdx].forEach((h, idx) => {
      const item = document.createElement('div');
      item.className = 'highlight-item';
      item.id = `sidebar-${h.id}`;
      
      // Compute RGB Color string
      const r = Math.round(h.color[0] * 255);
      const g = Math.round(h.color[1] * 255);
      const b = Math.round(h.color[2] * 255);
      const colorStr = `rgb(${r}, ${g}, ${b})`;
      
      item.style.setProperty('--highlight-color', colorStr);
      
      item.innerHTML = `
        <div class="highlight-header">
          <div class="highlight-header-left">
            <span class="color-dot"></span>
            <span class="highlight-label">Highlight ${idx + 1}</span>
          </div>
          <div class="highlight-header-right">
            <span class="highlight-page-badge">P${pageNum}</span>
            <span class="expand-arrow">▶</span>
          </div>
        </div>
        <div class="highlight-body" style="display: none;">
          <div class="highlight-text">"${h.text}"</div>
        </div>
      `;
      
      item.addEventListener('click', () => {
        const isExpanded = item.classList.contains('expanded');
        
        // Collapse all other items
        document.querySelectorAll('.highlight-item.expanded').forEach(other => {
          if (other !== item) {
            other.classList.remove('expanded');
            other.querySelector('.highlight-body').style.display = 'none';
            other.querySelector('.expand-arrow').textContent = '▶';
          }
        });
        
        if (isExpanded) {
          // Collapse this item
          item.classList.remove('expanded');
          item.querySelector('.highlight-body').style.display = 'none';
          item.querySelector('.expand-arrow').textContent = '▶';
        } else {
          // Expand this item and navigate
          item.classList.add('expanded');
          item.querySelector('.highlight-body').style.display = 'block';
          item.querySelector('.expand-arrow').textContent = '▼';
          activateHighlight(h.id, true);
        }
      });
      
      groupDiv.appendChild(item);
    });
    
    highlightsList.appendChild(groupDiv);
  });
}

// Render Bounding Box Highlight Overlays
function renderHighlightOverlays(viewport, pageIndex) {
  highlightOverlayLayer.innerHTML = '';
  
  // Filter highlights on this page
  const pageHighlights = highlights.filter(h => h.page_index === pageIndex);
  const meta = pagesMeta[pageIndex];
  
  if (!meta) return;
  
  const originalWidth = meta.width;
  const originalHeight = meta.height;
  
  // Compute scale ratio (since viewport incorporates rotation and scaling)
  // Standard scaling factors:
  const scaleX = viewport.width / originalWidth;
  const scaleY = viewport.height / originalHeight;
  
  pageHighlights.forEach(h => {
    const [x0, y0, x1, y1] = h.rect;
    
    const left = x0 * scaleX;
    const top = y0 * scaleY;
    const width = (x1 - x0) * scaleX;
    const height = (y1 - y0) * scaleY;
    
    const overlay = document.createElement('div');
    overlay.className = 'highlight-overlay-item';
    overlay.id = `overlay-${h.id}`;
    
    // Parse color
    const r = Math.round(h.color[0] * 255);
    const g = Math.round(h.color[1] * 255);
    const b = Math.round(h.color[2] * 255);
    
    overlay.style.left = `${left}px`;
    overlay.style.top = `${top}px`;
    overlay.style.width = `${width}px`;
    overlay.style.height = `${height}px`;
    
    // Set custom visual styles matching the color
    overlay.style.setProperty('--overlay-color', `rgba(${r}, ${g}, ${b}, 0.3)`);
    overlay.style.setProperty('--overlay-hover-color', `rgba(${r}, ${g}, ${b}, 0.5)`);
    overlay.style.setProperty('--overlay-glow', `rgb(${r}, ${g}, ${b})`);
    
    // Trigger highlight selection on click
    overlay.addEventListener('click', () => {
      activateHighlight(h.id, false);
    });
    
    highlightOverlayLayer.appendChild(overlay);
  });
  
  // If we navigated to a page because we clicked a highlight, activate the pulse effect
  if (activeHighlightId) {
    const activeOverlay = document.getElementById(`overlay-${activeHighlightId}`);
    if (activeOverlay) {
      activeOverlay.classList.add('active-pulse');
      setTimeout(() => {
        activeOverlay.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    }
  }
}

// Activate Highlight and Center View
async function activateHighlight(highlightId, triggerPageChange = true) {
  activeHighlightId = highlightId;
  
  // Find highlight data
  const highlight = highlights.find(h => h.id === highlightId);
  if (!highlight) return;
  
  // Handle sidebar active classes
  document.querySelectorAll('.highlight-item').forEach(item => {
    item.classList.remove('active');
  });
  const sidebarItem = document.getElementById(`sidebar-${highlightId}`);
  if (sidebarItem) {
    sidebarItem.classList.add('active');
    sidebarItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  
  const targetPageNum = highlight.page_index + 1;
  
  if (triggerPageChange && currentPageNum !== targetPageNum) {
    // Page is different, render first and then scroll
    await renderPage(targetPageNum);
  } else {
    // Already on the page, just clear previous active overlay pulse and set it on the new one
    document.querySelectorAll('.highlight-overlay-item').forEach(overlay => {
      overlay.classList.remove('active-pulse');
    });
    
    const activeOverlay = document.getElementById(`overlay-${highlightId}`);
    if (activeOverlay) {
      activeOverlay.classList.add('active-pulse');
      activeOverlay.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
}

// Navigation helpers
async function showPrevPage() {
  if (currentPageNum <= 1) return;
  await renderPage(currentPageNum - 1);
}

async function showNextPage() {
  if (!pdfDoc || currentPageNum >= pdfDoc.numPages) return;
  await renderPage(currentPageNum + 1);
}

async function zoomIn() {
  if (zoomScale >= 3.0) return;
  zoomScale += 0.25;
  zoomLevelText.textContent = `${Math.round(zoomScale * 100)}%`;
  await renderPage(currentPageNum);
}

async function zoomOut() {
  if (zoomScale <= 0.5) return;
  zoomScale -= 0.25;
  zoomLevelText.textContent = `${Math.round(zoomScale * 100)}%`;
  await renderPage(currentPageNum);
}

function showLoading(show) {
  loadingOverlay.style.display = show ? 'flex' : 'none';
}

// Initialize Application
document.addEventListener('DOMContentLoaded', init);
