const http = require('http');
const { chromium } = require('playwright');
const DUP = process.argv[2] === 'dup';

const server = http.createServer((req, res) => {
  if (req.url === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end('<html><body><script>fetch("/api/profiles").then(r=>r.text()).then(t=>{document.title="OK:"+t.length}).catch(e=>{document.title="ERR:"+String(e).slice(0,300)})</script></body></html>');
    return;
  }
  const preq = http.request({ host: '127.0.0.1', port: 8010, path: req.url, method: req.method, headers: Object.assign({}, req.headers, { host: '127.0.0.1:8010' }) }, pres => {
    const headers = Object.assign({}, pres.headers);
    console.log('   upstream status=' + pres.statusCode + ' raw=' + JSON.stringify(pres.rawHeaders) + ' origin_in=' + JSON.stringify(req.headers.origin));
    if (DUP) {
      let acao = headers['access-control-allow-origin'];
      if (!acao) acao = req.headers.origin || 'null';
      const arr = Array.isArray(acao) ? acao.slice() : [acao];
      arr.push(acao);
      headers['access-control-allow-origin'] = arr;
    }
    res.writeHead(pres.statusCode, headers);
    pres.pipe(res);
  });
  preq.on('error', e => { res.writeHead(502); res.end(String(e)); });
  req.pipe(preq);
});

server.listen(3002, '127.0.0.1', async () => {
  const acaoReq = http.request({ host: '127.0.0.1', port: 8010, path: '/api/profiles', headers: { Origin: 'http://localhost:3002' } }, r => { r.resume(); r.on('end', () => {}); });
  acaoReq.end();
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const logs = [];
  page.on('console', m => logs.push(m.type() + ': ' + m.text()));
  page.on('requestfailed', r => logs.push('requestfailed: ' + ((r.failure() || {}).errorText || '?')));
  await page.goto('http://localhost:3002/', { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  console.log('MODE=' + (DUP ? 'DUP' : 'CLEAN') + ' title=' + (await page.title()));
  console.log('logs: ' + (logs.join(' | ') || '(none)'));
  await browser.close();
  server.close();
});
