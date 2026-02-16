/**
 * Table List Page Component
 * Displays paginated table data with search
 */

import { AdminLayout } from "./admin-layout.js";

export function TableListPage({
  tableName,
  data,
  columns,
  page,
  limit,
  total,
  totalPages,
  search,
}: {
  tableName: string;
  data: any[];
  columns: string[];
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  search: string;
}) {
  return (
    <AdminLayout title={tableName}>
      <div style="padding: 2rem;">
        {/* Breadcrumb */}
        <div style="margin-bottom: 1rem; color: #999;">
          <a href="/admin">Admin</a> / <span>{tableName}</span>
        </div>

        {/* Header */}
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
          <h1 style="font-size: 1.8rem;">{tableName}</h1>
          <div style="color: #999;">
            {total} record{total !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Search */}
        <form method="GET" style="margin-bottom: 1.5rem;">
          <input
            type="text"
            name="search"
            value={search}
            placeholder={`Search ${tableName}...`}
            style="width: 100%; max-width: 500px; padding: 0.75rem; background: #1a1d27; border: 1px solid #2a2d37; border-radius: 4px; color: #e0e0e0; font-family: inherit;"
          />
          <input type="hidden" name="page" value="1" />
          <button type="submit" class="btn" style="margin-left: 0.5rem;">Search</button>
          {search && <a href={`/admin/table/${tableName}`} style="margin-left: 0.5rem; color: #999;">Clear</a>}
        </form>

        {/* Table */}
        <div style="background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px; overflow: hidden;">
          {data.length === 0 ? (
            <div style="padding: 3rem; text-align: center; color: #999;">No records found</div>
          ) : (
            <div style="overflow-x: auto;">
              <table>
                <thead>
                  <tr>
                    {columns.map((col) => (
                      <th>{col}</th>
                    ))}
                    {tableName === 'emails' && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {data.map((row) => (
                    <tr>
                      {columns.map((col) => (
                        <td style={col === 'subject' ? 'max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;' : ''}>
                          {formatValue(row[col])}
                        </td>
                      ))}
                      {tableName === 'emails' && (
                        <td>
                          <a href={`/debug/email/${row.id}`} style="color: #4a7c59;">🔍 Debug</a>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style="margin-top: 1.5rem; display: flex; justify-content: center; align-items: center; gap: 1rem;">
            {page > 1 && (
              <a href={`/admin/table/${tableName}?page=${page - 1}&limit=${limit}${search ? `&search=${encodeURIComponent(search)}` : ''}`}>
                ← Previous
              </a>
            )}
            <span style="color: #999;">
              Page {page} of {totalPages}
            </span>
            {page < totalPages && (
              <a href={`/admin/table/${tableName}?page=${page + 1}&limit=${limit}${search ? `&search=${encodeURIComponent(search)}` : ''}`}>
                Next →
              </a>
            )}
          </div>
        )}

        {/* Page size selector */}
        <div style="margin-top: 1rem; text-align: center; color: #999; font-size: 0.9rem;">
          Show:
          {[25, 50, 100].map((size) => (
            <>
              {' '}
              {size === limit ? (
                <span style="font-weight: bold; color: #4a7c59;">{size}</span>
              ) : (
                <a href={`/admin/table/${tableName}?page=1&limit=${size}${search ? `&search=${encodeURIComponent(search)}` : ''}`}>
                  {size}
                </a>
              )}
            </>
          ))}
          {' '}records per page
        </div>
      </div>
    </AdminLayout>
  );
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
