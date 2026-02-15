/** @jsxImportSource hono/jsx */
export const EmailDetailPage = ({ email, events, llmCalls }: any) => (
  <html lang="en">
    <head>
      <meta charSet="UTF-8" />
      <title>Email {email.id} - Debug</title>
      <style>{`
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'SF Mono', monospace; background: #0f1117; color: #e4e4e7; }
        .nav { background: #1a1d27; padding: 1rem 2rem; border-bottom: 1px solid #2a2d37; }
        .nav-content { max-width: 1400px; margin: 0 auto; display: flex; gap: 1.5rem; }
        .container { max-width: 1400px; margin: 2rem auto; padding: 0 2rem; }
        .card { background: #1a1d27; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1.5rem; }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; margin-right: 0.5rem; }
        .badge-blue { background: #1e40af; }
        .btn { background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; cursor: pointer; }
        .btn-purple { background: #7c3aed; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.75rem; border-bottom: 1px solid #2a2d37; font-size: 0.875rem; }
        .expandable { cursor: pointer; color: #60a5fa; }
        .content { background: #0f1117; padding: 1rem; border-radius: 0.375rem; max-height: 400px; overflow: auto; white-space: pre-wrap; }
      `}</style>
    </head>
    <body>
      <div class="nav">
        <div class="nav-content">
          <h1>Email Debug</h1>
          <a href="/debug/emails">← Back to List</a>
          <button class="btn btn-purple" onclick="reclassify({email.id})">Reclassify</button>
        </div>
      </div>
      <div class="container">
        <div class="card">
          <h2>{email.subject || "(no subject)"}</h2>
          <p>From: {email.sender_email}</p>
          <p>Thread: <code>{email.gmail_thread_id}</code></p>
          <div style="margin-top: 1rem;">
            <span class="badge badge-blue">{email.classification}</span>
            <span class="badge badge-blue">{email.status}</span>
            <span class="badge badge-blue">{email.confidence}</span>
          </div>
        </div>
        
        <div class="card">
          <h3>Events ({events.length})</h3>
          {events.length === 0 ? <p>No events recorded.</p> : (
            <table>
              <thead><tr><th>ID</th><th>Type</th><th>Detail</th><th>Time</th></tr></thead>
              <tbody>
                {events.map((e: any) => (
                  <tr key={e.id}>
                    <td>{e.id}</td>
                    <td>{e.event_type}</td>
                    <td>{e.detail}</td>
                    <td>{e.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div class="card">
          <h3>LLM Calls ({llmCalls.length})</h3>
          {llmCalls.length === 0 ? <p>No LLM calls recorded.</p> : (
            <table>
              <thead><tr><th>ID</th><th>Type</th><th>Model</th><th>Tokens</th><th>Latency</th><th>Prompts</th></tr></thead>
              <tbody>
                {llmCalls.map((call: any) => (
                  <tr key={call.id}>
                    <td>{call.id}</td>
                    <td>{call.call_type}</td>
                    <td>{call.model}</td>
                    <td>{call.total_tokens}</td>
                    <td>{call.latency_ms}ms</td>
                    <td>
                      <span class="expandable" onclick={`toggle('llm-${call.id}')`}>▸ Expand</span>
                      <div id={`llm-${call.id}`} style="display: none;" class="content">
                        <strong>System:</strong><br/>{call.system_prompt}<br/><br/>
                        <strong>User:</strong><br/>{call.user_message}<br/><br/>
                        <strong>Response:</strong><br/>{call.response_text}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <script dangerouslySetInnerHTML={{__html: `
        function toggle(id) {
          const el = document.getElementById(id);
          el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }
        async function reclassify(id) {
          if (!confirm('Reclassify this email?')) return;
          const res = await fetch(\`/api/emails/\${id}/reclassify\`, { method: 'POST' });
          const data = await res.json();
          alert(res.ok ? \`Queued: Job #\${data.job_id}\` : 'Failed');
        }
      `}} />
    </body>
  </html>
);
