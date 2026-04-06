import React from 'react';

function Skeleton({ className = '', style }) {
  return (
    <div
      className={`animate-pulse bg-gray-200 rounded ${className}`}
      style={style}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-white border rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-6 w-6 rounded-full" />
      </div>
      <Skeleton className="h-9 w-40 mt-2" />
    </div>
  );
}

export function SkeletonTable({ rows = 8 }) {
  const cols = [120, 140, 100, 100, 80, 70, 56];
  return (
    <div className="overflow-x-auto bg-white rounded-xl shadow-md border">
      <table className="min-w-full">
        <thead className="bg-gray-100">
          <tr>
            {cols.map((w, i) => (
              <th key={i} className="p-3">
                <Skeleton style={{ width: w, height: 14 }} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <tr key={i} className="border-t">
              <td className="p-3"><Skeleton className="h-4 w-24" /></td>
              <td className="p-3"><Skeleton className="h-8 w-36" /></td>
              <td className="p-3"><Skeleton className="h-8 w-24" /></td>
              <td className="p-3"><Skeleton className="h-8 w-24" /></td>
              <td className="p-3"><Skeleton className="h-4 w-16" /></td>
              <td className="p-3"><Skeleton className="h-5 w-14" /></td>
              <td className="p-3"><Skeleton className="h-7 w-14" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SkeletonChart({ height = 'h-80' }) {
  return (
    <div className="bg-white border rounded-xl p-6 shadow-sm">
      <Skeleton className="h-5 w-48 mb-4" />
      <Skeleton className={`${height} w-full rounded-lg`} />
    </div>
  );
}

export default Skeleton;
