import React from "react";

const Toast = ({ open, type = "success", title, message, onClose }) => {
  if (!open) return null;

  const tone = {
    success: {
      ring: "ring-green-300",
      bg: "from-green-500 to-green-600",
      icon: "✅",
    },
    error: {
      ring: "ring-red-300",
      bg: "from-red-500 to-red-600",
      icon: "⚠️",
    },
    info: {
      ring: "ring-blue-300",
      bg: "from-blue-500 to-blue-600",
      icon: "ℹ️",
    },
  }[type];

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 w-[320px] rounded-2xl shadow-2xl overflow-hidden ring-1 ${tone.ring}
                  animate-[toastIn_.25s_ease-out]`}
      role="status"
      aria-live="polite"
    >
      <div className={`bg-gradient-to-r ${tone.bg} text-white px-4 py-3`}>
        <div className="flex items-center gap-2 font-semibold">
          <span>{tone.icon}</span>
          <span>{title}</span>
        </div>
      </div>
      <div className="bg-white px-4 py-3 text-gray-700">
        <div className="text-sm">{message}</div>
        <button
          onClick={onClose}
          className="mt-3 text-sm font-medium text-blue-600 hover:text-blue-800"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
};

export default Toast;
