// src/components/PageWrapper.jsx
export default function PageWrapper({ children, className = "" }) {
  return (
    <div className={`max-w-6xl mx-auto space-y-6 ${className}`}>
      {children}
    </div>
  );
}
