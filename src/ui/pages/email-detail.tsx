/** @jsxImportSource hono/jsx */

interface TimelineEntry {
  time: Date;
  type: "event" | "llm" | "agent";
  data: any;
}

function buildTimeline(events: any[], llmCalls: any[], agentRuns: any[]): TimelineEntry[] {
  const timeline: TimelineEntry[] = [];

  events.forEach((e) => {
    timeline.push({
      time: new Date(e.createdAt || e.created_at),
      type: "event",
      data: e,
    });
  });

  llmCalls.forEach((call) => {
    timeline.push({
      time: new Date(call.createdAt || call.created_at),
      type: "llm",
      data: call,
    });
  });

  agentRuns.forEach((run) => {
    timeline.push({
      time: new Date(run.createdAt || run.created_at),
      type: "agent",
      data: run,
    });
  });

  return timeline.sort((a, b) => b.time.getTime() - a.time.getTime());
}

export const EmailDetailPage = ({ email, events, llmCalls, agentRuns }: any) => {
  const timeline = buildTimeline(events || [], llmCalls || [], agentRuns || []);

  return (
    <html lang="en">
      <head>
        <meta charSet="UTF-8" />
        <title>Email {email.id} - Debug</title>
        <style>{`
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; background: #0f1117; color: #e4e4e7; line-height: 1.6; }
          .nav { background: #1a1d27; padding: 1rem 2rem; border-bottom: 1px solid #2a2d37; position: sticky; top: 0; z-index: 100; }
          .nav-content { max-width: 1600px; margin: 0 auto; display: flex; gap: 1.5rem; align-items: center; justify-content: space-between; }
          .nav-left { display: flex; gap: 1.5rem; align-items: center; }
          .nav-right { display: flex; gap: 1rem; align-items: center; }
          .nav h1 { font-size: 1.25rem; font-weight: bold; }
          .nav a { color: #60a5fa; text-decoration: none; }
          .nav a:hover { text-decoration: underline; }
          .btn { background: #2a5c3f; color: white; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; cursor: pointer; font-family: inherit; font-size: 0.875rem; }
          .btn:hover { background: #3a6c4f; }
          .btn-purple { background: #7c3aed; }
          .btn-purple:hover { background: #6d28d9; }
          .container { max-width: 1600px; margin: 2rem auto; padding: 0 2rem; }
          .card { background: #1a1d27; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #2a2d37; }
          .card h2 { font-size: 1.5rem; margin-bottom: 0.5rem; }
          .card h3 { font-size: 1.2rem; margin-bottom: 1rem; }
          .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 500; margin-right: 0.5rem; }
          .badge-needs_response { background: #1e40af; color: white; }
          .badge-action_required { background: #6b21a8; color: white; }
          .badge-payment_request { background: #c2410c; color: white; }
          .badge-fyi { background: #52525b; color: white; }
          .badge-waiting { background: #0e7490; color: white; }
          .badge-pending { background: #a16207; color: white; }
          .badge-drafted { background: #1e40af; color: white; }
          .badge-sent { background: #15803d; color: white; }
          .badge-high { background: #15803d; color: white; }
          .badge-medium { background: #a16207; color: white; }
          .badge-low { background: #c2410c; color: white; }
          table { width: 100%; border-collapse: collapse; }
          th, td { padding: 0.75rem; border-bottom: 1px solid #2a2d37; font-size: 0.875rem; text-align: left; vertical-align: top; }
          th { background: #0f1117; font-weight: 600; }
          tr:hover { background: #23262f; }
          .expandable { cursor: pointer; color: #60a5fa; user-select: none; }
          .expandable:hover { text-decoration: underline; }
          .content { background: #0f1117; padding: 1rem; border-radius: 0.375rem; margin-top: 0.5rem; max-height: 400px; overflow: auto; white-space: pre-wrap; word-wrap: break-word; border: 1px solid #2a2d37; }
          .metadata-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; margin-top: 1rem; }
          .metadata-item { background: #0f1117; padding: 0.75rem; border-radius: 0.375rem; border: 1px solid #2a2d37; }
          .metadata-label { font-size: 0.75rem; color: #999; margin-bottom: 0.25rem; }
          .metadata-value { font-size: 0.875rem; word-break: break-all; }
          .timeline { margin-top: 1.5rem; }
          .timeline-entry { display: grid; grid-template-columns: 90px 28px 1fr; gap: 1rem; margin-bottom: 1.5rem; align-items: start; }
          .timeline-time { text-align: right; color: #999; font-size: 0.875rem; padding-top: 0.25rem; }
          .timeline-dot { display: flex; flex-direction: column; align-items: center; }
          .timeline-dot-circle { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
          .timeline-dot-line { width: 2px; flex-grow: 1; background: #2a2d37; margin-top: 0.5rem; }
          .timeline-content { }
          .dot-event { background: #15803d; }
          .dot-llm { background: #7c3aed; }
          .dot-agent { background: #0e7490; }
          .empty { padding: 2rem; text-align: center; color: #999; }
          code { background: #0f1117; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-family: inherit; border: 1px solid #2a2d37; }
        `}</style>
      </head>
      <body>
        <div class="nav">
          <div class="nav-content">
            <div class="nav-left">
              <h1>Email Debug</h1>
              <a href="/debug/emails">← All Emails</a>
              <a href="/admin">SQLAdmin</a>
              <button class="btn btn-purple" onclick={`reclassifyEmail(${email.id})`}>
                Reclassify
              </button>
              <button class="btn" onclick="triggerFullSync()">Full Sync</button>
            </div>
            <div class="nav-right">
              <a href={`/debug/email/${email.id - 1}`}>← prev</a>
              <a href={`/debug/email/${email.id + 1}`}>next →</a>
            </div>
          </div>
        </div>

        <div class="container">
          {/* Email Metadata Card */}
          <div class="card">
            <h2>{email.subject || "(no subject)"}</h2>
            <div style="margin: 0.5rem 0 1rem 0; color: #999;">
              From: {email.senderName || email.sender_name || ""} &lt;{email.senderEmail || email.sender_email}&gt;
            </div>
            <div style="margin-bottom: 0.5rem;">
              <code>Thread: {email.gmailThreadId || email.gmail_thread_id}</code>
            </div>
            <div style="margin-bottom: 1rem;">
              <code>Message: {email.gmailMessageId || email.gmail_message_id}</code>
            </div>

            {/* Badges */}
            <div style="margin-bottom: 1rem;">
              <span class={`badge badge-${email.classification}`}>{email.classification}</span>
              <span class={`badge badge-${email.status}`}>{email.status}</span>
              {email.confidence && (
                <span class={`badge badge-${email.confidence}`}>{email.confidence}</span>
              )}
              <span class="badge badge-fyi">
                {email.messageCount || email.message_count || 1} message{(email.messageCount || email.message_count || 1) !== 1 ? "s" : ""}
              </span>
              <span class="badge badge-fyi">{email.resolvedStyle || email.resolved_style || "business"}</span>
              <span class="badge badge-fyi">{email.detectedLanguage || email.detected_language || "en"}</span>
            </div>

            {/* Metadata Grid */}
            <div class="metadata-grid">
              <div class="metadata-item">
                <div class="metadata-label">Received at</div>
                <div class="metadata-value">{email.receivedAt || email.received_at || "—"}</div>
              </div>
              <div class="metadata-item">
                <div class="metadata-label">Processed at</div>
                <div class="metadata-value">{email.processedAt || email.processed_at || "—"}</div>
              </div>
              <div class="metadata-item">
                <div class="metadata-label">Drafted at</div>
                <div class="metadata-value">{email.draftedAt || email.drafted_at || "—"}</div>
              </div>
              <div class="metadata-item">
                <div class="metadata-label">Acted at</div>
                <div class="metadata-value">{email.actedAt || email.acted_at || "—"}</div>
              </div>
              <div class="metadata-item">
                <div class="metadata-label">Draft ID</div>
                <div class="metadata-value">{email.gmailDraftId || email.gmail_draft_id || "—"}</div>
              </div>
              <div class="metadata-item">
                <div class="metadata-label">Rework count</div>
                <div class="metadata-value">{email.reworkCount || email.rework_count || 0}</div>
              </div>
              <div class="metadata-item">
                <div class="metadata-label">Vendor</div>
                <div class="metadata-value">{email.vendor || "—"}</div>
              </div>
              <div class="metadata-item">
                <div class="metadata-label">DB ID</div>
                <div class="metadata-value">{email.id}</div>
              </div>
            </div>

            {/* Additional sections */}
            {email.classificationReasoning && (
              <div style="margin-top: 1rem; padding: 1rem; background: #0f1117; border-radius: 0.375rem; border: 1px solid #2a2d37;">
                <div style="font-weight: 600; margin-bottom: 0.5rem; font-size: 0.875rem;">Classification Reasoning:</div>
                <pre style="white-space: pre-wrap; font-size: 0.875rem; margin: 0;">{email.classificationReasoning}</pre>
              </div>
            )}
            {email.lastReworkInstruction && (
              <div style="margin-top: 1rem; padding: 1rem; background: #0f1117; border-radius: 0.375rem; border: 1px solid #2a2d37;">
                <div style="font-weight: 600; margin-bottom: 0.5rem; font-size: 0.875rem;">Last Rework Instruction:</div>
                <pre style="white-space: pre-wrap; font-size: 0.875rem; margin: 0;">{email.lastReworkInstruction}</pre>
              </div>
            )}
            {email.snippet && (
              <div style="margin-top: 1rem; padding: 1rem; background: #0f1117; border-radius: 0.375rem; border: 1px solid #2a2d37;">
                <div style="font-weight: 600; margin-bottom: 0.5rem; font-size: 0.875rem;">Snippet:</div>
                <pre style="white-space: pre-wrap; font-size: 0.875rem; margin: 0;">{email.snippet}</pre>
              </div>
            )}
          </div>

          {/* Timeline */}
          <div class="card">
            <h3>Timeline ({timeline.length})</h3>
            {timeline.length === 0 ? (
              <div class="empty">No timeline entries.</div>
            ) : (
              <div class="timeline">
                {timeline.map((entry, idx) => (
                  <div class="timeline-entry" key={idx}>
                    <div class="timeline-time">
                      {entry.time.toLocaleTimeString()}
                    </div>
                    <div class="timeline-dot">
                      <div class={`timeline-dot-circle dot-${entry.type}`}></div>
                      {idx < timeline.length - 1 && <div class="timeline-dot-line"></div>}
                    </div>
                    <div class="timeline-content">
                      {entry.type === "event" && (
                        <div>
                          <span class="badge badge-fyi">{entry.data.eventType || entry.data.event_type}</span>
                          <div style="margin-top: 0.25rem; font-size: 0.875rem;">{entry.data.detail}</div>
                          {entry.data.labelId && <div style="margin-top: 0.25rem; font-size: 0.75rem; color: #999;">Label: {entry.data.labelId}</div>}
                          {entry.data.draftId && <div style="margin-top: 0.25rem; font-size: 0.75rem; color: #999;">Draft: {entry.data.draftId}</div>}
                        </div>
                      )}
                      {entry.type === "llm" && (
                        <div>
                          <span class="badge badge-waiting">{entry.data.callType || entry.data.call_type}</span>
                          <div style="margin-top: 0.25rem; font-size: 0.875rem;">
                            {entry.data.model} • {entry.data.totalTokens || entry.data.total_tokens} tokens • {entry.data.latencyMs || entry.data.latency_ms}ms
                          </div>
                          {entry.data.error && <div style="margin-top: 0.25rem; color: #ef4444; font-size: 0.875rem;">Error: {entry.data.error}</div>}
                        </div>
                      )}
                      {entry.type === "agent" && (
                        <div>
                          <span class="badge badge-waiting">{entry.data.profile}</span>
                          <div style="margin-top: 0.25rem; font-size: 0.875rem;">
                            {entry.data.iterations} iterations • <span class={`badge badge-${entry.data.status === "completed" ? "sent" : entry.data.status === "error" ? "payment_request" : "fyi"}`}>{entry.data.status}</span>
                          </div>
                          {entry.data.error && <div style="margin-top: 0.25rem; color: #ef4444; font-size: 0.875rem;">Error: {entry.data.error}</div>}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Events Section */}
          <div class="card">
            <h3>Events ({events?.length || 0})</h3>
            {!events || events.length === 0 ? (
              <div class="empty">No events recorded.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Detail</th>
                    <th>Label</th>
                    <th>Draft</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e: any) => (
                    <tr key={e.id}>
                      <td>{e.id}</td>
                      <td><span class="badge badge-fyi">{e.eventType || e.event_type}</span></td>
                      <td>{e.detail}</td>
                      <td>{e.labelId || e.label_id || "—"}</td>
                      <td>{e.draftId || e.draft_id || "—"}</td>
                      <td style="font-size: 0.8rem; color: #999;">{e.createdAt || e.created_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* LLM Calls Section */}
          <div class="card">
            <h3>LLM Calls ({llmCalls?.length || 0})</h3>
            {!llmCalls || llmCalls.length === 0 ? (
              <div class="empty">No LLM calls recorded.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Model</th>
                    <th>Prompt</th>
                    <th>Compl.</th>
                    <th>Total</th>
                    <th>Latency</th>
                    <th>Error</th>
                    <th>Time</th>
                    <th>Prompts / Response</th>
                  </tr>
                </thead>
                <tbody>
                  {llmCalls.map((call: any) => (
                    <tr key={call.id}>
                      <td>{call.id}</td>
                      <td><span class="badge badge-waiting">{call.callType || call.call_type}</span></td>
                      <td>{call.model}</td>
                      <td>{call.promptTokens || call.prompt_tokens || 0}</td>
                      <td>{call.completionTokens || call.completion_tokens || 0}</td>
                      <td>{call.totalTokens || call.total_tokens || 0}</td>
                      <td>{call.latencyMs || call.latency_ms || 0}ms</td>
                      <td style="color: #ef4444;">{call.error || ""}</td>
                      <td style="font-size: 0.8rem; color: #999;">{call.createdAt || call.created_at}</td>
                      <td>
                        <div>
                          <button class="btn" style="font-size: 0.75rem; padding: 0.25rem 0.5rem; margin-right: 0.5rem;" onclick={`toggleAll('llm-${call.id}', true)`}>Expand all</button>
                          <button class="btn" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;" onclick={`toggleAll('llm-${call.id}', false)`}>Collapse all</button>
                        </div>
                        <div style="margin-top: 0.5rem;">
                          <div>
                            <span class="expandable" onclick={`toggle('llm-${call.id}-system')`}>▸ system</span>
                            <div id={`llm-${call.id}-system`} style="display: none;" class="content">
                              {call.systemPrompt || call.system_prompt || "(empty)"}
                            </div>
                          </div>
                          <div style="margin-top: 0.5rem;">
                            <span class="expandable" onclick={`toggle('llm-${call.id}-user')`}>▸ user</span>
                            <div id={`llm-${call.id}-user`} style="display: none;" class="content">
                              {call.userMessage || call.user_message || "(empty)"}
                            </div>
                          </div>
                          <div style="margin-top: 0.5rem;">
                            <span class="expandable" onclick={`toggle('llm-${call.id}-response')`}>▸ response</span>
                            <div id={`llm-${call.id}-response`} style="display: none;" class="content">
                              {call.responseText || call.response_text || "(empty)"}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Agent Runs Section */}
          <div class="card">
            <h3>Agent Runs ({agentRuns?.length || 0})</h3>
            {!agentRuns || agentRuns.length === 0 ? (
              <div class="empty">No agent runs recorded.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Profile</th>
                    <th>Status</th>
                    <th>Iterations</th>
                    <th>Error</th>
                    <th>Started</th>
                    <th>Completed</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {agentRuns.map((run: any) => (
                    <tr key={run.id}>
                      <td>{run.id}</td>
                      <td>{run.profile}</td>
                      <td><span class={`badge badge-${run.status === "completed" ? "sent" : run.status === "error" ? "payment_request" : "fyi"}`}>{run.status}</span></td>
                      <td>{run.iterations || 0}</td>
                      <td style="color: #ef4444;">{run.error || ""}</td>
                      <td style="font-size: 0.8rem; color: #999;">{run.createdAt || run.created_at}</td>
                      <td style="font-size: 0.8rem; color: #999;">{run.completedAt || run.completed_at || "—"}</td>
                      <td>
                        <div>
                          <span class="expandable" onclick={`toggle('agent-${run.id}-tools')`}>▸ tool calls</span>
                          <div id={`agent-${run.id}-tools`} style="display: none;" class="content">
                            {JSON.stringify(run.toolCallsLog || run.tool_calls_log || [], null, 2)}
                          </div>
                        </div>
                        <div style="margin-top: 0.5rem;">
                          <span class="expandable" onclick={`toggle('agent-${run.id}-final')`}>▸ final message</span>
                          <div id={`agent-${run.id}-final`} style="display: none;" class="content">
                            {run.finalMessage || run.final_message || "(empty)"}
                          </div>
                        </div>
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
          function toggle(id) {
            const el = document.getElementById(id);
            const toggler = document.querySelector('[onclick*="toggle(\\''+id+'\\')"]');
            if (el.style.display === 'none') {
              el.style.display = 'block';
              if (toggler) toggler.textContent = toggler.textContent.replace('▸', '▾');
            } else {
              el.style.display = 'none';
              if (toggler) toggler.textContent = toggler.textContent.replace('▾', '▸');
            }
          }

          function toggleAll(prefix, expand) {
            ['system', 'user', 'response'].forEach(section => {
              const id = prefix + '-' + section;
              const el = document.getElementById(id);
              const toggler = document.querySelector('[onclick*="toggle(\\''+id+'\\')"]');
              if (el) {
                el.style.display = expand ? 'block' : 'none';
                if (toggler) toggler.textContent = toggler.textContent.replace(expand ? '▸' : '▾', expand ? '▾' : '▸');
              }
            });
          }

          async function reclassifyEmail(id) {
            if (!confirm('Reclassify this email? This will re-run the LLM classifier.')) return;
            try {
              const res = await fetch(\`/api/emails/\${id}/reclassify\`, { method: 'POST' });
              if (res.ok) {
                const data = await res.json();
                alert(\`Reclassification queued: Job #\${data.job_id}\`);
              } else {
                alert('Reclassification failed: ' + await res.text());
              }
            } catch (error) {
              alert('Error: ' + error.message);
            }
          }

          async function triggerFullSync() {
            if (!confirm('Trigger a full inbox sync?')) return;
            try {
              const res = await fetch('/api/sync', { method: 'POST' });
              if (res.ok) {
                alert('Sync triggered successfully');
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
};
