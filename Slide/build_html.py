import os
import re
import json

def build_slides():
    slide_dir = os.path.dirname(os.path.abspath(__file__))
    sections_dir = os.path.join(slide_dir, 'sections')
    
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

    header = '''---
marp: true
theme: default
paginate: true
size: 16:9
header: 'CryptoBot — Software Architecture Presentation'
footer: 'Trường ĐH Khoa học Tự nhiên - ĐHQG-HCM | Bộ môn KTPM'
style: |
  section {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 24px;
    padding: 32px 48px;
    background-color: #ffffff;
    color: #1e293b;
  }
  h1 {
    color: #0f172a;
    font-size: 36px;
    margin-bottom: 12px;
    font-weight: 700;
  }
  h2 {
    color: #1e3a8a;
    font-size: 28px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 14px;
  }
  h3 {
    color: #2563eb;
    font-size: 23px;
    margin-top: 4px;
    margin-bottom: 8px;
  }
  p, li {
    font-size: 22px;
    line-height: 1.45;
  }
  ul {
    margin-top: 4px;
    margin-bottom: 8px;
    padding-left: 24px;
  }
  li {
    margin-bottom: 5px;
  }
  table {
    font-size: 17.5px;
    border-collapse: collapse;
    width: 100%;
    margin-top: 8px;
  }
  th {
    background-color: #f1f5f9;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 18.5px;
  }
  td {
    border: 1px solid #e2e8f0;
    padding: 8px 12px;
    font-size: 17px;
    line-height: 1.4;
  }
  tr:nth-child(even) {
    background-color: #f8fafc;
  }
  .columns {
    display: grid;
    grid-template-columns: 1fr 1.15fr;
    gap: 28px;
    align-items: center;
  }
  .columns-equal {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    align-items: start;
  }
  img {
    max-height: 480px;
    max-width: 100%;
    object-fit: contain;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    background-color: #ffffff;
    display: block;
    margin: 0 auto;
  }
  section.lead {
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  }
  section.lead img {
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
  }
  section.lead .lead-institution {
    margin-top: 0;
    margin-bottom: 14px;
    text-align: center;
  }
  section.lead .lead-uni {
    font-size: 17px;
    font-weight: 700;
    color: #1e293b;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin: 0 0 3px 0;
    line-height: 1.3;
  }
  section.lead .lead-faculty {
    font-size: 15px;
    font-weight: 600;
    color: #2563eb;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0;
    line-height: 1.3;
  }
  section.lead h1 {
    font-size: 42px;
    color: #1e3a8a;
  }
  section.lead h2 {
    border-bottom: none;
    font-size: 24px;
    color: #475569;
  }
---'''

    section_texts = []
    for sec in section_files:
        path = os.path.join(sections_dir, sec)
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read().strip()
            # In main.md (sitting in Slide/), diagrams are at ../blueprint/...
            text_for_main = text.replace('../../blueprint/', '../blueprint/').replace('../selab.jpeg', './selab.jpeg')
            section_texts.append(text_for_main)

    combined = header + '\n\n' + '\n\n---\n\n'.join(section_texts)
    main_md_path = os.path.join(slide_dir, 'main.md')
    with open(main_md_path, 'w', encoding='utf-8') as f:
        f.write(combined)

    # Now parse slides for HTML runner (split strictly on standalone '---' slide boundary)
    parts = re.split(r'\n+---+\s*\n+', combined)
    slides_raw = []
    for p in parts:
        p_str = p.strip()
        if not p_str or p_str.startswith('marp: true') or p_str.startswith('style:') or 'paginate: true' in p_str:
            continue
        slides_raw.append(p_str)

    slides_json = json.dumps(slides_raw, ensure_ascii=False)

    html_content = f'''<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CryptoBot — Software Architecture Presentation</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
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
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
      padding: 10px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1f2937;
      font-size: 14px;
      z-index: 100;
    }}
    .header-title {{
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
      color: #93c5fd;
    }}
    .header-badge {{
      background: #2563eb;
      color: #ffffff;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }}
    .header-controls {{
      display: flex;
      gap: 12px;
      align-items: center;
    }}
    button.btn-ctrl {{
      background: #1f2937;
      border: 1px solid #374151;
      color: #f8fafc;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
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
    select.nav-select {{
      background: #1f2937;
      color: #f8fafc;
      border: 1px solid #374151;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 13px;
      max-width: 360px;
      cursor: pointer;
    }}

    /* Main Presentation Stage */
    #stage {{
      flex: 1;
      display: flex;
      justify-content: center;
      align-items: center;
      position: relative;
      background: #0b1120;
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
      transition: transform 0.1s ease;
    }}

    .slide-body {{
      flex: 1;
      padding: 32px 48px 20px 48px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
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

    /* Two Column Layout */
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
      transform: scale(1.012);
      box-shadow: 0 8px 20px rgba(30, 58, 138, 0.12);
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
      padding: 8px 24px;
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

    /* Modal for Image Zoom */
    #zoom-modal {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(4px);
      z-index: 1000;
      justify-content: center;
      align-items: center;
      cursor: zoom-out;
    }}
    #zoom-modal img {{
      max-width: 92vw;
      max-height: 92vh;
      object-fit: contain;
      border-radius: 8px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.5);
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
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
      z-index: 500;
      font-size: 14px;
    }}
    #help-overlay h3 {{
      color: #93c5fd;
      margin-bottom: 12px;
      font-size: 18px;
    }}
    #help-overlay table {{
      border-collapse: collapse;
      width: 100%;
    }}
    #help-overlay td {{
      padding: 6px 12px;
      border-bottom: 1px solid #374151;
    }}
    #help-overlay kbd {{
      background: #111827;
      border: 1px solid #374151;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
      color: #60a5fa;
    }}
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="header-title">
      <span>📈 Crypto Strategy Lab</span>
      <span class="header-badge">Software Architecture Presentation</span>
    </div>
    <div class="header-controls">
      <select id="section-select" class="nav-select" onchange="jumpToSlide(parseInt(this.value))">
        <!-- Injected via JS -->
      </select>
      <button class="btn-ctrl" onclick="toggleHelp()">⌨️ Phím tắt (?)</button>
      <button class="btn-ctrl" onclick="toggleFullscreen()">⛶ Toàn màn hình (F)</button>
    </div>
  </header>

  <!-- Slide Canvas -->
  <main id="stage">
    <div id="slide-viewport">
      <div id="slide-body" class="slide-body">
        <!-- Rendered markdown content -->
      </div>
      <div class="slide-footer">
        <span>Crypto Strategy Lab — Architecture Presentation</span>
        <span id="slide-counter">Slide 1 / 39</span>
        <span>Trường ĐH Khoa học Tự nhiên - ĐHQG-HCM</span>
      </div>
    </div>
  </main>

  <!-- Bottom Navigation Bar -->
  <footer class="bottom-bar">
    <button class="btn-ctrl" onclick="prevSlide()">◀ Trang trước (←)</button>
    <div class="progress-track" onclick="seekSlide(event)">
      <div id="progress-fill" class="progress-bar"></div>
    </div>
    <span id="slide-indicator" style="font-family: monospace; font-weight: 600;">1 / 39</span>
    <button class="btn-ctrl" onclick="nextSlide()">Trang sau (→) ▶</button>
  </footer>

  <!-- Image Zoom Modal -->
  <div id="zoom-modal" onclick="this.style.display='none'">
    <img id="zoomed-img" src="" alt="Zoomed diagram">
  </div>

  <!-- Keyboard Help Modal -->
  <div id="help-overlay" onclick="this.style.display='none'">
    <h3>⌨️ Phím tắt điều khiển trình chiếu</h3>
    <table>
      <tr><td><kbd>→</kbd> hoặc <kbd>Space</kbd> hoặc <kbd>PageDown</kbd></td><td>Chuyển slide kế tiếp</td></tr>
      <tr><td><kbd>←</kbd> hoặc <kbd>Backspace</kbd> hoặc <kbd>PageUp</kbd></td><td>Quay lại slide trước</td></tr>
      <tr><td><kbd>Home</kbd> / <kbd>End</kbd></td><td>Về slide đầu / slide cuối</td></tr>
      <tr><td><kbd>F</kbd></td><td>Bật / tắt chế độ toàn màn hình</td></tr>
      <tr><td><kbd>?</kbd> hoặc <kbd>H</kbd></td><td>Bật / tắt bảng hướng dẫn phím tắt</td></tr>
      <tr><td><kbd>Click ảnh sơ đồ</kbd></td><td>Phóng to sơ đồ kiến trúc HD</td></tr>
    </table>
  </div>

  <script>
    const rawSlides = {slides_json};
    let currentSlide = 0;
    const totalSlides = rawSlides.length;

    // Custom marked renderer for images and lead class
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
      return `<img src="${{href}}" alt="${{alt || ''}}" title="${{t || ''}}" onclick="zoomImage(this.src)" />`;
    }};

    marked.setOptions({{
      renderer: renderer,
      gfm: true,
      breaks: true
    }});

    function resizeViewport() {{
      const stage = document.getElementById('stage');
      const viewport = document.getElementById('slide-viewport');
      const targetW = 1280;
      const targetH = 720;
      
      const availableW = stage.clientWidth - 32;
      const availableH = stage.clientHeight - 32;
      
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
        opt.textContent = `${{idx + 1}}. ${{title.substring(0, 45)}}`;
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

      if (window.renderMathInElement) {{
        try {{
          renderMathInElement(slideBody, {{
            delimiters: [
              {{left: '$$', right: '$$', display: true}},
              {{left: '$', right: '$', display: false}}
            ],
            throwOnError: false
          }});
        }} catch(e) {{
          console.warn('Math render error:', e);
        }}
      }}

      document.getElementById('slide-counter').textContent = `Slide ${{currentSlide + 1}} / ${{totalSlides}}`;
      document.getElementById('slide-indicator').textContent = `${{currentSlide + 1}} / ${{totalSlides}}`;
      document.getElementById('progress-fill').style.width = `${{((currentSlide + 1) / totalSlides) * 100}}%`;
      document.getElementById('section-select').value = currentSlide;
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
      const pct = clickX / rect.width;
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

    function zoomImage(src) {{
      const modal = document.getElementById('zoom-modal');
      const img = document.getElementById('zoomed-img');
      img.src = src;
      modal.style.display = 'flex';
    }}

    function toggleHelp() {{
      const help = document.getElementById('help-overlay');
      help.style.display = help.style.display === 'block' ? 'none' : 'block';
    }}

    document.addEventListener('keydown', (e) => {{
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
        toggleFullscreen();
      }} else if (e.key === '?' || e.key === 'h' || e.key === 'H') {{
        toggleHelp();
      }} else if (e.key === 'Escape') {{
        document.getElementById('zoom-modal').style.display = 'none';
        document.getElementById('help-overlay').style.display = 'none';
      }}
    }});

    // Initialize
    initSectionDropdown();
    renderSlide(0);
    resizeViewport();
  </script>
</body>
</html>
'''

    out_path = os.path.join(slide_dir, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f'Combined {len(section_files)} sections into main.md and built index.html ({len(slides_raw)} slides) successfully!')

    # Also build standalone.html
    try:
        from export_standalone import build_standalone_html
        build_standalone_html('standalone.html')
    except Exception as e:
        print(f'[Warning] Failed to generate standalone.html: {e}')

if __name__ == '__main__':
    build_slides()
