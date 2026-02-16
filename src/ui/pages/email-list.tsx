/** @jsxImportSource hono/jsx */
export const EmailListPage = ({ emails, count, filters }: any) => (
  <html lang="en">
    <head>
      <meta charSet="UTF-8" />
      <title>Email Debug - Gmail Assistant</title>
      <style>{`
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; background: #0f1117; color: #e4e4e7; line-height: 1.6; }
        .nav { background: #1a1d27; padding: 1rem 2rem; border-bottom: 1px solid #2a2d37; position: sticky; top: 0; z-index: 100; }
        .nav-content { max-width: 1600px; margin: 0 auto; display: flex; gap: 1.5rem; align-items: center; }
        .nav h1 { font-size: 1.25rem; font-weight: bold; }
        .nav a { color: #60a5fa; text-decoration: none; }
        .nav a:hover { text-decoration: underline; }
        .btn { background: #2a5c3f; color: white; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; cursor: pointer; font-family: inherit; font-size: 0.875rem; }
        .btn:hover { background: #3a6c4f; }
        .container { max-width: 1600px; margin: 2rem auto; padding: 0 2rem; }
        .card { background: #1a1d27; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #2a2d37; }
        .filters { display: grid; grid-template-columns: 1fr auto auto auto auto; gap: 1rem; align-items: center; }
        input, select { background: #0f1117; border: 1px solid #2a2d37; color: #e4e4e7; padding: 0.5rem; border-radius: 0.375rem; font-family: inherit; font-size: 0.875rem; }
        input:focus, select:focus { outline: 2px solid #4a7c59; outline-offset: 2px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #2a2d37; font-size: 0.875rem; }
        th { background: #0f1117; font-weight: 600; position: sticky; top: 0; }
        tr:hover { background: #23262f; }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 500; }
        .badge-needs_response { background: #1e40af; color: white; }
        .badge-action_required { background: #6b21a8; color: white; }
        .badge-payment_request { background: #c2410c; color: white; }
        .badge-fyi { background: #52525b; color: white; }
        .badge-waiting { background: #0e7490; color: white; }
        .badge-pending { background: #a16207; color: white; }
        .badge-drafted { background: #1e40af; color: white; }
        .badge-rework_requested { background: #c2410c; color: white; }
        .badge-sent { background: #15803d; color: white; }
        .badge-skipped { background: #52525b; color: white; }
        .badge-archived { background: #52525b; color: white; }
        .badge-high { background: #15803d; color: white; }
        .badge-medium { background: #a16207; color: white; }
        .badge-low { background: #c2410c; color: white; }
        a.link { color: #60a5fa; text-decoration: none; }
        a.link:hover { text-decoration: underline; }
        .empty { padding: 3rem; text-align: center; color: #999; }
      `}</style>
    </head>
    <body>
      <div class="nav">
        <div class="nav-content">
          <h1>Email Debug</h1>
          <a href="/debug/emails">All Emails</a>
          <a href="/admin">SQLAdmin</a>
          <button class="btn" onclick="triggerFullSync()">Full Sync</button>
        </div>
      </div>
      <div class="container">
        <div class="card">
          <form method="GET" class="filters">
            <input
              type="text"
              name="q"
              placeholder="Search subject, body, sender, thread ID..."
              value={filters.q || ""}
            />
            <select name="status">
              <option value="">All Status</option>
              <option value="pending" selected={filters.status === "pending"}>pending</option>
              <option value="drafted" selected={filters.status === "drafted"}>drafted</option>
              <option value="rework_requested" selected={filters.status === "rework_requested"}>rework_requested</option>
              <option value="sent" selected={filters.status === "sent"}>sent</option>
              <option value="skipped" selected={filters.status === "skipped"}>skipped</option>
              <option value="archived" selected={filters.status === "archived"}>archived</option>
            </select>
            <select name="classification">
              <option value="">All Classification</option>
              <option value="needs_response" selected={filters.classification === "needs_response"}>needs_response</option>
              <option value="action_required" selected={filters.classification === "action_required"}>action_required</option>
              <option value="payment_request" selected={filters.classification === "payment_request"}>payment_request</option>
              <option value="fyi" selected={filters.classification === "fyi"}>fyi</option>
              <option value="waiting" selected={filters.classification === "waiting"}>waiting</option>
            </select>
            <button type="submit" class="btn">Filter</button>
            <a href="/debug/emails" class="btn">Reset</a>
          </form>
        </div>
        <div class="card">
          <div style="margin-bottom: 1rem; color: #999; font-size: 0.875rem;">
            Showing {count} email{count !== 1 ? "s" : ""}
          </div>
          {emails.length === 0 ? (
            <div class="empty">No emails found.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>User</th>
                  <th>Subject</th>
                  <th>Sender</th>
                  <th>Classification</th>
                  <th>Draft Status</th>
                  <th>Confidence</th>
                  <th>Events</th>
                  <th>LLM</th>
                  <th>Received</th>
                </tr>
              </thead>
              <tbody>
                {emails.map((e: any) => (
                  <tr key={e.id}>
                    <td>
                      <a href={`/debug/email/${e.id}`} class="link">
                        {e.id}
                      </a>
                    </td>
                    <td>{e.userId || e.user_id}</td>
                    <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                      <a href={`/debug/email/${e.id}`} class="link">
                        {e.subject?.substring(0, 60) || "(no subject)"}
                      </a>
                    </td>
                    <td>{e.senderEmail || e.sender_email}</td>
                    <td>
                      <span class={`badge badge-${e.classification}`}>
                        {e.classification}
                      </span>
                    </td>
                    <td>
                      <span class={`badge badge-${e.status}`}>
                        {e.status}
                      </span>
                    </td>
                    <td>
                      {e.confidence && (
                        <span class={`badge badge-${e.confidence === "high" ? "high" : e.confidence === "medium" ? "medium" : "low"}`}>
                          {e.confidence}
                        </span>
                      )}
                    </td>
                    <td>{e.event_count || 0}</td>
                    <td>{e.llm_call_count || 0}</td>
                    <td style="font-size: 0.8rem; color: #999;">
                      {e.receivedAt || e.received_at ? new Date(e.receivedAt || e.received_at).toLocaleString() : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <script dangerouslySetInnerHTML={{
        __html: `
        async function triggerFullSync() {
          if (!confirm('Trigger a full inbox sync?')) return;
          try {
            const res = await fetch('/api/sync', { method: 'POST' });
            if (res.ok) {
              alert('Sync triggered successfully');
              window.location.reload();
            } else {
              alert('Sync failed: ' + await res.text());
            }
          } catch (error) {
            alert('Error: ' + error.message);
          }
        }
      `,
      }} />
    </body>
  </html>
);
