# AgroIntel v4.0 — UI Style Guide & Design Tokens

## Executive Summary

The AgroIntel v4.0 interface implements modern **Glassmorphism Design Principles** tailored specifically for agricultural intelligence platforms. It features curated HSL/RGB color tokens, clean typography (`Inter`), backdrop blur effects, and seamless Dark/Light theme switching.

---

## 1. Color Palette Tokens

### Dark Theme (`data-theme="dark"`)
- **Background Main**: `#090d16` (Deep obsidian dark)
- **Glass Surface**: `rgba(18, 26, 43, 0.7)` (Translucent navy blue)
- **Accent Emerald**: `#10b981` (Vibrant agricultural green)
- **Accent Blue**: `#3b82f6` (Tech blue)
- **Accent Gold**: `#f59e0b` (Market gold)
- **Accent Crimson**: `#ef4444` (Warning red)

### Light Theme (`data-theme="light"`)
- **Background Main**: `#f0fdf4` (Soft mint background)
- **Glass Surface**: `rgba(255, 255, 255, 0.85)` (Translucent white)
- **Accent Emerald**: `#059669` (Deep forest green)
- **Accent Blue**: `#2563eb` (Royal blue)
- **Accent Gold**: `#d97706` (Amber gold)

---

## 2. Glassmorphism Design Rules

1. **Translucency & Backdrop Blur**:
   - `backdrop-filter: blur(16px)` applied to cards, navbar, and hero banners.
2. **Subtle Border Glow**:
   - 1px solid borders (`rgba(255, 255, 255, 0.12)`) transitioning to emerald glow on hover (`rgba(16, 185, 129, 0.4)`).
3. **Shadow Depth**:
   - Multi-layered soft drop shadows (`0 8px 32px 0 rgba(0, 0, 0, 0.4)`).

---

## 3. Typography Rules

- **Font Family**: `'Inter', system-ui, -apple-system, sans-serif`
- **Headings**:
  - `Hero Title`: 2.2rem, Font Weight 800
  - `Section Header`: 1.6rem, Font Weight 800
  - `Card Title`: 1.3rem, Font Weight 700
- **Body Text**: 0.9rem - 1.05rem, Font Weight 400 - 500

---
*AgroIntel v4.0 UI Style Guide*
