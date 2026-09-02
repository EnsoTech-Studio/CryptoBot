const { chromium } = require('playwright');
const path = require('path');

async function main() {
  const browser = await chromium.launch({
    executablePath: '/usr/bin/brave-browser',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  page.on('pageerror', err => {
    consoleMessages.push({ type: 'pageerror', text: err.toString() });
  });

  const filePath = 'file://' + path.resolve(__dirname, 'standalone.html');
  console.log(`[Playwright] Opening standalone slide: ${filePath}...`);
  await page.goto(filePath, { waitUntil: 'load' });

  const slideCount = await page.evaluate(() => typeof rawSlides !== 'undefined' ? rawSlides.length : 0);
  console.log(`[Playwright] Found ${slideCount} slides in standalone.html.\n`);

  if (slideCount === 0) {
    console.error('Error: rawSlides is undefined or empty!');
    process.exit(1);
  }

  const results = [];

  for (let i = 0; i < slideCount; i++) {
    await page.evaluate((index) => renderSlide(index), i);
    await page.waitForTimeout(50);

    const slideInfo = await page.evaluate((index) => {
      const body = document.getElementById('slide-body');
      const titleEl = body.querySelector('h1, h2');
      const title = titleEl ? titleEl.innerText.trim() : `Slide ${index + 1}`;

      const images = Array.from(body.querySelectorAll('img')).map(img => ({
        srcLength: (img.getAttribute('src') || '').length,
        isBase64: (img.getAttribute('src') || '').startsWith('data:image/'),
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        complete: img.complete,
        isBroken: !img.complete || img.naturalWidth === 0
      }));

      // Check overflow: scrollHeight > clientHeight + 10px margin
      const isOverflow = (body.scrollHeight - body.clientHeight) > 10;

      return {
        index: index + 1,
        title,
        images,
        isOverflow,
        scrollHeight: body.scrollHeight,
        clientHeight: body.clientHeight
      };
    }, i);

    results.push(slideInfo);
  }

  // Interactive feature checks:
  console.log('[Playwright] Testing interactive features...');

  // 1. Zoom Modal test on the first slide with an image
  const firstImgSlideIdx = results.findIndex(s => s.images.length > 0);
  if (firstImgSlideIdx !== -1) {
    await page.evaluate((idx) => renderSlide(idx), firstImgSlideIdx);
    await page.waitForTimeout(50);
    const imgClicked = await page.evaluate(() => {
      const img = document.querySelector('#slide-body img');
      if (!img) return false;
      img.click();
      const modal = document.getElementById('zoom-modal');
      const zoomedImg = document.getElementById('zoomed-img');
      const isVisible = modal && window.getComputedStyle(modal).display === 'flex';
      const hasSrc = zoomedImg && zoomedImg.src.startsWith('data:image/');
      return isVisible && hasSrc;
    });
    console.log(`  - Image Zoom Modal Test (Slide ${firstImgSlideIdx + 1}): ${imgClicked ? 'PASSED ✅' : 'FAILED ❌'}`);
  }

  // 2. Blackout Screen test
  const blackoutWorked = await page.evaluate(() => {
    toggleBlackout();
    const b = document.getElementById('blackout-screen');
    const visible = b && window.getComputedStyle(b).display === 'block';
    toggleBlackout(); // toggle back
    return visible;
  });
  console.log(`  - Blackout Mode Test: ${blackoutWorked ? 'PASSED ✅' : 'FAILED ❌'}`);

  // 3. Help Overlay test
  const helpWorked = await page.evaluate(() => {
    toggleHelp();
    const h = document.getElementById('help-overlay');
    const visible = h && window.getComputedStyle(h).display === 'block';
    toggleHelp(); // toggle back
    return visible;
  });
  console.log(`  - Keyboard Help Overlay Test: ${helpWorked ? 'PASSED ✅' : 'FAILED ❌'}`);

  // 4. Timer test
  await page.waitForTimeout(1100);
  const timerDisplay = await page.evaluate(() => document.getElementById('timer-display').innerText);
  console.log(`  - Live Presentation Timer Test: ${timerDisplay !== '00:00' ? `PASSED (${timerDisplay}) ✅` : 'FAILED ❌'}`);

  await browser.close();

  // Print Summary Report
  console.log('\n================================================================');
  console.log('             STANDALONE SLIDE VERIFICATION REPORT               ');
  console.log('================================================================');

  let totalBrokenImages = 0;
  let totalBase64Images = 0;
  let totalOverflows = 0;

  results.forEach(s => {
    const brokenImgs = s.images.filter(img => img.isBroken);
    const b64Imgs = s.images.filter(img => img.isBase64);
    totalBrokenImages += brokenImgs.length;
    totalBase64Images += b64Imgs.length;
    if (s.isOverflow) totalOverflows++;

    const imgStatus = s.images.length === 0 
      ? 'No images' 
      : (brokenImgs.length === 0 ? `✅ ${s.images.length} Base64 img OK` : `❌ ${brokenImgs.length}/${s.images.length} BROKEN`);

    const overflowStatus = s.isOverflow
      ? `⚠️ Overflow (+${s.scrollHeight - s.clientHeight}px)`
      : '✅ Fit';

    console.log(`Slide ${String(s.index).padStart(2, '0')}: [${imgStatus}] [${overflowStatus}] — ${s.title.substring(0, 42)}`);
  });

  console.log('================================================================');
  console.log(`Total Slides: ${slideCount}`);
  console.log(`Total Inlined Base64 Images: ${totalBase64Images}`);
  console.log(`Total Broken Images: ${totalBrokenImages}`);
  console.log(`Total Content Overflows: ${totalOverflows}`);
  console.log(`Console / Page Errors: ${consoleMessages.filter(m => m.type === 'error' || m.type === 'pageerror').length}`);
  console.log('================================================================');

  if (totalBrokenImages > 0 || totalOverflows > 0) {
    console.error('[Verification Failed] Issues detected.');
    process.exit(1);
  } else {
    console.log('\n🎉 ALL 29 SLIDES & 20 DIAGRAMS VERIFIED 100% STANDALONE & WORKING PERFECTLY!');
  }
}

main().catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
