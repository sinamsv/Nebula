"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import {
  FolderKanban,
  Plus,
  Search,
  ChevronDown,
  Pin,
  MoreVertical,
  Pencil,
  Trash2,
  X,
  Check,
  AlertCircle
} from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import {
  listProjects,
  createProject,
  updateProject,
  deleteProject,
  ApiError
} from "@/lib/api";
import type { ProjectMetadata } from "@/types/api";
import { LoadingSpinner } from "@/components/ProtectedRoute";
import Banner from "@/components/Banner";
import GlassPanel from "@/components/GlassPanel";

export default function ProjectsPage() {
  const { token, user } = useAuth();
  const router = useRouter();

  // State
  const [projects, setProjects] = useState<ProjectMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sorting and Search
  const [sortBy, setSortBy] = useState<"name" | "updated" | "created">("updated");
  const [showSortDropdown, setShowSortDropdown] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearchInput, setShowSearchInput] = useState(false);

  // Create Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDesc, setNewProjectDesc] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Edit Modal
  const [editingProject, setEditingProject] = useState<ProjectMetadata | null>(null);
  const [editProjectName, setEditProjectName] = useState("");
  const [editProjectDesc, setEditProjectDesc] = useState("");
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Delete Inline Confirmation
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Open Three-Dot Menus
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);

  const menuRef = useRef<HTMLDivElement>(null);
  const sortRef = useRef<HTMLDivElement>(null);

  // Fetch projects
  const fetchProjectsList = useCallback(async () => {
    if (!token || !user?.username) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await listProjects(token, user.username);
      setProjects(res.projects);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load your projects.");
    } finally {
      setIsLoading(false);
    }
  }, [token, user?.username]);

  useEffect(() => {
    fetchProjectsList();
  }, [fetchProjectsList]);

  // Click outside handlers
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setActiveMenuId(null);
      }
      if (sortRef.current && !sortRef.current.contains(e.target as Node)) {
        setShowSortDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Handlers
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    if (!newProjectName.trim()) {
      setCreateError("Project name is required.");
      return;
    }
    setIsCreating(true);
    setCreateError(null);
    try {
      const project = await createProject(token, newProjectName, newProjectDesc);
      setIsCreateModalOpen(false);
      setNewProjectName("");
      setNewProjectDesc("");
      router.push(`/dashboard/projects/${project.id}`);
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Couldn't create the project.");
    } finally {
      setIsCreating(false);
    }
  };

  const handleTogglePin = async (e: React.MouseEvent, project: ProjectMetadata) => {
    e.stopPropagation();
    if (!token) return;
    setActiveMenuId(null);

    // Optimistic update
    const updatedPinned = !project.pinned;
    setProjects(prev =>
      prev.map(p => (p.id === project.id ? { ...p, pinned: updatedPinned } : p))
    );

    try {
      await updateProject(token, project.id, { pinned: updatedPinned });
    } catch (err) {
      // Revert optimistic update
      setProjects(prev =>
        prev.map(p => (p.id === project.id ? { ...p, pinned: project.pinned } : p))
      );
      setError(err instanceof ApiError ? err.message : "Failed to toggle pin.");
    }
  };

  const handleStartEdit = (e: React.MouseEvent, project: ProjectMetadata) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setEditingProject(project);
    setEditProjectName(project.name);
    setEditProjectDesc(project.description);
    setEditError(null);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !editingProject) return;
    if (!editProjectName.trim()) {
      setEditError("Project name is required.");
      return;
    }
    setIsSavingEdit(true);
    setEditError(null);
    try {
      const updated = await updateProject(token, editingProject.id, {
        name: editProjectName,
        description: editProjectDesc
      });
      setProjects(prev => prev.map(p => (p.id === editingProject.id ? updated : p)));
      setEditingProject(null);
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to update metadata.");
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!token) return;
    try {
      await deleteProject(token, id);
      setProjects(prev => prev.filter(p => p.id !== id));
      setConfirmDeleteId(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete the project.");
    }
  };

  // Filter and Sort Projects
  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedProjects = [...filteredProjects].sort((a, b) => {
    if (sortBy === "name") {
      return a.name.localeCompare(b.name);
    } else if (sortBy === "created") {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    } else {
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    }
  });

  const pinnedProjects = sortedProjects.filter(p => p.pinned);
  const standardProjects = sortedProjects.filter(p => !p.pinned);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto px-4 py-6 sm:px-6 md:py-8">
      {/* Top Banner Error */}
      {error && (
        <div className="mb-4">
          <Banner variant="error">{error}</Banner>
        </div>
      )}

      {/* Header Container */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between md:gap-0 mb-6">
        <div className="flex flex-col md:flex-row md:items-center md:gap-6 w-full">
          {/* Responsive Heading with Specified Margin Gaps */}
          <h1 className="text-2xl font-bold font-display order-3 mt-16 md:mt-0 md:order-1 sm:text-3xl text-gradient-brand">
            Projects
          </h1>

          {/* Search, Sort, New Project controls */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center order-1 md:order-2 md:ml-auto w-full md:w-auto">
            {/* Search & Sort Row */}
            <div className="flex items-center justify-end gap-2 w-full sm:w-auto">
              {showSearchInput && (
                <input
                  type="text"
                  placeholder="Search projects..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="px-3 py-1.5 text-sm bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-nebula-purple transition-all w-full sm:w-48 text-nebula-text"
                />
              )}
              <button
                onClick={() => setShowSearchInput(!showSearchInput)}
                className="p-2 text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-lg transition-colors cursor-pointer"
                title="Search"
              >
                <Search className="h-5 w-5" />
              </button>

              {/* Sort Dropdown */}
              <div ref={sortRef} className="relative">
                <button
                  onClick={() => setShowSortDropdown(!showSortDropdown)}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs text-nebula-text-secondary hover:text-nebula-text bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
                >
                  <span>Sort: {sortBy === "name" ? "Name" : sortBy === "updated" ? "Recently Updated" : "Created"}</span>
                  <ChevronDown className="h-3.5 w-3.5" />
                </button>
                {showSortDropdown && (
                  <div className="absolute right-0 mt-1 z-30 w-40 bg-nebula-surface border border-white/10 rounded-lg shadow-xl py-1">
                    <button
                      onClick={() => { setSortBy("updated"); setShowSortDropdown(false); }}
                      className={cn("w-full text-left px-3 py-2 text-xs hover:bg-white/5 transition-colors text-nebula-text-secondary", sortBy === "updated" && "text-nebula-purple font-semibold")}
                    >
                      Recently Updated
                    </button>
                    <button
                      onClick={() => { setSortBy("name"); setShowSortDropdown(false); }}
                      className={cn("w-full text-left px-3 py-2 text-xs hover:bg-white/5 transition-colors text-nebula-text-secondary", sortBy === "name" && "text-nebula-purple font-semibold")}
                    >
                      Name
                    </button>
                    <button
                      onClick={() => { setSortBy("created"); setShowSortDropdown(false); }}
                      className={cn("w-full text-left px-3 py-2 text-xs hover:bg-white/5 transition-colors text-nebula-text-secondary", sortBy === "created" && "text-nebula-purple font-semibold")}
                    >
                      Created
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* New Project Button */}
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center justify-center gap-1.5 w-full sm:w-auto px-4 py-2 text-sm bg-gradient-to-r from-nebula-purple to-nebula-pink text-white rounded-lg hover:opacity-90 font-medium shadow-md transition-all cursor-pointer order-2 md:order-3"
            >
              <Plus className="h-4 w-4" />
              <span>New Project</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {projects.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
          <FolderKanban className="h-12 w-12 text-nebula-text-tertiary mb-3 animate-pulse" />
          <h3 className="text-lg font-medium text-nebula-text">No projects yet</h3>
          <p className="text-sm text-nebula-text-secondary max-w-sm mt-1">
            Projects let you build scoped, custom knowledge workspaces with their own system instructions and files.
          </p>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="mt-4 px-4 py-2 text-sm bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 text-nebula-text transition-all font-medium cursor-pointer"
          >
            Create first project
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {/* Pinned Projects Section */}
          {pinnedProjects.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-1.5 px-1">
                <Pin className="h-3.5 w-3.5 text-nebula-purple" />
                <span className="text-xs font-semibold uppercase tracking-wider text-nebula-text-secondary/70">Pinned</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {pinnedProjects.map((p) => renderCard(p))}
              </div>
              {standardProjects.length > 0 && (
                <div className="border-t border-white/5 my-2" />
              )}
            </div>
          )}

          {/* Standard Projects Section */}
          {standardProjects.length > 0 && (
            <div className="flex flex-col gap-3">
              {pinnedProjects.length > 0 && (
                <span className="text-xs font-semibold uppercase tracking-wider text-nebula-text-secondary/70 px-1">All Projects</span>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {standardProjects.map((p) => renderCard(p))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-nebula-surface border border-white/10 rounded-2xl p-6 shadow-glow-soft animate-scale-in">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold font-display text-nebula-text">Create Project</h2>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="p-1.5 text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-lg cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {createError && (
              <div className="mb-4">
                <Banner variant="error">{createError}</Banner>
              </div>
            )}

            <form onSubmit={handleCreate} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-nebula-text-secondary">Project Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. My Website Bot"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="px-3.5 py-2 text-sm bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-nebula-purple text-nebula-text w-full"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-nebula-text-secondary">Description (Optional)</label>
                <textarea
                  placeholder="Briefly describe what this project represents..."
                  value={newProjectDesc}
                  onChange={(e) => setNewProjectDesc(e.target.value)}
                  rows={3}
                  className="px-3.5 py-2 text-sm bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-nebula-purple text-nebula-text w-full resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 text-sm text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="px-4 py-2 text-sm bg-gradient-to-r from-nebula-purple to-nebula-pink text-white rounded-xl hover:opacity-90 font-medium disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                >
                  {isCreating ? <LoadingSpinner /> : null}
                  <span>Create</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-nebula-surface border border-white/10 rounded-2xl p-6 shadow-glow-soft animate-scale-in">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold font-display text-nebula-text">Edit Project Details</h2>
              <button
                onClick={() => setEditingProject(null)}
                className="p-1.5 text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-lg cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {editError && (
              <div className="mb-4">
                <Banner variant="error">{editError}</Banner>
              </div>
            )}

            <form onSubmit={handleSaveEdit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-nebula-text-secondary">Project Name</label>
                <input
                  type="text"
                  required
                  placeholder="Project Name"
                  value={editProjectName}
                  onChange={(e) => setEditProjectName(e.target.value)}
                  className="px-3.5 py-2 text-sm bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-nebula-purple text-nebula-text w-full"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-nebula-text-secondary">Description</label>
                <textarea
                  placeholder="Description..."
                  value={editProjectDesc}
                  onChange={(e) => setEditProjectDesc(e.target.value)}
                  rows={3}
                  className="px-3.5 py-2 text-sm bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-nebula-purple text-nebula-text w-full resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setEditingProject(null)}
                  className="px-4 py-2 text-sm text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingEdit}
                  className="px-4 py-2 text-sm bg-gradient-to-r from-nebula-purple to-nebula-pink text-white rounded-xl hover:opacity-90 font-medium disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                >
                  {isSavingEdit ? <LoadingSpinner /> : null}
                  <span>Save</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );

  // Card rendering helper
  function renderCard(p: ProjectMetadata) {
    const isConfirmingDelete = confirmDeleteId === p.id;
    const isMenuOpen = activeMenuId === p.id;

    return (
      <GlassPanel
        key={p.id}
        onClick={() => router.push(`/dashboard/projects/${p.id}`)}
        className="group relative flex flex-col p-5 h-44 hover:border-white/20 transition-all cursor-pointer"
      >
        {isConfirmingDelete ? (
          <div className="flex flex-col justify-between h-full w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start gap-2 text-red-300">
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <div className="flex flex-col">
                <span className="font-semibold text-sm">Delete project?</span>
                <span className="text-xs text-nebula-text-secondary mt-1">This will permanently delete "{p.name}" and all of its scoped conversations and file uploads. This action is irreversible.</span>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-3">
              <button
                onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(null); }}
                className="px-3 py-1.5 text-xs text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={(e) => handleDelete(e, p.id)}
                className="px-3 py-1.5 text-xs bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors cursor-pointer"
              >
                Delete
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col justify-between h-full w-full">
            <div>
              {/* Top Row: Name and Pin badge / Menus */}
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-2 min-w-0">
                  <h3 className="font-semibold font-display text-nebula-text truncate text-base group-hover:text-gradient-brand">
                    {p.name}
                  </h3>
                  {p.pinned && (
                    <Pin className="h-3.5 w-3.5 text-nebula-purple flex-shrink-0 transform rotate-45" />
                  )}
                </div>

                {/* Dropdown Wrapper */}
                <div ref={isMenuOpen ? menuRef : null} className="relative flex-shrink-0">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveMenuId(isMenuOpen ? null : p.id);
                    }}
                    className="p-1 text-nebula-text-secondary hover:text-nebula-text hover:bg-white/5 rounded-md transition-colors cursor-pointer"
                    title="Options"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>

                  {isMenuOpen && (
                    <div className="absolute right-0 mt-1 z-30 w-44 bg-nebula-surface border border-white/10 rounded-lg shadow-xl py-1" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={(e) => handleTogglePin(e, p)}
                        className="flex items-center gap-2 w-full text-left px-3 py-2 text-xs text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text transition-colors"
                      >
                        <Pin className="h-3.5 w-3.5 text-nebula-purple" />
                        <span>{p.pinned ? "Unpin" : "Pin to top"}</span>
                      </button>
                      <button
                        onClick={(e) => handleStartEdit(e, p)}
                        className="flex items-center gap-2 w-full text-left px-3 py-2 text-xs text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text transition-colors"
                      >
                        <Pencil className="h-3.5 w-3.5 text-blue-400" />
                        <span>Rename & Edit</span>
                      </button>
                      <div className="h-px bg-white/5 my-1" />
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenuId(null);
                          setConfirmDeleteId(p.id);
                        }}
                        className="flex items-center gap-2 w-full text-left px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        <span>Delete Project</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-nebula-text-secondary line-clamp-2 mt-2 select-none">
                {p.description || "No description provided."}
              </p>
            </div>

            {/* Bottom Row: Timestamp */}
            <div className="text-[10px] text-nebula-text-tertiary select-none">
              Updated {formatRelativeTime(p.updated_at)}
            </div>
          </div>
        )}
      </GlassPanel>
    );
  }
}
