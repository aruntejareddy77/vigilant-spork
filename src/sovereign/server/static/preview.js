/**
 * preview.js
 * Canvas-based document preview and bounding box renderer.
 * Air-gapped: zero external CDN dependencies.
 */
class DocumentPreviewRenderer {
  constructor(canvasId, imageId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.image = document.getElementById(imageId);
    this.documentData = null;
    this.currentPage = 1;
    this.selectedRegionId = null;
    this.zoomScale = 1.0;

    this.colors = {
      printed: '#10b981',      // Green
      handwriting: '#3b82f6',  // Blue
      review: '#f59e0b',       // Amber (< 0.85 confidence)
      diffAdd: '#10b981',      // Green
      diffRem: '#ef4444',      // Red
      diffMod: '#f59e0b',      // Amber
      highlight: '#ef4444'     // Highlight border halo
    };
  }

  setDocument(docData) {
    this.documentData = docData;
    this.currentPage = 1;
    this.selectedRegionId = null;
    this.renderPage(this.currentPage);
  }

  computeBoxCoordinates(bbox, width, height) {
    // bbox is [ymin, xmin, ymax, xmax] in normalized coordinates [0.0, 1.0]
    const [ymin, xmin, ymax, xmax] = bbox;
    return {
      x: xmin * width,
      y: ymin * height,
      w: (xmax - xmin) * width,
      h: (ymax - ymin) * height
    };
  }

  selectRegion(regionId) {
    this.selectedRegionId = regionId;
    this.renderPage(this.currentPage);
  }

  renderPage(pageNumber) {
    if (!this.canvas || !this.ctx) return;
    this.currentPage = pageNumber;
    const width = this.canvas.width;
    const height = this.canvas.height;

    this.ctx.clearRect(0, 0, width, height);

    // Draw background placeholder
    this.ctx.fillStyle = '#0f172a';
    this.ctx.fillRect(0, 0, width, height);

    if (!this.documentData || !this.documentData.pages) {
      return;
    }

    const page = this.documentData.pages.find(p => p.page_number === pageNumber);
    if (!page || !page.regions) return;

    // Render bounding boxes
    for (const region of page.regions) {
      const { x, y, w, h } = this.computeBoxCoordinates(region.bounding_box, width, height);
      let color = this.colors.printed;

      if (region.type === 'handwriting') {
        color = this.colors.handwriting;
      } else if (region.confidence !== undefined && region.confidence < 0.85) {
        color = this.colors.review;
      } else if (region.diff_status === 'added') {
        color = this.colors.diffAdd;
      } else if (region.diff_status === 'removed') {
        color = this.colors.diffRem;
      } else if (region.diff_status === 'modified') {
        color = this.colors.diffMod;
      }

      const isSelected = this.selectedRegionId === region.region_id;

      this.ctx.save();
      this.ctx.strokeStyle = isSelected ? this.colors.highlight : color;
      this.ctx.lineWidth = isSelected ? 3 : 2;
      this.ctx.fillStyle = isSelected ? 'rgba(239, 68, 68, 0.25)' : 'rgba(255, 255, 255, 0.05)';
      this.ctx.fillRect(x, y, w, h);
      this.ctx.strokeRect(x, y, w, h);

      // Label tag
      if (region.region_id) {
        this.ctx.fillStyle = isSelected ? this.colors.highlight : color;
        this.ctx.font = '10px Consolas, monospace';
        const label = region.region_id;
        const textWidth = this.ctx.measureText(label).width;
        this.ctx.fillRect(x, Math.max(0, y - 14), textWidth + 4, 14);
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillText(label, x + 2, Math.max(10, y - 3));
      }
      this.ctx.restore();
    }
  }
}

if (typeof window !== 'undefined') {
  window.DocumentPreviewRenderer = DocumentPreviewRenderer;
}
