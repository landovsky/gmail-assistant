/** @jsxImportSource hono/jsx */
export const EmailListPage = ({ emails, count, filters }: any) => (
  <html lang="en">
    <head>
      <meta charSet="UTF-8" />
      <title>Email Debug - Gmail Assistant</title>
      <style>{`
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'SF Mono', 'Consolas', monospace; background: #0f1117; color: #e4e4e7; }
        .nav { background: #1a1d27; padding: 1rem 2rem; border-bottom: 1px solid #2a2d37; }
        .nav-content { max-width: 1400px; margin: 0 auto; display: flex; gap: 1.5rem; align-items: center; }
        .nav h1 { font-size: 1.25rem; }
        .nav a { color: #60a5fa; text-decoration: none; }
        .btn { background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; cursor: pointer; }
        .container { max-width: 1400px; margin: 2rem auto; padding: 0 2rem; }
        .card { background: #1a1d27; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1.5rem; }
        .filters { display: grid; grid-template-columns: 1fr auto auto auto auto; gap: 1rem; }
        input, select { background: #0f1117; border: 1px solid #2a2d37; color: #e4e4e7; padding: 0.5rem; border-radius: 0.375rem; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #2a2d37; font-size: 0.875rem; }
        th { background: #0f1117; font-weight: 600; }
        tr:hover { background: #23262f; }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; }
        .badge-blue { background: #1e40af; }
        .badge-purple { background: #6b21a8; }
        .badge-orange { background: #c2410c; }
        .badge-gray { background: #52525b; }
        .badge-cyan { background: #0e7490; }
        .badge-yellow { background: #a16207; }
        .badge-green { background: #15803d; }
        a.link { color: #60a5fa; text-decoration: none; }
      `}</style>
    </head>
    <body>
      <div class="nav">
        <div class="nav-content">
          <h1>Email Debug</h1>
          <a href="/debug/emails">All Emails</a>
          <button class="btn" onclick="triggerFullSync()">Full Sync</button>
        </div>
      </div>
      <div class="container">
        <div class="card">
          <form method="GET" class="filters">
            <input type="text" name="q" placeholder="Search..." value={filters.q || ""} />
            <select name="status">
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="drafted">Drafted</option>
              <option value="sent">Sent</option>
            </select>
            <select name="classification">
              <option value="">All Types</option>
              <option value="needs_response">Needs Response</option>
              <option value="action_required">Action Required</option>
            </select>
            <button type="submit" class="btn">Filter</button>
            <a href="/debug/emails" class="btn">Reset</a>
          </form>
        </div>
        <div class="card">
          <p>Showing {count} emails</p>
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Subject</th><th>Sender</th><th>Classification</th><th>Status</th><th>Events</th><th>LLM</th>
              </tr>
            </thead>
            <tbody>
              {emails.map((e: any) => (
                <tr key={e.id}>
                  <td><a href={`/debug/email/${e.id}`} class="link">{e.id}</a></td>
                  <td><a href={`/debug/email/${e.id}`} class="link">{e.subject?.substring(0, 60)}</a></td>
                  <td>{e.sender_email}</td>
                  <td><span class="badge badge-blue">{e.classification}</span></td>
                  <td><span class="badge badge-yellow">{e.status}</span></td>
                  <td>{e.event_count || 0}</td>
                  <td>{e.llm_call_count || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <script dangerouslySetInnerHTML={{__html: `
        async function triggerFullSync() {
          if (!confirm('Trigger full sync?')) return;
          const res = await fetch('/api/sync?full=true', { method: 'POST' });
          alert(res.ok ? 'Sync queued!' : 'Failed');
        }
      `}} />
    </body>
  </html>
);
