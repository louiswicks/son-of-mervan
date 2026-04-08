// src/components/Card.jsx
export default function Card({ children, className = "" }) {
  return (
    <div
      className={`rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 sm:p-7 ${className}`}
    >
      {children}
    </div>
  );
}
