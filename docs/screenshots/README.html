<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Synthetic Identity Fraud Detection</title>
<meta name="description" content="Synthetic identity fraud ring detection: a data pipeline, an explainable risk model, and an analyst console." />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#f6f7fb;
    --surface:#ffffff;
    --surface-2:#f1f3f9;
    --border:#e3e6ef;
    --text:#171a2b;
    --text-2:#565c74;
    --text-3:#8790ab;
    --accent:#4f46e5;
    --accent-2:#6d28d9;
    --accent-soft:#eef0ff;
    --good:#0d9488;
    --good-soft:#e6fbf8;
    --warn:#b45309;
    --warn-soft:#fef3e0;
    --danger:#be123c;
    --danger-soft:#fde8ee;
    --code-bg:#11132a;
    --code-text:#e7e9ff;
    --shadow:0 1px 2px rgba(15,15,40,.04), 0 8px 24px -12px rgba(15,15,40,.12);
    --radius:14px;
    --maxw:1180px;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --bg:#0b0c14;
      --surface:#12131f;
      --surface-2:#171927;
      --border:#262841;
      --text:#eceef7;
      --text-2:#a8adc7;
      --text-3:#767c9c;
      --accent:#8b83ff;
      --accent-2:#a78bfa;
      --accent-soft:#1c1b3a;
      --good:#34d1bf;
      --good-soft:#0e2b2a;
      --warn:#f0b355;
      --warn-soft:#2c2312;
      --danger:#fb7185;
      --danger-soft:#2b1420;
      --code-bg:#080915;
      --code-text:#dfe2ff;
      --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 28px -14px rgba(0,0,0,.55);
    }
  }
  *{box-sizing:border-box;}
  html{scroll-behavior:smooth;}
  body{
    margin:0;
    background:
      radial-gradient(1100px 480px at 12% -8%, var(--accent-soft), transparent 60%),
      var(--bg);
    color:var(--text);
    font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    line-height:1.65;
    font-size:16px;
    -webkit-font-smoothing:antialiased;
  }
  a{color:var(--accent);text-decoration:none;}
  a:hover{text-decoration:underline;}
  code, pre, kbd{
    font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  }
  code{
    background:var(--surface-2);
    border:1px solid var(--border);
    padding:.12em .42em;
    border-radius:6px;
    font-size:.86em;
    color:var(--accent-2);
  }
  pre{
    background:var(--code-bg);
    color:var(--code-text);
    border-radius:12px;
    padding:18px 20px;
    overflow-x:auto;
    font-size:.86rem;
    line-height:1.6;
    box-shadow:var(--shadow);
    border:1px solid rgba(255,255,255,.05);
  }
  pre code{background:none;border:none;padding:0;color:inherit;font-size:1em;}

  /* ---- Layout shell ---- */
  .topbar{
    position:sticky;top:0;z-index:40;
    backdrop-filter:saturate(180%) blur(14px);
    background:color-mix(in srgb, var(--bg) 78%, transparent);
    border-bottom:1px solid var(--border);
  }
  .topbar-inner{
    max-width:var(--maxw);margin:0 auto;padding:12px 24px;
    display:flex;align-items:center;gap:14px;
  }
  .topbar .brand{display:flex;align-items:center;gap:10px;font-weight:700;color:var(--text);white-space:nowrap;}
  .topbar .brand svg{flex:none;}
  .topbar-links{display:flex;gap:4px;margin-left:auto;overflow-x:auto;scrollbar-width:none;}
  .topbar-links::-webkit-scrollbar{display:none;}
  .topbar-links a{
    font-size:.82rem;font-weight:600;color:var(--text-2);
    padding:7px 11px;border-radius:999px;white-space:nowrap;
  }
  .topbar-links a:hover{background:var(--surface-2);color:var(--text);text-decoration:none;}

  .hero{
    max-width:var(--maxw);margin:0 auto;padding:56px 24px 28px;
  }
  .eyebrow{
    display:inline-flex;align-items:center;gap:8px;
    font-size:.76rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
    color:var(--accent);background:var(--accent-soft);
    padding:6px 12px;border-radius:999px;margin-bottom:18px;
  }
  h1{font-size:clamp(2rem,4.4vw,3.05rem);line-height:1.08;letter-spacing:-.02em;margin:0 0 18px;font-weight:800;}
  h1 .accent{
    background:linear-gradient(90deg,var(--accent),var(--accent-2));
    -webkit-background-clip:text;background-clip:text;color:transparent;
  }
  .lede{font-size:1.14rem;color:var(--text-2);max-width:820px;margin:0 0 30px;}
  .badges{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:34px;}
  .badge{
    display:inline-flex;align-items:center;gap:6px;
    font-size:.78rem;font-weight:600;color:var(--text-2);
    background:var(--surface);border:1px solid var(--border);
    padding:6px 12px;border-radius:999px;
  }
  .badge b{color:var(--text);}
  .hero-figure{
    border-radius:var(--radius);overflow:hidden;border:1px solid var(--border);
    box-shadow:var(--shadow);background:var(--surface);
  }
  .hero-figure img{display:block;width:100%;height:auto;}

  .layout{
    max-width:var(--maxw);margin:0 auto;padding:8px 24px 100px;
    display:grid;grid-template-columns:230px minmax(0,1fr);gap:44px;
  }
  .toc{align-self:start;position:sticky;top:78px;}
  .toc-title{font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--text-3);margin:0 0 12px 4px;}
  .toc ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px;counter-reset:toc;}
  .toc a{
    counter-increment:toc;
    display:flex;gap:9px;font-size:.86rem;color:var(--text-2);font-weight:500;
    padding:7px 10px;border-radius:8px;
  }
  .toc a::before{
    content:counter(toc);
    flex:none;width:18px;height:18px;border-radius:5px;
    background:var(--surface-2);color:var(--text-3);
    font-size:.68rem;font-weight:700;display:flex;align-items:center;justify-content:center;
  }
  .toc a:hover{background:var(--surface-2);color:var(--text);text-decoration:none;}

  main{min-width:0;}
  section{
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:var(--radius);
    box-shadow:var(--shadow);
    padding:34px clamp(20px,4vw,44px);
    margin-bottom:26px;
    scroll-margin-top:78px;
  }
  section > h2:first-child{margin-top:0;}
  h2{
    font-size:1.5rem;letter-spacing:-.01em;margin:0 0 6px;
    display:flex;align-items:center;gap:10px;
  }
  .sec-index{
    font-family:"JetBrains Mono",monospace;font-size:.78rem;font-weight:600;
    color:var(--accent);background:var(--accent-soft);
    width:30px;height:30px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex:none;
  }
  h2 + .kicker{color:var(--text-3);font-size:.92rem;margin:0 0 22px;}
  h3{font-size:1.08rem;margin:28px 0 10px;color:var(--text);}
  h3:first-of-type{margin-top:6px;}
  p{margin:0 0 14px;color:var(--text);}
  section p, section li{color:var(--text-2);}
  section li strong, section p strong{color:var(--text);}
  ul, ol{margin:0 0 14px;padding-left:1.25em;}
  li{margin-bottom:6px;}
  hr{border:none;border-top:1px solid var(--border);margin:26px 0;}

  .table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px;margin:16px 0 22px;}
  table{width:100%;border-collapse:collapse;font-size:.88rem;min-width:520px;}
  thead th{
    text-align:left;background:var(--surface-2);color:var(--text-3);
    font-size:.72rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
    padding:11px 14px;border-bottom:1px solid var(--border);white-space:nowrap;
  }
  tbody td{padding:11px 14px;border-bottom:1px solid var(--border);color:var(--text-2);vertical-align:top;}
  tbody tr:last-child td{border-bottom:none;}
  tbody tr:hover{background:var(--surface-2);}
  td strong, th strong{color:var(--text);}
  .num{text-align:right;font-variant-numeric:tabular-nums;font-family:"JetBrains Mono",monospace;}

  .callout{
    border-radius:12px;padding:16px 18px;margin:16px 0;
    border:1px solid var(--border);background:var(--surface-2);
    font-size:.92rem;color:var(--text-2);
  }
  .callout.good{background:var(--good-soft);border-color:color-mix(in srgb, var(--good) 35%, var(--border));}
  .callout.warn{background:var(--warn-soft);border-color:color-mix(in srgb, var(--warn) 35%, var(--border));}
  .callout strong{color:var(--text);}

  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0;}
  .shot{
    border-radius:12px;overflow:hidden;border:1px solid var(--border);
    box-shadow:var(--shadow);background:var(--surface-2);
  }
  .shot img{display:block;width:100%;height:auto;}
  .shot figcaption{padding:9px 13px;font-size:.78rem;color:var(--text-3);border-top:1px solid var(--border);}

  .flow{
    display:flex;flex-wrap:wrap;align-items:center;gap:10px;
    padding:20px;border:1px dashed var(--border);border-radius:12px;background:var(--surface-2);
    margin:16px 0 22px;font-size:.86rem;
  }
  .flow .step{
    background:var(--surface);border:1px solid var(--border);border-radius:9px;
    padding:8px 12px;font-weight:600;color:var(--text);white-space:nowrap;
  }
  .flow .arrow{color:var(--text-3);font-weight:700;}
  .flow .step.accent{border-color:transparent;background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;}

  .stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0 22px;}
  .stat{
    border:1px solid var(--border);border-radius:12px;padding:16px 16px;background:var(--surface-2);
  }
  .stat .n{font-family:"JetBrains Mono",monospace;font-size:1.5rem;font-weight:700;color:var(--accent-2);display:block;}
  .stat .l{font-size:.78rem;color:var(--text-3);margin-top:2px;}

  .pill-list{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;}
  .pill{
    font-size:.78rem;font-weight:600;color:var(--text-2);background:var(--surface-2);
    border:1px solid var(--border);padding:5px 11px;border-radius:999px;
  }

  footer{
    max-width:var(--maxw);margin:0 auto;padding:10px 24px 70px;
    color:var(--text-3);font-size:.82rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;
  }

  @media (max-width:920px){
    .layout{grid-template-columns:1fr;}
    .toc{position:static;order:2;margin-top:8px;}
    .toc ol{flex-direction:row;flex-wrap:wrap;}
    .toc a{background:var(--surface);border:1px solid var(--border);}
    main{order:1;}
    .grid-2{grid-template-columns:1fr;}
    .topbar-links{display:none;}
  }

  @media print{
    .topbar, .toc{display:none;}
    body{background:#fff;}
    section{box-shadow:none;border:1px solid #ddd;break-inside:avoid;}
    .hero{padding-top:10px;}
    a{color:#000;text-decoration:underline;}
  }
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-inner">
    <span class="brand">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
        <path d="M9 10L23 10L16 23Z" fill="none" stroke="var(--text-2)" stroke-width="2.4"/>
        <circle cx="9" cy="10" r="4.6" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>
        <circle cx="23" cy="10" r="4.6" fill="#e11d48" stroke="var(--surface)" stroke-width="2"/>
        <circle cx="16" cy="23" r="4.6" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>
      </svg>
      Fraud Ring Console
    </span>
    <nav class="topbar-links">
      <a href="#quick-start">Quick start</a>
      <a href="#what-the-console-does">Console</a>
      <a href="#how-it-works">How it works</a>
      <a href="#results">Results</a>
      <a href="#testing">Testing</a>
      <a href="#project-layout">Layout</a>
    </nav>
  </div>
</div>

<div class="hero">
  <span class="eyebrow">● README — analyst console &amp; detection pipeline</span>
  <h1>Synthetic Identity <span class="accent">Fraud Ring Detection</span></h1>
  <p class="lede">
    Fraud rings build synthetic identities and reuse the same phone numbers, emails, addresses and devices
    across many fake accounts. This project detects those rings. It generates a realistic synthetic dataset,
    builds a customer identity graph from shared attributes, trains models on network and behaviour features,
    and ships an <strong>analyst console</strong>. The console scores every customer, explains each score in
    plain English, surfaces suspected fraud rings for review, and feeds analyst decisions back into the model.
    It also works on <strong>your own data</strong> &mdash; upload a CSV in whatever format you have, and the
    app detects the columns, links customers through shared identifiers, and shows the fraud rings, even
    without fraud labels.
  </p>
  <div class="badges">
    <span class="badge"><b>Python</b> 3.11+</span>
    <span class="badge"><b>Node.js</b> 20.19+</span>
    <span class="badge">FastAPI</span>
    <span class="badge">React + TypeScript + Vite</span>
    <span class="badge">scikit-learn</span>
    <span class="badge">Cytoscape.js</span>
    <span class="badge">SQLite</span>
    <span class="badge">networkx</span>
  </div>
  <figure class="hero-figure">
    <img src="docs/screenshots/overview.png" alt="Overview dashboard screenshot" loading="lazy" />
  </figure>
</div>

<div class="layout">
  <nav class="toc" aria-label="Table of contents">
    <p class="toc-title">Contents</p>
    <ol>
      <li><a href="#quick-start">Quick start</a></li>
      <li><a href="#using-your-own-data">Using your own data</a></li>
      <li><a href="#what-the-console-does">What the console does</a></li>
      <li><a href="#how-it-works">How it works</a></li>
      <li><a href="#results">Results</a></li>
      <li><a href="#research-pipeline">Research pipeline</a></li>
      <li><a href="#contrastive">Contrastive pretraining</a></li>
      <li><a href="#testing">Testing</a></li>
      <li><a href="#demo-script">Demo script</a></li>
      <li><a href="#future-work">Future work</a></li>
      <li><a href="#project-layout">Project layout</a></li>
    </ol>
  </nav>

  <main>

    <section id="quick-start">
      <h2><span class="sec-index">01</span>Quick start</h2>
      <p class="kicker">Requirements: Python 3.11+, Node.js 20.19+ (only to build the frontend).</p>

      <pre><code>python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
npm run build                    # creates frontend/dist, served by the backend
cd ..

python -m backend                # open http://127.0.0.1:8000</code></pre>

      <p>The first screen offers two paths: <strong>Generate and analyse</strong> (the synthetic demo, about a
      minute) or <strong>Upload a CSV</strong>. To have data ready before a demo, preload it from the command line:</p>

      <pre><code>python -m backend.cli demo                                   # synthetic dataset, seed 42
python -m backend.cli analyze sample_data/bank_customers_unlabeled.csv --name "Bank export"
python -m backend.cli list</code></pre>

      <p><strong>Development mode</strong> (hot reload for both halves):</p>
      <pre><code>python -m backend --reload       # API on :8000
cd frontend && npm run dev       # UI on http://localhost:5173 (proxies /api to :8000)</code></pre>

      <div class="callout">
        Interactive API docs are at <code>http://127.0.0.1:8000/docs</code>. Everything the app stores
        (SQLite database, uploads, generated datasets) lives in <code>storage/</code>, which is git-ignored;
        delete the folder to start fresh, or set <code>FRAUD_APP_STORAGE</code> to use another location.
      </div>
    </section>

    <section id="using-your-own-data">
      <h2><span class="sec-index">02</span>Using your own data</h2>
      <p>Upload on <strong>Datasets &amp; uploads</strong> (or use <code>python -m backend.cli analyze file.csv</code>).</p>

      <div class="table-wrap"><table>
        <thead><tr><th>File</th><th>Required</th><th>Shape</th></tr></thead>
        <tbody>
          <tr><td><strong>Customers</strong></td><td>yes</td><td>One row per customer. Any column names.</td></tr>
          <tr><td><strong>Account events</strong></td><td>no</td><td>One row per event: customer ID and date; optionally event type, credit utilization and credit limit.</td></tr>
          <tr><td><strong>Identity links</strong></td><td>no</td><td>Long format: customer ID, attribute type (<code>phone</code>, <code>email</code>, &hellip;), attribute value. This is the format of <code>data/raw/customer_attribute_links.csv</code>.</td></tr>
        </tbody>
      </table></div>

      <p><strong>Column roles are detected automatically</strong> from names and values, and you can change any of them before running:</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Role</th><th>Examples it recognises</th><th>Used for</th></tr></thead>
        <tbody>
          <tr><td>Customer ID</td><td><code>customer_id</code>, <code>Client ID</code>, <code>CUST_NO</code></td><td>Row identity; duplicate IDs are merged.</td></tr>
          <tr><td>Phone / email / address / device / IP / national ID / bank account / other identifier</td><td><code>Mobile Number</code>, <code>E-mail</code>, <code>Street Address</code> + <code>City</code> + <code>ZIP</code>, <code>Device ID</code>, <code>ip_address</code>, <code>SSN</code>, <code>IBAN</code></td><td>Linking customers into the identity graph.</td></tr>
          <tr><td>Fraud label</td><td><code>is_fraud</code>, <code>Fraud Flag</code> with 1/0, yes/no, true/false, fraud/legit</td><td>Training or evaluation (your choice).</td></tr>
          <tr><td>Known ring ID</td><td><code>ring_id</code>, <code>Ring Ref</code></td><td>Evaluation only, never a feature.</td></tr>
          <tr><td>Account open date</td><td><code>account_open_date</code>, <code>signup_date</code></td><td>Derives account age.</td></tr>
          <tr><td>Numeric feature</td><td><code>annual_income</code>, <code>credit_score</code>, <code>$45,000</code></td><td>Model input when you train on your labels.</td></tr>
        </tbody>
      </table></div>

      <p><strong>Identity values are normalised before matching</strong>:</p>
      <ul>
        <li>Phone numbers are compared by digits, so <code>(555) 123-4567</code> matches <code>+1 555.123.4567</code>.</li>
        <li>Emails and addresses are compared case-insensitively, and addresses are abbreviated (<code>Street</code> &rarr; <code>st</code>).</li>
        <li>Placeholders such as <code>N/A</code>, <code>unknown</code> or <code>000-000-0000</code> are dropped.</li>
        <li>National IDs and bank accounts are stored as hashes and shown masked.</li>
      </ul>

      <p>Split address columns (street, city, state, ZIP) are combined into one address. A city on its own is
      never used as a link. Any value shared by more than 50 customers, such as an office address or a
      placeholder, is reported and <strong>not</strong> turned into links, because that would glue unrelated
      people into one giant &ldquo;ring&rdquo;.</p>

      <p><strong>Labels are optional.</strong></p>
      <ul>
        <li><strong>No label column:</strong> customers are scored by a model trained on the synthetic reference dataset, using exactly the kinds of data your file has. For example, if your file has phone and email but no device, the reference model is retrained on phone and email features only. Rings are still found from your identity graph.</li>
        <li><strong>Label column, &ldquo;train&rdquo; mode:</strong> a model is trained on your labels. Scores are out-of-fold from ring-aware cross-validation, so no customer is scored by a model that saw its own label.</li>
        <li><strong>Label column, &ldquo;evaluate only&rdquo; mode:</strong> labels are hidden from the model and used only to report how well it did.</li>
      </ul>
      <p>Analyst decisions become training labels in every mode.</p>

      <div class="callout good">
        <strong>Sample files</strong> in a deliberately different format live in <code>sample_data/</code>.
        They come from a different synthetic population (seed 7, 1,650 customers) and have messy phone
        formats, split addresses, <code>$</code> incomes, Yes/No labels and a 60-person office address. The
        upload page can load them with one click. Regenerate them with <code>python -m scripts.make_sample_data</code>.
      </div>
    </section>

    <section id="what-the-console-does">
      <h2><span class="sec-index">03</span>What the console does</h2>

      <div class="table-wrap"><table>
        <thead><tr><th>Page</th><th>What you get</th></tr></thead>
        <tbody>
          <tr><td><strong>Overview</strong></td><td>Suspected rings, high-risk count, model quality, risk-score distribution with the alert threshold, what drives the scores, ring-detection accuracy against known labels, top rings and customers, data-quality notes.</td></tr>
          <tr><td><strong>Fraud-ring review</strong></td><td>Queue of suspected rings, highest score first. Each ring shows a plain-English summary, an interactive graph, the exact shared values (&ldquo;email <code>x@&hellip;</code> used by 6 of 6&rdquo;), members with risk and reasons, and per-member tick boxes. <strong>Confirm</strong> or <strong>Dismiss</strong> with an audit note; the queue auto-advances to the next ring.</td></tr>
          <tr><td><strong>Network graph</strong></td><td>All suspected rings (or all linked groups) as an interactive graph. Filter by ring score, link type and review status; colour by model risk or known labels; click for details, double-click to open a customer.</td></tr>
          <tr><td><strong>Customers</strong></td><td>Searchable, sortable, paginated list with each customer&rsquo;s main reason.</td></tr>
          <tr><td><strong>Customer detail</strong></td><td>Risk score against the threshold, a plain-English explanation, a factor chart showing how each fact moved the score, a connection graph, linked accounts with the exact shared values, identity details, account activity over time, all feature values, and an analyst decision.</td></tr>
          <tr><td><strong>Model &amp; metrics</strong></td><td>ROC and precision-recall curves, confusion matrix, precision/recall for the top K, the feature-set comparison (profile vs network vs behaviour), feature importance, graph statistics, and the model version history with a like-for-like comparison after each retrain.</td></tr>
          <tr><td><strong>Datasets &amp; uploads</strong></td><td>Upload wizard with column mapping, synthetic generator, dataset list and recent jobs.</td></tr>
        </tbody>
      </table></div>

      <p>Jobs report <strong>live progress</strong> stage by stage (Server-Sent Events with a polling
      fallback). <strong>Retrain with feedback</strong> appears as soon as there are new review decisions;
      ring IDs stay the same across versions. Scores can be exported as CSV.</p>

      <div class="grid-2">
        <figure class="shot"><img src="docs/screenshots/ring-review.png" alt="Ring review screen" loading="lazy"><figcaption>Fraud-ring review screen</figcaption></figure>
        <figure class="shot"><img src="docs/screenshots/customer.png" alt="Customer detail" loading="lazy"><figcaption>Customer detail</figcaption></figure>
        <figure class="shot"><img src="docs/screenshots/network.png" alt="Network graph" loading="lazy"><figcaption>Network graph</figcaption></figure>
        <figure class="shot"><img src="docs/screenshots/metrics.png" alt="Model metrics" loading="lazy"><figcaption>Model &amp; metrics</figcaption></figure>
      </div>
    </section>

    <section id="how-it-works">
      <h2><span class="sec-index">04</span>How it works</h2>

      <div class="flow">
        <span class="step">upload / generate</span><span class="arrow">&rarr;</span>
        <span class="step">ingest &amp; normalise</span><span class="arrow">&rarr;</span>
        <span class="step">identity graph</span><span class="arrow">&rarr;</span>
        <span class="step">features</span><span class="arrow">&rarr;</span>
        <span class="step accent">model</span><span class="arrow">&rarr;</span>
        <span class="step">explanations</span><span class="arrow">&rarr;</span>
        <span class="step">ring review</span><span class="arrow">&rarr;</span>
        <span class="step">analyst decisions</span><span class="arrow">&rarr;</span>
        <span class="step accent">retrain</span><span class="arrow">&rarr;</span>
        <span class="step">SQLite</span><span class="arrow">&rarr;</span>
        <span class="step">React console</span>
      </div>

      <div class="table-wrap"><table>
        <thead><tr><th>Stage</th><th>Code</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>Ingest</td><td><code>backend/pipeline/ingest.py</code></td><td>Column-role detection, value normalisation, canonical customers / links / events.</td></tr>
          <tr><td>Identity graph</td><td><code>src/data/build_customer_graph.py</code></td><td>Customers sharing any attribute value are linked; per-type flags on every edge.</td></tr>
          <tr><td>Features</td><td><code>src/data/generate_red_flag_features.py</code>, <code>generate_temporal_features.py</code></td><td>Network red flags (shared phone/email/address/device counts, degree) and behaviour over time (event bursts, utilization spikes, gaps). Both are vectorised and produce exactly the same values as the original implementations.</td></tr>
          <tr><td>Model</td><td><code>backend/pipeline/modeling.py</code></td><td>Class-balanced <code>HistGradientBoostingClassifier</code>. <strong>Supervised mode:</strong> out-of-fold scores from 5-fold <code>StratifiedGroupKFold</code> (known rings or connected components kept together), plus the research experiment table. <strong>Transfer mode:</strong> a model trained on the synthetic reference dataset with the same feature definitions as the upload, plus analyst labels weighted 5&times;. The alert threshold maximises F1.</td></tr>
          <tr><td>Explanations</td><td><code>backend/pipeline/explain.py</code></td><td><strong>Baseline Shapley values</strong>, estimated by permutation sampling with antithetic orders. Each factor&rsquo;s contribution is how much it moved the score away from a typical legitimate customer, and contributions add up exactly to the score. Contributions become sentences with the customer&rsquo;s real values: <em>&ldquo;High risk (100/100): flagged because it is linked to 8 other accounts through shared identity details, shares an email address with 6 other accounts&hellip;&rdquo;</em>. Graph context (ring membership, how many linked accounts are high risk, analyst decisions) is added.</td></tr>
          <tr><td>Rings</td><td><code>backend/pipeline/rings.py</code></td><td>Connected groups of linked customers (groups above 30 are split with Louvain). A group is a <strong>suspected ring</strong> when at least two members are high risk or the average member risk is above the threshold. Ring IDs depend only on the graph, so they are stable when the model is retrained.</td></tr>
          <tr><td>Jobs &amp; API</td><td><code>backend/jobs.py</code>, <code>backend/main.py</code></td><td>Background worker with per-stage progress in SQLite; FastAPI REST API and an SSE stream per job.</td></tr>
          <tr><td>Database</td><td><code>backend/db.py</code></td><td>SQLite: datasets, jobs, model runs (all metrics), customers (score, explanation, features, identity details), edges, rings, reviews, events.</td></tr>
          <tr><td>Frontend</td><td><code>frontend/</code></td><td>React + TypeScript + Vite. The graph uses Cytoscape.js (fcose for single networks, a packed-ring layout for hundreds of separate rings). Charts are hand-built SVG with hover tooltips. Light and dark themes.</td></tr>
        </tbody>
      </table></div>

      <div class="callout">
        <strong>Feedback loop.</strong> A confirmed ring labels its ticked members as fraud; a dismissal
        labels them legitimate; the latest decision wins. Retraining creates a new model version.
        <br>&bull; <strong>Transfer mode:</strong> the labels are added to the reference training data.
        <br>&bull; <strong>Supervised mode:</strong> the labels override the dataset&rsquo;s own labels.
        <br>Each version records how many customers changed risk level and which rings became or stopped
        being suspected. It also re-scores the previous version on exactly the same customers, so
        version-to-version metrics are like-for-like.
      </div>
    </section>

    <section id="results">
      <h2><span class="sec-index">05</span>Results</h2>

      <h3>Research experiments <span style="font-weight:400;color:var(--text-3);">&mdash; synthetic dataset, ring-aware 80/20 split</span></h3>
      <p>Test set: 1,776 customers including 180 fraud customers. The same table is reproduced by the app for any labelled dataset.</p>

      <div class="table-wrap"><table>
        <thead><tr><th>Model</th><th>Feature set</th><th class="num">Accuracy</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">F1</th><th class="num">ROC-AUC</th><th class="num">PR-AUC</th></tr></thead>
        <tbody>
          <tr><td>Random Forest</td><td>Tabular</td><td class="num">0.8682</td><td class="num">0.1029</td><td class="num">0.0389</td><td class="num">0.0565</td><td class="num">0.4911</td><td class="num">0.1002</td></tr>
          <tr><td>HistGradientBoosting</td><td>Tabular</td><td class="num">0.7095</td><td class="num">0.0922</td><td class="num">0.2111</td><td class="num">0.1284</td><td class="num">0.4746</td><td class="num">0.0965</td></tr>
          <tr><td>Random Forest</td><td>Tabular + Network</td><td class="num">0.9623</td><td class="num">0.8509</td><td class="num">0.7611</td><td class="num">0.8035</td><td class="num">0.9153</td><td class="num">0.8373</td></tr>
          <tr><td>HistGradientBoosting</td><td>Tabular + Network</td><td class="num">0.9600</td><td class="num">0.8263</td><td class="num">0.7667</td><td class="num">0.7954</td><td class="num">0.9184</td><td class="num">0.8398</td></tr>
          <tr><td>Random Forest</td><td>Tabular + Temporal</td><td class="num">0.9482</td><td class="num">0.8929</td><td class="num">0.5556</td><td class="num">0.6849</td><td class="num">0.7888</td><td class="num">0.6575</td></tr>
          <tr><td>HistGradientBoosting</td><td>Tabular + Temporal</td><td class="num">0.9403</td><td class="num">0.7500</td><td class="num">0.6167</td><td class="num">0.6768</td><td class="num">0.7853</td><td class="num">0.6816</td></tr>
          <tr><td><strong>Random Forest</strong></td><td><strong>Combined</strong></td><td class="num">0.9707</td><td class="num">0.9051</td><td class="num">0.7944</td><td class="num">0.8462</td><td class="num">0.9396</td><td class="num">0.8915</td></tr>
          <tr><td><strong>HistGradientBoosting</strong></td><td><strong>Combined</strong></td><td class="num"><strong>0.9747</strong></td><td class="num">0.8947</td><td class="num"><strong>0.8500</strong></td><td class="num"><strong>0.8718</strong></td><td class="num"><strong>0.9457</strong></td><td class="num"><strong>0.9074</strong></td></tr>
        </tbody>
      </table></div>

      <p>Profile data alone (income, credit score, tenure) is no better than chance. The identity network
      carries most of the signal, and behaviour over time adds more. Accuracy is misleading on this
      imbalanced problem: the tabular Random Forest scores 0.87 accuracy while catching 7 of 180 frauds.</p>

      <h3>In the app</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>Dataset</th><th>Mode</th><th class="num">ROC-AUC</th><th class="num">PR-AUC</th><th>Suspected rings</th><th>Ring quality vs known labels</th></tr></thead>
        <tbody>
          <tr><td>Synthetic demo (8,800 customers)</td><td>Trained on labels (out-of-fold)</td><td class="num">0.957</td><td class="num">0.915</td><td>196 of 943 linked groups</td><td>94.4% are mostly fraud; 88.9% of the 216 true rings found</td></tr>
          <tr><td>Bank sample, labels hidden (1,650)</td><td>Reference model</td><td class="num">0.948</td><td class="num">0.896</td><td>32 of 170</td><td>87.5% are mostly fraud; 82.9% of the 35 true rings found</td></tr>
          <tr><td>Bank sample, no labels at all (1,650)</td><td>Reference model, no events</td><td class="num">&ndash;</td><td class="num">&ndash;</td><td>33 of 170</td><td>&ndash;</td></tr>
        </tbody>
      </table></div>

      <div class="stat-grid">
        <div class="stat"><span class="n">94.2%</span><span class="l">Alert precision (678 of 720 alerts are fraud)</span></div>
        <div class="stat"><span class="n">84.8%</span><span class="l">Fraud recall (678 of 800 fraud customers caught)</span></div>
        <div class="stat"><span class="n">196</span><span class="l">Suspected rings out of 943 linked groups</span></div>
        <div class="stat"><span class="n">88.9%</span><span class="l">Of 216 true rings recovered</span></div>
      </div>

      <div class="callout good">
        <strong>Feedback helps, measured fairly.</strong> On the bank sample with labels hidden, a simulated
        analyst reviewed the 60 highest-scoring linked groups, deciding each one from the known labels. After
        retraining, both versions were scored on the customers nobody reviewed:
      </div>

      <div class="table-wrap"><table>
        <thead><tr><th></th><th class="num">ROC-AUC</th><th class="num">PR-AUC</th><th class="num">F1</th></tr></thead>
        <tbody>
          <tr><td>Before feedback (v1)</td><td class="num">0.738</td><td class="num">0.456</td><td class="num">0.424</td></tr>
          <tr><td>After feedback (v2)</td><td class="num"><strong>0.768</strong></td><td class="num"><strong>0.490</strong></td><td class="num"><strong>0.471</strong></td></tr>
        </tbody>
      </table></div>
      <p style="font-size:.86rem;color:var(--text-3);">Absolute numbers are lower than in the table above because the unreviewed remainder is the hard cases.</p>
    </section>

    <section id="research-pipeline">
      <h2><span class="sec-index">06</span>Research pipeline</h2>
      <p>The original, script-based experiment pipeline is unchanged in behaviour and still runs on its own:</p>
      <pre><code>python -m data_generation.run_all
python -m src.data.split_data
python -m src.data.build_customer_graph
python -m src.data.generate_red_flag_features
python -m src.data.generate_temporal_features
python -m src.data.validate_graph
python -m src.models.random_forest_baseline
pytest -q</code></pre>

      <div class="table-wrap"><table>
        <thead><tr><th>File</th><th>Purpose</th></tr></thead>
        <tbody>
          <tr><td><code>data/raw/customers.csv</code></td><td>Customer profiles, fraud label and ring ID (ground truth).</td></tr>
          <tr><td><code>data/raw/phones.csv</code>, <code>emails.csv</code>, <code>addresses.csv</code>, <code>devices.csv</code></td><td>Identity attribute values.</td></tr>
          <tr><td><code>data/raw/customer_attribute_links.csv</code></td><td>Customer-to-attribute links used to build graph edges.</td></tr>
          <tr><td><code>data/raw/events.csv</code></td><td>Account events (purchases, payments, limit increases, bust-outs).</td></tr>
          <tr><td><code>data/raw/ring_ground_truth.csv</code></td><td>Ring membership, for validation.</td></tr>
          <tr><td><code>data/processed/train.csv</code>, <code>test.csv</code></td><td>Ring-aware split (no ring in both).</td></tr>
          <tr><td><code>data/processed/customer_edges.csv</code></td><td>Customer graph edges with shared-attribute flags.</td></tr>
          <tr><td><code>data/processed/customer_features.csv</code></td><td>Network red-flag features.</td></tr>
          <tr><td><code>data/processed/customer_temporal_features.csv</code></td><td>Behaviour-over-time features.</td></tr>
          <tr><td><code>outputs/models/rf_baseline/</code></td><td>Metrics, predictions and feature importances.</td></tr>
        </tbody>
      </table></div>

      <p><strong>How the synthetic data is made.</strong></p>
      <ul>
        <li>Legitimate customers share attributes for plausible reasons: households share addresses (and sometimes a phone or device), and contact pairs share a phone.</li>
        <li>Fraud rings (2&ndash;10 members) share one to three attribute types, each member probabilistically, so rings are not perfect cliques.</li>
        <li>Some fraud customers also share an attribute with a legitimate customer.</li>
        <li>Only 60% of fraud customers show bust-out behaviour, and some legitimate customers have utilization spikes, so behaviour overlaps between the classes.</li>
      </ul>
      <p><code>generate_all()</code> accepts <code>seed</code>, <code>n_legitimate</code>, <code>n_fraud</code>, <code>out_dir</code> and <code>progress</code>; the defaults reproduce the canonical dataset byte for byte.</p>

      <div class="callout warn">
        <strong>Leakage controls.</strong> <code>is_synthetic_fraud</code>, <code>ring_id</code> and
        <code>group_id</code> are never features. Splits keep each ring on one side, and tests check that no
        customer or ring appears in both. The graph is built from the full identity universe, which is a
        transductive assumption; see future work.
      </div>
    </section>

    <section id="contrastive">
      <h2><span class="sec-index">07</span>Stretch goal: contrastive pretraining</h2>
      <p><code>src/models/contrastive_pretraining.py</code> adds a GRACE-style <strong>graph contrastive
      learner</strong>, which uses no labels:</p>
      <ul>
        <li>Two random views of the identity graph are made by dropping edges and masking features.</li>
        <li>A 2-layer GCN embeds every customer in both views.</li>
        <li>An NT-Xent loss pulls the two views of the same customer together and pushes different customers apart.</li>
      </ul>
      <p>The 32-dimensional embeddings are appended to the existing features and evaluated on the same ring-aware split.</p>
      <pre><code>pip install -r requirements-contrastive.txt --index-url https://download.pytorch.org/whl/cpu
python -m src.models.contrastive_pretraining          # about 4 minutes on CPU (3 seeds)</code></pre>

      <p>Mean &plusmn; standard deviation over seeds 42, 43 and 44:</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Model</th><th>Features</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">F1</th><th class="num">ROC-AUC</th><th class="num">PR-AUC</th></tr></thead>
        <tbody>
          <tr><td>HistGradientBoosting</td><td>Combined (baseline)</td><td class="num">0.895</td><td class="num">0.850</td><td class="num">0.872</td><td class="num">0.946</td><td class="num">0.907</td></tr>
          <tr><td>Logistic regression (linear probe)</td><td>Embeddings only</td><td class="num">0.518 &plusmn; 0.012</td><td class="num">0.800 &plusmn; 0.010</td><td class="num">0.628 &plusmn; 0.007</td><td class="num">0.930 &plusmn; 0.004</td><td class="num">0.817 &plusmn; 0.015</td></tr>
          <tr><td>HistGradientBoosting</td><td>Embeddings only</td><td class="num">0.923 &plusmn; 0.013</td><td class="num">0.732 &plusmn; 0.009</td><td class="num">0.816 &plusmn; 0.004</td><td class="num">0.931 &plusmn; 0.011</td><td class="num">0.846 &plusmn; 0.013</td></tr>
          <tr><td>HistGradientBoosting</td><td>Combined + embeddings</td><td class="num">0.950 &plusmn; 0.024</td><td class="num">0.794 &plusmn; 0.006</td><td class="num">0.865 &plusmn; 0.011</td><td class="num">0.950 &plusmn; 0.003</td><td class="num">0.898 &plusmn; 0.007</td></tr>
          <tr><td>Random Forest</td><td>Combined + embeddings</td><td class="num">0.931 &plusmn; 0.003</td><td class="num">0.696 &plusmn; 0.009</td><td class="num">0.797 &plusmn; 0.005</td><td class="num">0.942 &plusmn; 0.003</td><td class="num">0.861 &plusmn; 0.006</td></tr>
        </tbody>
      </table></div>

      <div class="callout">
        <strong>Reading.</strong> Embeddings learned <strong>without any labels</strong> reach ROC-AUC 0.93,
        about 98% of what the hand-engineered network and behaviour features achieve. That is useful for data
        where nobody has engineered red flags. Added on top of the hand-engineered features, they raise
        precision and ROC-AUC slightly but lower recall, F1 and PR-AUC, so on this dataset they are not a
        clear win. The bolt-on is kept as an optional experiment and the app does not use it.
      </div>
    </section>

    <section id="testing">
      <h2><span class="sec-index">08</span>Testing</h2>
      <pre><code>pytest -q                          # about 4 minutes; the contrastive tests are skipped without PyTorch
cd frontend && npm run typecheck   # strict TypeScript</code></pre>
      <p>The tests cover:</p>
      <ul>
        <li><strong>Research pipeline:</strong> determinism, data validation, and leakage.</li>
        <li><strong>Refactored feature code:</strong> it matches the original implementations exactly.</li>
        <li><strong>Ingestion:</strong> role detection and normalisation on a foreign schema, and upload validation errors.</li>
        <li><strong>Explanations:</strong> Shapley contributions add up to the score, and the written reasons name the largest factor.</li>
        <li><strong>End-to-end through the API:</strong> unlabeled upload &rarr; rings &rarr; review &rarr; retrain &rarr; version 2 with stable ring IDs; labels hidden vs trained on; the synthetic job reproducing the research table.</li>
        <li><strong>Jobs:</strong> the SSE stream, CSV export, and recovery of jobs interrupted by a restart.</li>
      </ul>
    </section>

    <section id="demo-script">
      <h2><span class="sec-index">09</span>Demo script</h2>
      <p class="kicker">About 7 minutes. Preload with <code>python -m backend.cli demo</code> and <code>python -m backend.cli analyze sample_data/bank_customers_unlabeled.csv --name "Bank export (no labels)"</code>, then <code>python -m backend</code>.</p>
      <ol>
        <li><strong>Overview (synthetic demo).</strong> 196 suspected rings out of 943 linked groups. The model has ROC-AUC 0.957, and 94% of suspected rings are real rings. Point at the risk histogram: most customers score near 0, and known fraud piles up at 100.</li>
        <li><strong>Model &amp; metrics.</strong> The feature-set comparison: profile data alone is at chance (0.49), the identity network lifts it to 0.92, and everything combined reaches 0.95. Accuracy would have hidden this.</li>
        <li><strong>Fraud-ring review.</strong> Open the top ring and read the one-line summary: &ldquo;6 accounts linked by 1 shared email address and 1 shared phone number&hellip;&rdquo;. Show the evidence panel with the exact email used by 6 of 6 members, and the graph. Confirm it with a note; the queue advances to the next ring.</li>
        <li><strong>Customer detail.</strong> Open a member. The summary says in plain English why it was flagged. The factor chart shows each fact&rsquo;s points, and they add up from a typical customer&rsquo;s score to this one&rsquo;s. Show the connections table with the exact shared phone, email and device. For a bust-out account, the activity chart shows the utilization spike just before the account went quiet.</li>
        <li><strong>Your own data.</strong> On Datasets &amp; uploads, click <strong>Unlabeled sample</strong>, then <strong>Upload and detect columns</strong>. Every column is recognised even though the names differ, and the four address columns are combined. Run it and watch the live progress, stage by stage.</li>
        <li><strong>Rings without labels.</strong> The same console now shows rings in data that has no fraud labels. Note that the 60-person office address was ignored, not flagged as a ring.</li>
        <li><strong>Feedback loop.</strong> Confirm one ring and dismiss another, then click <strong>Retrain with feedback</strong>. Model v2 appears in the version history with what changed, and the ring keeps its ID and status.</li>
      </ol>
    </section>

    <section id="future-work">
      <h2><span class="sec-index">10</span>Future work: temporal modelling <span style="font-weight:400;color:var(--text-3);">(deferred)</span></h2>
      <p>Time-based modelling was explicitly deferred. The current system is <strong>transductive and static</strong>:</p>
      <ul>
        <li>The identity graph uses every link in the data regardless of when it appeared.</li>
        <li>Behaviour features summarise each customer&rsquo;s whole history.</li>
        <li>Labels are end states.</li>
      </ul>
      <p>That is fine for finding rings in a snapshot, but it overstates how early fraud can be caught. A clearly scoped next step:</p>
      <ol>
        <li><strong>Timestamped links.</strong> Record when each customer&ndash;attribute link first appeared (application or login time). The generator already has account-open dates; links need their own timestamps.</li>
        <li><strong>Point-in-time graph snapshots.</strong> Compute network features for a customer using only links that existed at the scoring time, for example at application or 30 days after opening.</li>
        <li><strong>Point-in-time behaviour features.</strong> Aggregate events only up to the scoring time, with rolling windows (7/30/90 days) instead of whole-history summaries.</li>
        <li><strong>Forward-in-time evaluation.</strong> Train on customers who opened accounts before a cut-off date and test on later ones, still keeping rings on one side, and report how many days before bust-out each ring is flagged.</li>
        <li><strong>Sequence and temporal-graph models,</strong> only after 1&ndash;4 exist: sequence models over each customer&rsquo;s events, and temporal graph networks over timestamped edges. Compare them against the gradient-boosting baseline on the forward-in-time split.</li>
      </ol>
      <div class="callout warn">
        <strong>Success criterion:</strong> detection <em>before</em> the bust-out, measured as recall at a
        fixed alert budget N days before the first bust-out event, not end-of-history ROC-AUC.
      </div>
    </section>

    <section id="project-layout">
      <h2><span class="sec-index">11</span>Project layout</h2>
      <pre><code>backend/              FastAPI app, job runner, SQLite layer, CLI
  pipeline/           ingest, features, modeling, explanations, rings, reference model, runner
data_generation/      synthetic data generator (customers, identities, rings, events)
src/data/             graph, feature, split and validation scripts (research pipeline)
src/models/           experiment runner and the contrastive pretraining bolt-on
frontend/             React + TypeScript analyst console
sample_data/          "bring your own data" examples in a different format
scripts/              make_sample_data.py
tests/                pytest suite (research pipeline, app end to end, contrastive)
docs/screenshots/     screenshots used in this README</code></pre>
      <p>Project status and weekly history are in <code>PROJECT_STATUS.md</code>.</p>
    </section>

  </main>
</div>

<footer>
  <span>Synthetic Identity Fraud Detection &mdash; analyst console &amp; detection pipeline</span>
  <span>Converted from <code>README.md</code> for presentation / offline reading &middot; content unchanged</span>
</footer>

</body>
</html>
