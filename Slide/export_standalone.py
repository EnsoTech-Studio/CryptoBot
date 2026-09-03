#!/usr/bin/env python3
"""
export_standalone.py — Export CryptoBot architecture slides to a 100% standalone HTML file.

Features:
- Single self-contained HTML file (zero external dependencies, zero web server needed).
- Embeds all architecture diagram images as Base64 data URIs.
- Inlines marked.min.js and all styles/scripts.
- Keyboard navigation (Arrows, Space, PageUp/Down, Home, End).
- Fullscreen mode (F key), Blackout/Blank mode (B key for speaker pauses).
- Interactive HD Image Zoom Modal for diagrams.
- Live Presentation Stopwatch Timer (with Play/Pause/Reset).
- Jump-to-slide Dropdown Menu with slide titles.
- Auto-scaling 16:9 canvas (1280x720) fitting any display (1080p, 4K, 720p, projectors).
- Print / Save as PDF mode with @media print stylesheet.
"""

import os
import re
import json
import base64
import argparse

def get_slide_markdowns(slide_dir, sec_dir, section_files, inline_images=True):
    slides_raw = []
    image_cache = {}
    total_img_bytes = 0

    combined_sections = []
    for sec in section_files:
        path = os.path.join(sec_dir, sec)
        if not os.path.exists(path):
            print(f"[Warning] Section file not found: {path}")
            continue
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            combined_sections.append(content)

    full_markdown = '\n\n---\n\n'.join(combined_sections)
    parts = re.split(r'\n+---+\s*\n+', full_markdown)

    for p in parts:
        p_str = p.strip()
        if not p_str or p_str.startswith('marp: true') or p_str.startswith('style:') or 'paginate: true' in p_str:
            continue

        if inline_images:
            # Replace all markdown image links with Base64 data URIs
            def replace_img(match):
                nonlocal total_img_bytes
                alt_text = match.group(1)
                img_rel = match.group(2)

                if img_rel.startswith('data:'):
                    return match.group(0)

                # Resolve relative path from sections/ or Slide/
                if img_rel.startswith('../../'):
                    disk_path = os.path.normpath(os.path.join(sec_dir, img_rel))
                elif img_rel.startswith('../'):
                    disk_path = os.path.normpath(os.path.join(slide_dir, img_rel))
                else:
                    disk_path = os.path.normpath(os.path.join(slide_dir, img_rel))

                if not os.path.exists(disk_path):
                    # Try looking directly in sec_dir, slide_dir, or blueprint/assets/diagrams-png/
                    base_name = os.path.basename(img_rel)
                    candidates = [
                        os.path.normpath(os.path.join(sec_dir, img_rel)),
                        os.path.normpath(os.path.join(slide_dir, base_name)),
                        os.path.normpath(os.path.join(slide_dir, '..', 'blueprint', 'assets', 'diagrams-png', base_name))
                    ]
                    for cand in candidates:
                        if os.path.exists(cand):
                            disk_path = cand
                            break

                if os.path.exists(disk_path):
                    if disk_path not in image_cache:
                        with open(disk_path, 'rb') as ifp:
                            raw = ifp.read()
                            total_img_bytes += len(raw)
                            ext = os.path.splitext(disk_path)[1].lower().replace('.', '')
                            mime = 'image/png' if ext == 'png' else f'image/{ext}'
                            b64 = base64.b64encode(raw).decode('utf-8')
                            image_cache[disk_path] = f'data:{mime};base64,{b64}'
                    return f'![{alt_text}]({image_cache[disk_path]})'
                else:
                    print(f"[Warning] Image file not found: {img_rel} (resolved: {disk_path})")
                    return match.group(0)

            p_str = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_img, p_str)

        slides_raw.append(p_str)

    print(f"[Export] Processed {len(slides_raw)} slides, encoded {len(image_cache)} images ({total_img_bytes / (1024*1024):.2f} MB raw binary).")
    return slides_raw

def read_vendor_file(slide_dir, filename):
    vendor_path = os.path.join(slide_dir, 'vendor', filename)
    if os.path.exists(vendor_path):
        with open(vendor_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def build_standalone_html(output_file='standalone.html'):
    slide_dir = os.path.dirname(os.path.abspath(__file__))
    sec_dir = os.path.join(slide_dir, 'sections')
    
    section_files = [
        '01_drivers_asrs.md',
        '02_usecase_c4.md',
        '03_component_boundaries.md',
        '04_contracts_class_diagrams.md',
        '05_high_level_architecture.md',
        '06_runtime_flows.md',
        '07_security_scale_failure_devops.md',
        '08_tradeoffs_summary.md'
    ]

    slides_raw = get_slide_markdowns(slide_dir, sec_dir, section_files, inline_images=True)
    slides_json = json.dumps(slides_raw, ensure_ascii=False)

    # Inlined Marked JS
    marked_js = read_vendor_file(slide_dir, 'marked.min.js')
    if not marked_js:
        print("[Warning] marked.min.js not found in vendor/. Downloading...")
        try:
            import urllib.request
            resp = urllib.request.urlopen('https://cdn.jsdelivr.net/npm/marked/marked.min.js', timeout=8)
            marked_js = resp.read().decode('utf-8')
        except Exception as e:
            print(f"[Error] Failed to fetch marked.min.js: {e}")

    # Standalone HTML Template
    html = f'''<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CryptoBot — Software Architecture Presentation (Standalone)</title>
  <style>
    :root {{
      --primary: #1e3a8a;
      --primary-light: #2563eb;
      --primary-dark: #172554;
      --secondary: #0f766e;
      --bg-canvas: #090d16;
      --bg-slide: #ffffff;
      --text-main: #1e293b;
      --text-muted: #64748b;
      --border-color: #e2e8f0;
      --accent: #f59e0b;
      --card-bg: #f8fafc;
      --success: #10b981;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      background-color: var(--bg-canvas);
      color: var(--text-main);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      user-select: none;
    }}

    /* Top Header Bar */
    header {{
      background: #111827;
      color: #f8fafc;
      padding: 8px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1f2937;
      font-size: 13.5px;
      z-index: 100;
    }}
    .header-left {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .header-title {{
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
      color: #93c5fd;
      font-size: 14.5px;
    }}
    .header-badge {{
      background: #2563eb;
      color: #ffffff;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11.5px;
      font-weight: 600;
      letter-spacing: 0.3px;
    }}
    .header-timer {{
      background: #1e293b;
      border: 1px solid #334155;
      padding: 3px 10px;
      border-radius: 6px;
      color: #38bdf8;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }}
    .header-timer:hover {{
      background: #334155;
    }}

    .header-controls {{
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    button.btn-ctrl {{
      background: #1f2937;
      border: 1px solid #374151;
      color: #f8fafc;
      padding: 5px 11px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12.5px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }}
    button.btn-ctrl:hover {{
      background: #374151;
      border-color: #4b5563;
    }}
    button.btn-ctrl:active {{
      transform: scale(0.97);
    }}
    select.nav-select {{
      background: #1f2937;
      color: #f8fafc;
      border: 1px solid #374151;
      padding: 5px 10px;
      border-radius: 6px;
      font-size: 12.5px;
      max-width: 320px;
      cursor: pointer;
    }}
    select.nav-select:focus {{
      outline: 2px solid #2563eb;
    }}

    /* Main Presentation Stage */
    #stage {{
      flex: 1;
      display: flex;
      justify-content: center;
      align-items: center;
      position: relative;
      background: #080d1a;
      padding: 16px;
      overflow: hidden;
    }}

    /* 16:9 Aspect Ratio Slide Container */
    #slide-viewport {{
      width: 1280px;
      height: 720px;
      background: var(--bg-slide);
      border-radius: 8px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transform-origin: center center;
      transition: transform 0.08s ease-out;
    }}

    .slide-body {{
      flex: 1;
      padding: 32px 48px 20px 48px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      scrollbar-width: thin;
      scrollbar-color: #cbd5e1 transparent;
    }}
    .slide-body::-webkit-scrollbar {{
      width: 6px;
    }}
    .slide-body::-webkit-scrollbar-thumb {{
      background: #cbd5e1;
      border-radius: 3px;
    }}

    /* Slide Typography & Layouts */
    .slide-body h1 {{
      color: #0f172a;
      font-size: 36px;
      font-weight: 800;
      margin-bottom: 12px;
      letter-spacing: -0.5px;
    }}
    .slide-body h2 {{
      color: var(--primary);
      font-size: 28px;
      font-weight: 700;
      border-bottom: 2px solid var(--border-color);
      padding-bottom: 8px;
      margin-top: 0;
      margin-bottom: 14px;
    }}
    .slide-body h3 {{
      color: var(--primary-light);
      font-size: 23px;
      font-weight: 600;
      margin-top: 4px;
      margin-bottom: 8px;
    }}
    .slide-body p, .slide-body li {{
      font-size: 22px;
      line-height: 1.45;
      color: var(--text-main);
    }}
    .slide-body ul {{
      margin-top: 4px;
      margin-bottom: 6px;
      padding-left: 22px;
    }}
    .slide-body li {{
      margin-bottom: 4px;
    }}
    .slide-body li ul {{
      margin-top: 2px;
      margin-bottom: 2px;
      padding-left: 18px;
    }}
    .slide-body li li {{
      margin-bottom: 2px;
      font-size: 20px;
    }}
    .slide-body strong {{
      color: #0f172a;
      font-weight: 600;
    }}
    .slide-body code {{
      background: #f1f5f9;
      color: #0f172a;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.9em;
      border: 1px solid #e2e8f0;
    }}

    /* Layout Grids */
    .columns {{
      display: grid;
      grid-template-columns: 1fr 1.15fr;
      gap: 28px;
      align-items: center;
      margin-top: 4px;
    }}
    .columns-equal {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      align-items: start;
    }}

    /* Tables */
    .slide-body table {{
      font-size: 17px;
      border-collapse: collapse;
      width: 100%;
      margin-top: 8px;
      background: #ffffff;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid var(--border-color);
    }}
    .slide-body th {{
      background-color: #f1f5f9;
      color: #0f172a;
      border: 1px solid #cbd5e1;
      padding: 8px 12px;
      font-weight: 700;
      font-size: 18px;
      text-align: left;
    }}
    .slide-body td {{
      border: 1px solid var(--border-color);
      padding: 8px 12px;
      font-size: 16.5px;
      line-height: 1.4;
    }}
    .slide-body tr:nth-child(even) {{
      background-color: #f8fafc;
    }}

    /* Diagram Images */
    .slide-body img {{
      max-height: 480px;
      max-width: 100%;
      object-fit: contain;
      border-radius: 8px;
      border: 1px solid var(--border-color);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
      background-color: #ffffff;
      display: block;
      margin: 0 auto;
      cursor: zoom-in;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .slide-body img:hover {{
      transform: scale(1.015);
      box-shadow: 0 8px 20px rgba(30, 58, 138, 0.15);
    }}

    /* Title / Lead Slide */
    .slide-body.lead {{
      text-align: center;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
    }}
    .slide-body.lead img {{
      width: 80px;
      height: 80px;
      max-height: 80px;
      max-width: 80px;
      object-fit: contain;
      border-radius: 14px;
      border: 1.5px solid #cbd5e1;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
      margin-bottom: 12px;
      background-color: #ffffff;
      padding: 5px;
    }}
    .slide-body.lead .lead-institution {{
      margin-top: 0;
      margin-bottom: 14px;
      text-align: center;
    }}
    .slide-body.lead .lead-uni {{
      font-size: 16.5px;
      font-weight: 700;
      color: #1e293b;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin: 0 0 4px 0;
      line-height: 1.3;
    }}
    .slide-body.lead .lead-faculty {{
      font-size: 14.5px;
      font-weight: 600;
      color: #2563eb;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin: 0;
      line-height: 1.3;
    }}
    .slide-body.lead h1 {{
      font-size: 38px;
      color: var(--primary);
      margin-bottom: 16px;
    }}
    .slide-body.lead h2 {{
      border-bottom: none;
      font-size: 22px;
      color: #475569;
      margin-bottom: 24px;
    }}

    /* Slide Footer */
    .slide-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 48px 10px 48px;
      font-size: 11.5px;
      color: var(--text-muted);
      border-top: 1px solid #f1f5f9;
      background: #ffffff;
    }}

    /* Bottom Control Bar */
    footer.bottom-bar {{
      background: #111827;
      padding: 8px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: #94a3b8;
      font-size: 13px;
      border-top: 1px solid #1f2937;
    }}
    .progress-track {{
      flex: 1;
      height: 6px;
      background: #1f2937;
      border-radius: 3px;
      margin: 0 20px;
      overflow: hidden;
      cursor: pointer;
    }}
    .progress-bar {{
      height: 100%;
      background: linear-gradient(90deg, #2563eb, #60a5fa);
      width: 0%;
      transition: width 0.2s ease;
    }}

    /* Blackout Overlay */
    #blackout-screen {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #000000;
      z-index: 9999;
      cursor: pointer;
    }}

    /* Modal for Image Zoom */
    #zoom-modal {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(15, 23, 42, 0.92);
      backdrop-filter: blur(5px);
      z-index: 1000;
      justify-content: center;
      align-items: center;
      cursor: zoom-out;
    }}
    #zoom-modal img {{
      max-width: 94vw;
      max-height: 94vh;
      object-fit: contain;
      border-radius: 8px;
      box-shadow: 0 25px 60px rgba(0,0,0,0.6);
      background: #ffffff;
    }}

    /* Help Overlay */
    #help-overlay {{
      display: none;
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: #1f2937;
      color: #f8fafc;
      padding: 24px 32px;
      border-radius: 12px;
      border: 1px solid #374151;
      box-shadow: 0 20px 40px rgba(0,0,0,0.7);
      z-index: 1500;
      font-size: 14px;
      min-width: 420px;
    }}
    #help-overlay h3 {{
      color: #93c5fd;
      margin-bottom: 14px;
      font-size: 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    #help-overlay table {{
      border-collapse: collapse;
      width: 100%;
    }}
    #help-overlay td {{
      padding: 7px 12px;
      border-bottom: 1px solid #374151;
    }}
    #help-overlay kbd {{
      background: #111827;
      border: 1px solid #374151;
      padding: 2px 7px;
      border-radius: 4px;
      font-family: monospace;
      color: #60a5fa;
      font-size: 12px;
    }}

    /* Standalone Badge Notification */
    .offline-badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }}

    /* Print / PDF Styles */
    @media print {{
      header, footer.bottom-bar, #zoom-modal, #help-overlay, #blackout-screen {{
        display: none !important;
      }}
      body {{
        background: #ffffff !important;
        height: auto !important;
        overflow: visible !important;
      }}
      #stage {{
        padding: 0 !important;
        background: #ffffff !important;
        display: block !important;
      }}
      #slide-viewport {{
        width: 100% !important;
        height: 100vh !important;
        box-shadow: none !important;
        transform: none !important;
        page-break-after: always !important;
        border-radius: 0 !important;
      }}
    }}
  </style>
</head>
<body>

  <!-- Blackout Screen for Speaker Pause -->
  <div id="blackout-screen" onclick="toggleBlackout()"></div>

  <!-- Top Header -->
  <header>
    <div class="header-left">
      <div class="header-title">
        <span>📈 Crypto Strategy Lab</span>
        <span class="header-badge">Software Architecture</span>
        <span class="offline-badge">⚡ Standalone Ready</span>
      </div>
      <div class="header-timer" id="presentation-timer" onclick="toggleTimer()" title="Click để Tạm dừng / Tiếp tục đếm thời gian (Double-click để Reset)">
        ⏱️ <span id="timer-display">00:00</span>
      </div>
    </div>
    <div class="header-controls">
      <select id="section-select" class="nav-select" onchange="jumpToSlide(parseInt(this.value))">
        <!-- Injected via JS -->
      </select>
      <button class="btn-ctrl" onclick="toggleBlackout()" title="Tắt màn hình để tập trung vào người nói (B)">🌑 Tối màn hình (B)</button>
      <button class="btn-ctrl" onclick="toggleHelp()">⌨️ Phím tắt (?)</button>
      <button class="btn-ctrl" onclick="toggleFullscreen()">⛶ Toàn màn hình (F)</button>
    </div>
  </header>

  <!-- Slide Canvas -->
  <main id="stage">
    <div id="slide-viewport">
      <div id="slide-body" class="slide-body">
        <!-- Rendered slide content -->
      </div>
      <div class="slide-footer">
        <span>Crypto Strategy Lab — Architecture Presentation</span>
        <span id="slide-counter">Slide 1 / {len(slides_raw)}</span>
        <span>Trường ĐH Khoa học Tự nhiên - ĐHQG-HCM</span>
      </div>
    </div>
  </main>

  <!-- Bottom Navigation Bar -->
  <footer class="bottom-bar">
    <button class="btn-ctrl" onclick="prevSlide()">◀ Trang trước (←)</button>
    <div class="progress-track" onclick="seekSlide(event)" title="Nhấp vào thanh tiến trình để chuyển nhanh">
      <div id="progress-fill" class="progress-bar"></div>
    </div>
    <span id="slide-indicator" style="font-family: monospace; font-weight: 600;">1 / {len(slides_raw)}</span>
    <button class="btn-ctrl" onclick="nextSlide()">Trang sau (→) ▶</button>
  </footer>

  <!-- Image Zoom Modal -->
  <div id="zoom-modal" onclick="this.style.display='none'">
    <img id="zoomed-img" src="" alt="Zoomed diagram">
  </div>

  <!-- Keyboard Help Modal -->
  <div id="help-overlay">
    <h3>
      <span>⌨️ Phím tắt điều khiển trình chiếu</span>
      <span style="cursor:pointer; font-size:16px;" onclick="toggleHelp()">✕</span>
    </h3>
    <table>
      <tr><td><kbd>→</kbd> / <kbd>Space</kbd> / <kbd>PageDn</kbd></td><td>Chuyển slide kế tiếp</td></tr>
      <tr><td><kbd>←</kbd> / <kbd>Backspace</kbd> / <kbd>PageUp</kbd></td><td>Quay lại slide trước</td></tr>
      <tr><td><kbd>Home</kbd> / <kbd>End</kbd></td><td>Về slide đầu / slide cuối</td></tr>
      <tr><td><kbd>F</kbd></td><td>Bật / tắt chế độ toàn màn hình</td></tr>
      <tr><td><kbd>B</kbd> hoặc <kbd>.</kbd></td><td>Bật / tắt màn hình đen (tập trung người nói)</td></tr>
      <tr><td><kbd>T</kbd></td><td>Bắt đầu / Tạm dừng đồng hồ bấm giờ</td></tr>
      <tr><td><kbd>?</kbd> hoặc <kbd>H</kbd></td><td>Bật / tắt bảng hướng dẫn phím tắt</td></tr>
      <tr><td><kbd>Click ảnh sơ đồ</kbd></td><td>Phóng to sơ đồ kiến trúc HD</td></tr>
    </table>
  </div>

  <!-- Inlined Marked.js for 100% Offline Standalone Support -->
  <script>
{marked_js}
  </script>

  <!-- Presentation Controller Engine -->
  <script>
    const rawSlides = {slides_json};
    let currentSlide = 0;
    const totalSlides = rawSlides.length;

    // Timer State
    let timerSeconds = 0;
    let timerRunning = true;
    let timerInterval = null;

    function startTimer() {{
      if (timerInterval) clearInterval(timerInterval);
      timerInterval = setInterval(() => {{
        if (timerRunning) {{
          timerSeconds++;
          const mins = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
          const secs = String(timerSeconds % 60).padStart(2, '0');
          document.getElementById('timer-display').textContent = `${{mins}}:${{secs}}`;
        }}
      }}, 1000);
    }}

    function toggleTimer() {{
      timerRunning = !timerRunning;
      const el = document.getElementById('presentation-timer');
      el.style.opacity = timerRunning ? '1.0' : '0.6';
    }}

    document.getElementById('presentation-timer').addEventListener('dblclick', (e) => {{
      e.stopPropagation();
      timerSeconds = 0;
      document.getElementById('timer-display').textContent = '00:00';
    }});

    // Custom marked renderer for diagram images
    const renderer = new marked.Renderer();
    renderer.image = function(tokenOrHref, title, text) {{
      let href = tokenOrHref;
      let alt = text;
      let t = title;
      if (typeof tokenOrHref === 'object' && tokenOrHref !== null) {{
        href = tokenOrHref.href;
        alt = tokenOrHref.text;
        t = tokenOrHref.title;
      }}
      return `<img src="${{href}}" alt="${{alt || ''}}" title="${{t || 'Click để phóng to HD'}}" onclick="zoomImage(this.src)" />`;
    }};

    marked.setOptions({{
      renderer: renderer,
      gfm: true,
      breaks: true
    }});

    function resizeViewport() {{
      const stage = document.getElementById('stage');
      const viewport = document.getElementById('slide-viewport');
      if (!stage || !viewport) return;

      const targetW = 1280;
      const targetH = 720;
      
      const availableW = stage.clientWidth - 24;
      const availableH = stage.clientHeight - 24;
      
      const scale = Math.min(availableW / targetW, availableH / targetH, 1.4);
      viewport.style.transform = `scale(${{scale}})`;
    }}

    window.addEventListener('resize', resizeViewport);

    function initSectionDropdown() {{
      const select = document.getElementById('section-select');
      select.innerHTML = '';
      rawSlides.forEach((slide, idx) => {{
        let title = `Slide ${{idx + 1}}`;
        const lines = slide.split('\\n');
        for (const line of lines) {{
          const clean = line.trim();
          if (clean.startsWith('# ') || clean.startsWith('## ')) {{
            title = clean.replace(/^#+\\s*/, '').replace(/<[^>]+>/g, '').trim();
            break;
          }}
        }}
        const opt = document.createElement('option');
        opt.value = idx;
        opt.textContent = `${{idx + 1}}. ${{title.substring(0, 42)}}`;
        select.appendChild(opt);
      }});
    }}

    function renderSlide(index) {{
      if (index < 0) index = 0;
      if (index >= totalSlides) index = totalSlides - 1;
      currentSlide = index;

      const slideMd = rawSlides[currentSlide];
      const isLead = slideMd.includes('class: lead') || currentSlide === 0;

      const slideBody = document.getElementById('slide-body');
      slideBody.className = 'slide-body' + (isLead ? ' lead' : '');
      slideBody.innerHTML = marked.parse(slideMd);

      document.getElementById('slide-counter').textContent = `Slide ${{currentSlide + 1}} / ${{totalSlides}}`;
      document.getElementById('slide-indicator').textContent = `${{currentSlide + 1}} / ${{totalSlides}}`;
      document.getElementById('progress-fill').style.width = `${{((currentSlide + 1) / totalSlides) * 100}}%`;
      document.getElementById('section-select').value = currentSlide;

      // Reset scroll position on new slide
      slideBody.scrollTop = 0;
    }}

    function nextSlide() {{
      if (currentSlide < totalSlides - 1) {{
        renderSlide(currentSlide + 1);
      }}
    }}

    function prevSlide() {{
      if (currentSlide > 0) {{
        renderSlide(currentSlide - 1);
      }}
    }}

    function jumpToSlide(idx) {{
      renderSlide(idx);
    }}

    function seekSlide(e) {{
      const track = e.currentTarget;
      const rect = track.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const pct = Math.max(0, Math.min(1, clickX / rect.width));
      const targetIdx = Math.floor(pct * totalSlides);
      renderSlide(targetIdx);
    }}

    function toggleFullscreen() {{
      if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen().catch(err => alert('Fullscreen error: ' + err.message));
      }} else {{
        document.exitFullscreen();
      }}
    }}

    function toggleBlackout() {{
      const b = document.getElementById('blackout-screen');
      b.style.display = (b.style.display === 'block') ? 'none' : 'block';
    }}

    function zoomImage(src) {{
      const modal = document.getElementById('zoom-modal');
      const img = document.getElementById('zoomed-img');
      img.src = src;
      modal.style.display = 'flex';
    }}

    function toggleHelp() {{
      const help = document.getElementById('help-overlay');
      help.style.display = (help.style.display === 'block') ? 'none' : 'block';
    }}

    // Keyboard Shortcuts
    document.addEventListener('keydown', (e) => {{
      // Ignore if user is typing in select or inputs
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {{
        return;
      }}

      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {{
        e.preventDefault();
        nextSlide();
      }} else if (e.key === 'ArrowLeft' || e.key === 'Backspace' || e.key === 'PageUp') {{
        e.preventDefault();
        prevSlide();
      }} else if (e.key === 'Home') {{
        e.preventDefault();
        renderSlide(0);
      }} else if (e.key === 'End') {{
        e.preventDefault();
        renderSlide(totalSlides - 1);
      }} else if (e.key === 'f' || e.key === 'F') {{
        e.preventDefault();
        toggleFullscreen();
      }} else if (e.key === 'b' || e.key === 'B' || e.key === '.') {{
        e.preventDefault();
        toggleBlackout();
      }} else if (e.key === 't' || e.key === 'T') {{
        e.preventDefault();
        toggleTimer();
      }} else if (e.key === '?' || e.key === 'h' || e.key === 'H') {{
        e.preventDefault();
        toggleHelp();
      }} else if (e.key === 'Escape') {{
        document.getElementById('zoom-modal').style.display = 'none';
        document.getElementById('help-overlay').style.display = 'none';
        document.getElementById('blackout-screen').style.display = 'none';
      }}
    }});

    // Initialize on load
    initSectionDropdown();
    renderSlide(0);
    resizeViewport();
    startTimer();
  </script>
</body>
</html>
'''

    if os.path.isabs(output_file):
        out_path = output_file
    elif os.path.sep in output_file or '/' in output_file:
        out_path = os.path.abspath(output_file)
    else:
        out_path = os.path.join(slide_dir, output_file)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"[Success] Generated standalone slide deck: {out_path} ({size_mb:.2f} MB)")
    return out_path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export standalone HTML presentation')
    parser.add_argument('--output', '-o', default='standalone.html', help='Output filename (default: standalone.html)')
    args = parser.parse_args()
    build_standalone_html(args.output)
