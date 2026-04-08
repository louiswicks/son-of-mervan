// src/components/CategoriesPage.jsx
import React, { useState } from 'react';
import { Plus, Edit2, Trash2, Check, X, Tag } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  useCategories,
  useCreateCategory,
  useUpdateCategory,
  useDeleteCategory,
} from '../hooks/useCategories';
import { SkeletonCard } from './Skeleton';

const DEFAULT_COLOR = '#6b7280';

// -------------------- Sub-components --------------------

function CategoryForm({ initial, onSubmit, onCancel, submitLabel = 'Save' }) {
  const [name, setName] = useState(initial?.name ?? '');
  const [color, setColor] = useState(initial?.color ?? DEFAULT_COLOR);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    onSubmit({ name: trimmed, color });
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 flex-wrap">
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Category name"
        maxLength={50}
        required
        className="flex-1 min-w-[160px] border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
        autoFocus
      />
      <div className="flex items-center gap-1.5">
        <label className="text-xs text-gray-500 dark:text-gray-400 select-none">Colour</label>
        <input
          type="color"
          value={color}
          onChange={(e) => setColor(e.target.value)}
          className="w-9 h-9 rounded-lg cursor-pointer border border-gray-300 dark:border-gray-600 p-0.5 bg-white dark:bg-gray-700"
          title="Pick a colour"
        />
      </div>
      <button
        type="submit"
        className="flex items-center justify-center w-10 h-10 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
        title={submitLabel}
      >
        <Check size={16} />
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="flex items-center justify-center w-10 h-10 border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
        title="Cancel"
      >
        <X size={16} />
      </button>
    </form>
  );
}

function CategoryRow({ cat, onEdit, onDelete }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        <span
          className="w-4 h-4 rounded-full flex-shrink-0 ring-2 ring-white dark:ring-gray-800 shadow-sm"
          style={{ backgroundColor: cat.color }}
        />
        <span className="font-medium text-gray-900 dark:text-white text-sm truncate">
          {cat.name}
        </span>
        {cat.is_default && (
          <span className="flex-shrink-0 text-xs text-gray-400 dark:text-gray-500">
            default
          </span>
        )}
      </div>
      <div className="flex items-center gap-0.5 flex-shrink-0 ml-2">
        <button
          onClick={() => onEdit(cat)}
          className="p-2 text-gray-400 hover:text-blue-500 dark:hover:text-blue-400 rounded-md transition-colors"
          title="Edit"
          aria-label={`Edit ${cat.name}`}
        >
          <Edit2 size={14} />
        </button>
        {!cat.is_default && (
          <button
            onClick={() => onDelete(cat)}
            className="p-2 text-gray-400 hover:text-red-500 dark:hover:text-red-400 rounded-md transition-colors"
            title="Delete"
            aria-label={`Delete ${cat.name}`}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

// -------------------- Main page --------------------

export default function CategoriesPage() {
  const { data: categories, isLoading, isError } = useCategories();
  const createCategory = useCreateCategory();
  const updateCategory = useUpdateCategory();
  const deleteCategory = useDeleteCategory();

  const [showAdd, setShowAdd] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const handleCreate = async (data) => {
    try {
      await createCategory.mutateAsync(data);
      setShowAdd(false);
      toast.success('Category created');
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Failed to create category');
    }
  };

  const handleUpdate = async (data) => {
    try {
      await updateCategory.mutateAsync({ id: editingId, ...data });
      setEditingId(null);
      toast.success('Category updated');
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Failed to update category');
    }
  };

  const handleDelete = async (cat) => {
    if (
      !window.confirm(
        `Delete "${cat.name}"? Existing expenses tagged with this category are unaffected.`
      )
    )
      return;
    try {
      await deleteCategory.mutateAsync(cat.id);
      toast.success('Category deleted');
    } catch (err) {
      toast.error(err.response?.data?.detail ?? 'Failed to delete category');
    }
  };

  if (isLoading) return <SkeletonCard />;

  if (isError) {
    return (
      <div className="max-w-xl mx-auto px-4 py-6">
        <p className="text-red-500 dark:text-red-400 text-sm">
          Failed to load categories. Please refresh the page.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Tag size={20} className="text-blue-500 flex-shrink-0" />
            Categories
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Organise your expenses. Default categories can be recoloured but not deleted.
          </p>
        </div>
        {!showAdd && editingId === null && (
          <button
            onClick={() => setShowAdd(true)}
            className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors min-h-[44px]"
          >
            <Plus size={16} />
            Add
          </button>
        )}
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="p-4 bg-gray-50 dark:bg-gray-800/60 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            New Category
          </p>
          <CategoryForm
            onSubmit={handleCreate}
            onCancel={() => setShowAdd(false)}
            submitLabel="Create"
          />
        </div>
      )}

      {/* Category list */}
      <div className="space-y-2">
        {categories?.length === 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
            No categories yet.
          </p>
        )}
        {categories?.map((cat) =>
          editingId === cat.id ? (
            <div
              key={cat.id}
              className="p-4 bg-gray-50 dark:bg-gray-800/60 rounded-lg border border-blue-400 dark:border-blue-500"
            >
              <CategoryForm
                initial={cat}
                onSubmit={handleUpdate}
                onCancel={() => setEditingId(null)}
                submitLabel="Save"
              />
            </div>
          ) : (
            <CategoryRow
              key={cat.id}
              cat={cat}
              onEdit={(c) => {
                setEditingId(c.id);
                setShowAdd(false);
              }}
              onDelete={handleDelete}
            />
          )
        )}
      </div>

      {/* Count */}
      {categories && categories.length > 0 && (
        <p className="text-xs text-gray-400 dark:text-gray-500 text-right">
          {categories.length} categor{categories.length === 1 ? 'y' : 'ies'} ·{' '}
          {categories.filter((c) => !c.is_default).length} custom
        </p>
      )}
    </div>
  );
}
