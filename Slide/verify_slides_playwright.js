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

  const filePath = 'file://' + path.resolve(__dirname, 'index.html');
  console.log(`[Playwright] Opening ${filePath}...`);
  await page.goto(filePath, { waitUntil: 'load' });

  const slideCount = await page.evaluate(() => typeof rawSlides !== 'undefined' ? rawSlides.length : 0);
  console.log(`[Playwright] Found ${slideCount} slides to verify.\n`);

  const results = [];

  for (let i = 0; i < slideCount; i++) {
    await page.evaluate((index) => renderSlide(index), i);
    await page.waitForTimeout(60);

    const slideInfo = await page.evaluate((index) => {
      const body = document.getElementById('slide-body');
      const titleEl = body.querySelector('h1, h2');
      const title = titleEl ? titleEl.innerText.trim() : `Slide ${index + 1}`;

      const images = Array.from(body.querySelectorAll('img')).map(img => ({
        src: img.getAttribute('src'),
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        complete: img.complete,
        isBroken: !img.complete || img.naturalWidth === 0
      }));

      const fullText = body.innerText;
      const latexMatches = fullText.match(/\$[^\$]+\$/g) || [];

      // Check overflow: scrollHeight > clientHeight + 5px margin
      const isOverflow = (body.scrollHeight - body.clientHeight) > 10;

      return {
        index: index + 1,
        title,
        images,
        latexMatches,
        isOverflow,
        scrollHeight: body.scrollHeight,
        clientHeight: body.clientHeight
      };
    }, i);

    results.push(slideInfo);
  }

  await browser.close();

  // Print Summary Report
  console.log('================================================================');
  console.log('                   SLIDE VERIFICATION REPORT                    ');
  console.log('================================================================');

  let totalBrokenImages = 0;
  let totalLatexMatches = 0;
  let totalOverflows = 0;

  results.forEach(s => {
    const brokenImgs = s.images.filter(img => img.isBroken);
    totalBrokenImages += brokenImgs.length;
    totalLatexMatches += s.latexMatches.length;
    if (s.isOverflow) totalOverflows++;

    const imgStatus = s.images.length === 0 
      ? 'No images' 
      : (brokenImgs.length === 0 ? `✅ ${s.images.length} img OK` : `❌ ${brokenImgs.length}/${s.images.length} BROKEN`);

    const latexStatus = s.latexMatches.length === 0
      ? '✅ No raw math'
      : `⚠️ ${s.latexMatches.length} raw LaTeX (${s.latexMatches.join(', ')})`;

    const overflowStatus = s.isOverflow
      ? `⚠️ Overflow (+${s.scrollHeight - s.clientHeight}px)`
      : '✅ Fit';

    console.log(`Slide ${String(s.index).padStart(2, '0')}: [${imgStatus}] [${latexStatus}] [${overflowStatus}] — ${s.title.substring(0, 40)}`);

    if (brokenImgs.length > 0) {
      brokenImgs.forEach(b => console.log(`   --> BROKEN IMAGE SRC: ${b.src}`));
    }
  });

  console.log('================================================================');
  console.log(`Total Slides: ${slideCount}`);
  console.log(`Total Broken Images: ${totalBrokenImages}`);
  console.log(`Total Unrendered LaTeX Matches: ${totalLatexMatches}`);
  console.log(`Total Content Overflows: ${totalOverflows}`);
  console.log(`Console / Page Errors: ${consoleMessages.filter(m => m.type === 'error' || m.type === 'pageerror').length}`);
  console.log('================================================================');
}

main().catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
