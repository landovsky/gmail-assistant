/**
 * Admin Layout Component
 * Provides consistent layout for admin pages
 */

export function AdminLayout({ title, children }: { title: string; children: any }) {
  return (
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{title} - Gmail Assistant Admin</title>
        <style>{`
          * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
          }
          body {
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            background: #0f1117;
            color: #e0e0e0;
            line-height: 1.6;
          }
          a {
            color: #4a7c59;
            text-decoration: none;
          }
          a:hover {
            text-decoration: underline;
          }
          .header {
            background: #1a1d27;
            border-bottom: 1px solid #2a2d37;
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
          }
          .header-title {
            font-size: 1.3rem;
            font-weight: bold;
          }
          .header-nav {
            display: flex;
            gap: 1.5rem;
            align-items: center;
          }
          .btn {
            background: #2a5c3f;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-family: inherit;
            font-size: 0.9rem;
          }
          .btn:hover {
            background: #3a6c4f;
          }
          table {
            width: 100%;
            border-collapse: collapse;
          }
          th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #2a2d37;
          }
          th {
            background: #1a1d27;
            font-weight: bold;
          }
          tr:hover {
            background: #1a1d27;
          }
        `}</style>
      </head>
      <body>
        <div class="header">
          <div class="header-title">
            <a href="/admin" style="color: inherit;">Gmail Assistant Admin</a>
          </div>
          <div class="header-nav">
            <a href="/debug/emails">Debug UI</a>
            <a href="/admin">Tables</a>
            <button class="btn" onclick="triggerFullSync()">Full Sync</button>
          </div>
        </div>
        {children}
        <script>{`
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
        `}</script>
      </body>
    </html>
  );
}
