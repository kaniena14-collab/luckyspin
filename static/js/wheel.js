/**
 * Lucky Spin Wheel Class
 * Handles wheel rendering, animation, and spin logic
 */
class SpinWheel {
    constructor(canvasId, prizes, settings) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.prizes = prizes || [];
        this.settings = settings || {};
        
        // Wheel properties
        this.centerX = this.canvas.width / 2;
        this.centerY = this.canvas.height / 2;
        this.radius = Math.min(this.centerX, this.centerY) - 20;
        this.currentRotation = 0;
        this.isSpinning = false;
        
        // Animation properties
        this.animationId = null;
        this.spinDuration = 5000; // 5 seconds
        this.easingFunction = this.easeOutCubic;
        
        // Bind context for event handlers
        this.handleResize = this.handleResize.bind(this);
        
        // Setup responsive canvas
        this.setupCanvas();
        window.addEventListener('resize', this.handleResize);
    }
    
    /**
     * Setup canvas for high DPI displays and responsive sizing
     */
    setupCanvas() {
        // Get container size for responsive design
        const container = this.canvas.parentElement;
        const containerWidth = container.clientWidth;
        const isMobile = window.innerWidth <= 768;
        
        // Set canvas size - much bigger (2x lipat) but responsive
        let canvasSize;
        if (isMobile) {
            // Mobile: maksimal 380px untuk layar 412px, beri margin 32px
            const screenWidth = window.innerWidth;
            canvasSize = Math.min(screenWidth - 32, 380); // Pastikan tidak terpotong di mobile
        } else {
            // Desktop: 2x lebih besar dari sebelumnya
            canvasSize = Math.min(700, containerWidth - 40); // Dari 450 jadi 700
        }
        
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = canvasSize * dpr;
        this.canvas.height = canvasSize * dpr;
        this.canvas.style.width = canvasSize + 'px';
        this.canvas.style.height = canvasSize + 'px';
        
        this.ctx.scale(dpr, dpr);
        
        // Recalculate dimensions
        this.centerX = canvasSize / 2;
        this.centerY = canvasSize / 2;
        this.radius = Math.max(80, Math.min(this.centerX, this.centerY) - 30); // Lebih besar juga
    }
    
    /**
     * Handle window resize
     */
    handleResize() {
        this.setupCanvas();
        this.draw();
    }
    
    /**
     * Draw the complete wheel
     */
    draw() {
        if (!this.prizes || this.prizes.length === 0) {
            this.drawEmptyWheel();
            return;
        }
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw wheel segments
        this.drawSegments();
        
        // Draw center circle
        this.drawCenter();
        
        // Draw border
        this.drawBorder();
    }
    
    /**
     * Draw wheel segments with prizes
     */
    drawSegments() {
        const segmentCount = this.prizes.length;
        const anglePerSegment = (2 * Math.PI) / segmentCount;
        
        this.prizes.forEach((prize, index) => {
            const startAngle = (index * anglePerSegment) + this.currentRotation - (Math.PI / 2);
            const endAngle = ((index + 1) * anglePerSegment) + this.currentRotation - (Math.PI / 2);
            
            // Alternate colors for segments
            const color = index % 2 === 0 ? this.settings.color1 : this.settings.color2;
            
            // Draw segment
            this.ctx.fillStyle = color;
            this.ctx.beginPath();
            this.ctx.moveTo(this.centerX, this.centerY);
            this.ctx.arc(this.centerX, this.centerY, this.radius, startAngle, endAngle);
            this.ctx.closePath();
            this.ctx.fill();
            
            // Draw segment border
            this.ctx.strokeStyle = '#ffffff';
            this.ctx.lineWidth = 1;
            this.ctx.stroke();
            
            // Draw prize text
            this.drawPrizeText(prize, startAngle, endAngle);
            
            // Draw prize icon if available
            this.drawPrizeIcon(prize, startAngle, endAngle);
        });
    }
    
    /**
     * Draw prize text on segment
     */
    drawPrizeText(prize, startAngle, endAngle) {
        const textAngle = startAngle + (endAngle - startAngle) / 2;
        const textRadius = this.radius * 0.7;
        
        // Calculate text position
        const textX = this.centerX + Math.cos(textAngle) * textRadius;
        const textY = this.centerY + Math.sin(textAngle) * textRadius;
        
        // Set text properties with bigger font size for better readability
        this.ctx.fillStyle = this.settings.textColor || '#FFFFFF';
        const isMobile = window.innerWidth <= 768;
        // Ukuran font diperbesar untuk wheel yang lebih besar
        const fontSize = isMobile ? Math.max(18, this.radius / 8) : Math.max(20, this.radius / 10);
        this.ctx.font = `bold ${fontSize}px Arial, sans-serif`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        
        // Add text shadow
        this.ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
        this.ctx.shadowBlur = 3;
        this.ctx.shadowOffsetX = 1;
        this.ctx.shadowOffsetY = 1;
        
        // Save context for rotation - mengikuti orientasi segment
        this.ctx.save();
        this.ctx.translate(textX, textY);
        
        // Rotate text to follow the segment orientation
        let rotationAngle = textAngle;
        // Jika teks di bagian bawah wheel, flip supaya tetap bisa dibaca
        if (textAngle > Math.PI / 2 && textAngle < (3 * Math.PI) / 2) {
            rotationAngle += Math.PI; // Flip text 180 degrees
        }
        this.ctx.rotate(rotationAngle);
        
        // Wrap long text dengan area yang lebih lebar
        const maxWidth = this.radius * 0.5; // Diperlebar dari 0.4 ke 0.5
        this.wrapText(prize.name, 0, 0, maxWidth);
        
        this.ctx.restore();
        
        // Reset shadow
        this.ctx.shadowColor = 'transparent';
        this.ctx.shadowBlur = 0;
        this.ctx.shadowOffsetX = 0;
        this.ctx.shadowOffsetY = 0;
    }
    
    /**
     * Draw prize icon on segment
     */
    drawPrizeIcon(prize, startAngle, endAngle) {
        if (!prize.icon_path) return;
        
        const iconAngle = startAngle + (endAngle - startAngle) / 2;
        const iconRadius = this.radius * 0.4;
        
        const iconX = this.centerX + Math.cos(iconAngle) * iconRadius;
        const iconY = this.centerY + Math.sin(iconAngle) * iconRadius;
        
        // Create image element
        const img = new Image();
        img.onload = () => {
            const iconSize = Math.max(20, this.radius / 10);
            
            this.ctx.save();
            this.ctx.translate(iconX, iconY);
            this.ctx.rotate(iconAngle + Math.PI / 2);
            
            // Draw image with drop shadow
            this.ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
            this.ctx.shadowBlur = 5;
            this.ctx.shadowOffsetX = 2;
            this.ctx.shadowOffsetY = 2;
            
            this.ctx.drawImage(img, -iconSize/2, -iconSize/2, iconSize, iconSize);
            
            this.ctx.restore();
        };
        img.src = `/uploads/${prize.icon_path}`;
    }
    
    /**
     * Wrap text to fit within specified width
     */
    wrapText(text, x, y, maxWidth) {
        const words = text.split(' ');
        let line = '';
        let lineHeight = parseInt(this.ctx.font) * 1.2;
        let currentY = y;
        
        for (let n = 0; n < words.length; n++) {
            const testLine = line + words[n] + ' ';
            const metrics = this.ctx.measureText(testLine);
            const testWidth = metrics.width;
            
            if (testWidth > maxWidth && n > 0) {
                this.ctx.fillText(line, x, currentY);
                line = words[n] + ' ';
                currentY += lineHeight;
            } else {
                line = testLine;
            }
        }
        this.ctx.fillText(line, x, currentY);
    }
    
    /**
     * Draw text vertically with characters stacked
     */
    wrapTextVertically(text, x, y, maxWidth) {
        // Clean text and limit length for better display
        const cleanText = text.replace(/\s+/g, ' ').trim();
        let displayText = cleanText;
        
        // If text is too long, show first few characters + "..."
        if (cleanText.length > 8) {
            displayText = cleanText.substring(0, 6) + '..';
        }
        
        const characters = displayText.split('');
        const charHeight = parseInt(this.ctx.font) * 0.9;
        const totalHeight = characters.length * charHeight;
        const startY = y - totalHeight / 2;
        
        // Draw each character vertically stacked
        characters.forEach((char, index) => {
            this.ctx.fillText(char, x, startY + (index * charHeight));
        });
    }
    
    /**
     * Draw casino-style gold center circle
     */
    drawCenter() {
        const isMobile = window.innerWidth <= 768;
        const outerRadius = isMobile ? 35 : 40;
        const innerRadius = isMobile ? 25 : 30;
        
        // Gold outer ring with gradient
        const goldGradient = this.ctx.createRadialGradient(
            this.centerX, this.centerY, 0,
            this.centerX, this.centerY, outerRadius
        );
        goldGradient.addColorStop(0, '#ffd700');
        goldGradient.addColorStop(0.6, '#ffed4e');
        goldGradient.addColorStop(1, '#cc9900');
        
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, outerRadius, 0, 2 * Math.PI);
        this.ctx.fillStyle = goldGradient;
        this.ctx.fill();
        
        // Gold border
        this.ctx.strokeStyle = '#b8860b';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
        
        // Inner dark circle
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, innerRadius, 0, 2 * Math.PI);
        this.ctx.fillStyle = '#2c1810';
        this.ctx.fill();
        
        // Inner gold highlight
        const innerGoldGradient = this.ctx.createRadialGradient(
            this.centerX, this.centerY - 5, 0,
            this.centerX, this.centerY, innerRadius
        );
        innerGoldGradient.addColorStop(0, 'rgba(255, 215, 0, 0.3)');
        innerGoldGradient.addColorStop(1, 'rgba(255, 215, 0, 0)');
        
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, innerRadius, 0, 2 * Math.PI);
        this.ctx.fillStyle = innerGoldGradient;
        this.ctx.fill();
    }
    
    /**
     * Draw star in center
     */
    drawStar(cx, cy, radius) {
        const spikes = 5;
        const step = Math.PI / spikes;
        let rot = Math.PI / 2 * 3;
        
        this.ctx.beginPath();
        this.ctx.moveTo(cx, cy - radius);
        
        for (let i = 0; i < spikes; i++) {
            const x = cx + Math.cos(rot) * radius;
            const y = cy + Math.sin(rot) * radius;
            this.ctx.lineTo(x, y);
            rot += step;
            
            const innerX = cx + Math.cos(rot) * (radius * 0.5);
            const innerY = cy + Math.sin(rot) * (radius * 0.5);
            this.ctx.lineTo(innerX, innerY);
            rot += step;
        }
        
        this.ctx.lineTo(cx, cy - radius);
        this.ctx.closePath();
        this.ctx.fillStyle = '#FFD700';
        this.ctx.fill();
        
        this.ctx.strokeStyle = this.settings.borderColor || '#333';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
    }
    
    /**
     * Draw enhanced wheel border with glow effect
     */
    drawBorder() {
        // Reset any shadows
        this.ctx.shadowColor = 'transparent';
        this.ctx.shadowBlur = 0;
        
        // Red outer border
        this.ctx.strokeStyle = '#dc2626';
        this.ctx.lineWidth = 12;
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, this.radius + 6, 0, 2 * Math.PI);
        this.ctx.stroke();
        
        // White inner border line
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 3;
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, this.radius + 1, 0, 2 * Math.PI);
        this.ctx.stroke();
        
        // Draw white dots around the border
        this.drawBorderDots();
    }
    
    /**
     * Draw white dots around the red border
     */
    drawBorderDots() {
        const dotCount = 24; // Number of dots around border
        const dotRadius = 4;
        const borderRadius = this.radius + 6;
        
        this.ctx.fillStyle = '#ffffff';
        
        for (let i = 0; i < dotCount; i++) {
            const angle = (i / dotCount) * 2 * Math.PI;
            const dotX = this.centerX + Math.cos(angle) * borderRadius;
            const dotY = this.centerY + Math.sin(angle) * borderRadius;
            
            this.ctx.beginPath();
            this.ctx.arc(dotX, dotY, dotRadius, 0, 2 * Math.PI);
            this.ctx.fill();
        }
    }
    
    /**
     * Draw empty wheel when no prizes
     */
    drawEmptyWheel() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw empty circle
        this.ctx.fillStyle = '#444';
        this.ctx.beginPath();
        this.ctx.arc(this.centerX, this.centerY, this.radius, 0, 2 * Math.PI);
        this.ctx.fill();
        
        // Draw border
        this.drawBorder();
        
        // Draw center
        this.drawCenter();
        
        // Draw "No Prizes" text
        this.ctx.fillStyle = '#999';
        this.ctx.font = `${Math.max(16, this.radius / 10)}px Arial, sans-serif`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('No Prizes Available', this.centerX, this.centerY + this.radius / 2);
    }
    
    /**
     * Spin the wheel with animation
     */
    spin(finalRotation, onComplete) {
        if (this.isSpinning) return;
        
        this.isSpinning = true;
        const startRotation = this.currentRotation;
        const startTime = performance.now();
        
        // Convert degrees to radians
        const targetRotation = (finalRotation * Math.PI) / 180;
        const totalRotation = targetRotation - startRotation;
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / this.spinDuration, 1);
            
            // Apply easing
            const eased = this.easingFunction(progress);
            
            // Update rotation
            this.currentRotation = startRotation + (totalRotation * eased);
            
            // Redraw wheel
            this.draw();
            
            if (progress < 1) {
                this.animationId = requestAnimationFrame(animate);
            } else {
                this.isSpinning = false;
                if (onComplete) {
                    setTimeout(onComplete, 500); // Small delay before showing result
                }
            }
        };
        
        this.animationId = requestAnimationFrame(animate);
    }
    
    /**
     * Easing function for smooth animation
     */
    easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }
    
    /**
     * Get the winning segment based on current rotation
     */
    getWinningSegment() {
        if (!this.prizes || this.prizes.length === 0) return null;
        
        // Normalize rotation to 0-2π range
        const normalizedRotation = ((this.currentRotation % (2 * Math.PI)) + (2 * Math.PI)) % (2 * Math.PI);
        
        // Calculate which segment the pointer is on (pointer is at top, 0 degrees)
        const segmentAngle = (2 * Math.PI) / this.prizes.length;
        const pointerAngle = (Math.PI / 2) - normalizedRotation; // Adjust for pointer position
        const segmentIndex = Math.floor(((pointerAngle % (2 * Math.PI)) + (2 * Math.PI)) % (2 * Math.PI) / segmentAngle);
        
        return this.prizes[segmentIndex] || this.prizes[0];
    }
    
    /**
     * Update wheel settings
     */
    updateSettings(newSettings) {
        this.settings = { ...this.settings, ...newSettings };
        this.draw();
    }
    
    /**
     * Update prizes and redraw
     */
    updatePrizes(newPrizes) {
        this.prizes = newPrizes || [];
        this.draw();
    }
    
    /**
     * Destroy wheel and cleanup
     */
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        window.removeEventListener('resize', this.handleResize);
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SpinWheel;
}
