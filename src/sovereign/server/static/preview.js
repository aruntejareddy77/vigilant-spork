/**
 * preview.js
 * Canvas-based document preview and bounding box renderer.
 * Air-gapped: zero external CDN dependencies.
 *
 * Implements spatial coordinate scaling for NormalizedDocument bounding boxes:
 *   [ymin, xmin, ymax, xmax] in [0.0, 1.0] -> pixel coordinates (x, y, w, h).
 */

/**
 * Coordinate mapping helper function.
 * Maps normalized [ymin, xmin, ymax, xmax] in [0.0, 1.0] to pixel dimensions.
 */
function computeBoxCoordinates(bbox, width, height) {
  if (!bbox || bbox.length < 4) {
    return { x: 0, y: 0, w: 0, h: 0 };
  }
  const [ymin, xmin, ymax, xmax] = bbox;
  const x = Math.round(xmin * width);
  const y = Math.round(ymin * height);
  const w = Math.round((xmax - xmin) * width);
  const h = Math.round((ymax - ymin) * height);
  return { x, y, w, h };
}

/**
 * Color coding rules:
 * - Printed text (conf >= 0.85): Green (#10B981)
 * - Handwritten text: Blue (#3B82F6)
 * - Low confidence / review required (< 0.85): Amber (#F59E0B)
 * - Drawing diff added: Vivid Green (#10B981)
 * - Drawing diff removed: Vivid Red (#EF4444)
 * - Drawing diff modified: Vivid Amber (#F59E0B)
 */
function getColorForRegion(region) {
  if (!region) return '#10B981';

  // Drawing diff status
  const diffStatus = region.diff_status || region.diff_type;
  if (diffStatus === 'added' || region.category === 'diff_added') {
    return '#10B981';
  }
  if (diffStatus === 'removed' || region.category === 'diff_removed') {
    return '#EF4444';
  }
  if (diffStatus === 'modified' || region.category === 'diff_modified') {
    return '#F59E0B';
  }

  // Confidence check (< 0.85 triggers amber review flag)
  const conf = region.confidence;
  if (conf !== undefined && conf !== null && typeof conf === 'number' && conf < 0.85) {
    return '#F59E0B';
  }

  // Modality: handwriting
  const modality = (region.modality || region.category || '').toLowerCase();
  if (modality === 'handwritten' || modality === 'handwriting' || region.is_handwritten) {
    return '#3B82F6';
  }

  // Default printed text
  return '#10B981';
}

class DocumentPreviewRenderer {
  constructor(canvasId = 'preview-canvas', imageId = 'preview-image') {
    this.canvas = typeof document !== 'undefined' ? document.getElementById(canvasId) : null;
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.image = typeof document !== 'undefined' ? document.getElementById(imageId) : null;

    this.documentData = null;
    this.currentPage = 1;
    this.totalPages = 1;
    this.selectedRegionId = null;
    this.zoomScale = 1.0;
    this.baseWidth = 800;
    this.baseHeight = 600;

    this.colors = {
      printed: '#10B981',
      handwriting: '#3B82F6',
      review: '#F59E0B',
      diffAdd: '#10B981',
      diffRem: '#EF4444',
      diffMod: '#F59E0B',
      highlight: '#EF4444',
      highlightFill: 'rgba(239, 68, 68, 0.25)',
      normalFill: 'rgba(255, 255, 255, 0.04)'
    };

    if (this.canvas) {
      this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
    }
  }

  setDocument(docData) {
    this.documentData = docData;
    this.currentPage = 1;
    this.selectedRegionId = null;

    if (docData) {
      if (docData.total_pages) {
        this.totalPages = docData.total_pages;
      } else if (docData.page_count) {
        this.totalPages = docData.page_count;
      } else if (docData.pages && Array.isArray(docData.pages)) {
        this.totalPages = docData.pages.length || 1;
      } else {
        this.totalPages = 1;
      }
    } else {
      this.totalPages = 1;
    }

    this.updatePageControls();
    this.renderPage(this.currentPage);
  }

  computeBoxCoordinates(bbox, width, height) {
    return computeBoxCoordinates(bbox, width, height);
  }

  getRegionsForPage(pageNumber) {
    if (!this.documentData) return [];

    // Format 1: NormalizedDocument with pages array
    if (this.documentData.pages && Array.isArray(this.documentData.pages)) {
      const page = this.documentData.pages.find(p => p.page_number === pageNumber);
      if (page) {
        let regions = [];
        if (page.regions) regions = regions.concat(page.regions);
        if (page.form_fields) {
          for (const f of page.form_fields) {
            regions.push({
              region_id: f.field_id || f.key,
              box_2d: f.box_2d,
              text: `${f.key}: ${f.value}`,
              confidence: f.confidence,
              modality: f.is_handwritten ? 'handwritten' : 'printed',
              needs_review: f.needs_review
            });
          }
        }
        return regions;
      }
    }

    // Format 2: PreviewResponse with bounding_boxes array
    if (this.documentData.bounding_boxes && Array.isArray(this.documentData.bounding_boxes)) {
      return this.documentData.bounding_boxes;
    }

    // Format 3: Direct regions array
    if (Array.isArray(this.documentData)) {
      return this.documentData;
    }

    return [];
  }

  selectRegion(regionId) {
    this.selectedRegionId = regionId;
    this.renderPage(this.currentPage);
  }

  nextPage() {
    if (this.currentPage < this.totalPages) {
      this.currentPage += 1;
      this.updatePageControls();
      this.renderPage(this.currentPage);
    }
  }

  prevPage() {
    if (this.currentPage > 1) {
      this.currentPage -= 1;
      this.updatePageControls();
      this.renderPage(this.currentPage);
    }
  }

  setZoom(scale) {
    this.zoomScale = Math.max(0.5, Math.min(3.0, scale));
    if (this.canvas) {
      this.canvas.width = Math.round(this.baseWidth * this.zoomScale);
      this.canvas.height = Math.round(this.baseHeight * this.zoomScale);
    }
    this.renderPage(this.currentPage);
  }

  updatePageControls() {
    if (typeof document === 'undefined') return;
    const pageLabel = document.getElementById('preview-page-indicator');
    if (pageLabel) {
      pageLabel.textContent = `Page ${this.currentPage} / ${this.totalPages}`;
    }
    const prevBtn = document.getElementById('btn-prev-page');
    if (prevBtn) prevBtn.disabled = this.currentPage <= 1;
    const nextBtn = document.getElementById('btn-next-page');
    if (nextBtn) nextBtn.disabled = this.currentPage >= this.totalPages;
  }

  handleCanvasClick(event) {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / rect.width;
    const scaleY = this.canvas.height / rect.height;
    const clickX = (event.clientX - rect.left) * scaleX;
    const clickY = (event.clientY - rect.top) * scaleY;

    const regions = this.getRegionsForPage(this.currentPage);
    const width = this.canvas.width;
    const height = this.canvas.height;

    for (let i = regions.length - 1; i >= 0; i--) {
      const region = regions[i];
      const bbox = region.box_2d || region.coordinates || region.bounding_box;
      if (!bbox) continue;
      const { x, y, w, h } = computeBoxCoordinates(bbox, width, height);

      if (clickX >= x && clickX <= x + w && clickY >= y && clickY <= y + h) {
        this.selectRegion(region.region_id);
        return;
      }
    }

    // Clicked background: deselect
    this.selectRegion(null);
  }

  renderPage(pageNumber = 1) {
    if (!this.canvas || !this.ctx) return;
    this.currentPage = pageNumber;
    const width = this.canvas.width;
    const height = this.canvas.height;

    this.ctx.clearRect(0, 0, width, height);

    // Industrial blueprint / dark document backdrop
    this.ctx.fillStyle = '#0b1120';
    this.ctx.fillRect(0, 0, width, height);

    // Subtle grid lines simulating technical schematic paper
    this.ctx.strokeStyle = 'rgba(51, 65, 85, 0.4)';
    this.ctx.lineWidth = 1;
    const gridSize = 40 * this.zoomScale;
    for (let gx = 0; gx < width; gx += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(gx, 0);
      this.ctx.lineTo(gx, height);
      this.ctx.stroke();
    }
    for (let gy = 0; gy < height; gy += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, gy);
      this.ctx.lineTo(width, gy);
      this.ctx.stroke();
    }

    const regions = this.getRegionsForPage(pageNumber);
    const emptyState = typeof document !== 'undefined' ? document.getElementById('preview-empty-state') : null;
    if (emptyState) {
      emptyState.style.display = regions.length === 0 ? 'flex' : 'none';
    }

    // Render bounding boxes
    for (const region of regions) {
      const bbox = region.box_2d || region.coordinates || region.bounding_box;
      if (!bbox) continue;
      const { x, y, w, h } = computeBoxCoordinates(bbox, width, height);
      const color = getColorForRegion(region);
      const isSelected = this.selectedRegionId && this.selectedRegionId === region.region_id;

      this.ctx.save();
      this.ctx.strokeStyle = isSelected ? this.colors.highlight : color;
      this.ctx.lineWidth = isSelected ? 3 : 2;
      this.ctx.fillStyle = isSelected ? this.colors.highlightFill : this.colors.normalFill;
      this.ctx.fillRect(x, y, w, h);
      this.ctx.strokeRect(x, y, w, h);

      // Label badge
      const label = region.region_id || region.text || '';
      if (label) {
        this.ctx.fillStyle = isSelected ? this.colors.highlight : color;
        this.ctx.font = '10px "Consolas", monospace';
        const displayLabel = label.length > 20 ? label.substring(0, 18) + '..' : label;
        const textWidth = this.ctx.measureText(displayLabel).width;
        const labelY = Math.max(0, y - 14);
        this.ctx.fillRect(x, labelY, textWidth + 6, 14);
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillText(displayLabel, x + 3, labelY + 11);
      }
      this.ctx.restore();
    }
  }
}

if (typeof window !== 'undefined') {
  window.DocumentPreviewRenderer = DocumentPreviewRenderer;
  window.computeBoxCoordinates = computeBoxCoordinates;
  window.getColorForRegion = getColorForRegion;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    DocumentPreviewRenderer,
    computeBoxCoordinates,
    getColorForRegion
  };
}
