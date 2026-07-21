import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { ArrowLeft, BookOpen, Clapperboard, Home, KanbanSquare, Link2, MessagesSquare, Palette, ScrollText, Search, Table2, Tag } from "lucide-react";
import { cn } from "@/lib/utils";
import { THEME_OPTIONS, type ThemeMode, loadTheme, saveTheme } from "@/lib/theme";
import HomePage from "./views/HomePage";
import KanbanPage from "./views/KanbanPage";
import KnowledgePage from "./views/KnowledgePage";
import ReaderPage from "./views/ReaderPage";
import ReelsPage from "./views/ReelsPage";
import ResearchChat from "./views/ResearchChat";
import SearchPage from "./views/SearchPage";
import SourcesPage from "./views/SourcesPage";
import TablePage from "./views/TablePage";
import TagsPage from "./views/TagsPage";

const nav = [
  { to: "/home", label: "Overview", icon: Home },
  { to: "/search", label: "Search", icon: Search },
  { to: "/reels", label: "Reels", icon: Clapperboard },
  { to: "/reader", label: "Reader", icon: ScrollText },
  { to: "/table", label: "Table", icon: Table2 },
  { to: "/board", label: "Board", icon: KanbanSquare },
  { to: "/tags", label: "Tags", icon: Tag },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/sources", label: "Sources", icon: Link2 },
  { to: "/research", label: "Research", icon: MessagesSquare },
];

function ThemeSwitcher() {
  const [theme, setTheme] = useState<ThemeMode>(() => loadTheme());
  return (
    <div className="mt-auto pt-4">
      <label className="mb-1 flex items-center gap-2 px-2 text-xs text-overlay0">
        <Palette size={13} /> Theme
      </label>
      <select
        value={theme}
        onChange={(e) => { const t = e.target.value as ThemeMode; setTheme(t); saveTheme(t); }}
        className="w-full rounded-lg border border-surface0 bg-base px-2 py-1.5 text-sm text-text"
      >
        {THEME_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

function TopBar() {
  const navigate = useNavigate();
  const loc = useLocation();
  // Home is the root — nothing to go back to.
  if (loc.pathname === "/home" || loc.pathname === "/") return null;
  // loc.key === "default" means the page was landed on directly (no prior
  // history entry) — fall back to Home instead of a dead back button.
  const canBack = loc.key !== "default";
  return (
    <div className="sticky top-0 z-20 flex items-center gap-1 border-b border-surface0 bg-base/80 px-6 py-2 backdrop-blur">
      <button
        onClick={() => (canBack ? navigate(-1) : navigate("/home"))}
        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-subtext transition-colors hover:bg-surface0 hover:text-text"
      >
        <ArrowLeft size={16} /> Back
      </button>
      <NavLink
        to="/home"
        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-subtext transition-colors hover:bg-surface0 hover:text-text"
      >
        <Home size={15} /> Home
      </NavLink>
    </div>
  );
}

export default function App() {
  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-surface0 bg-mantle p-3">
        <div className="mb-6 px-2 pt-2">
          <div className="text-lg font-bold text-text">Reels Research</div>
          <div className="text-xs text-overlay0">local knowledge base</div>
        </div>
        <nav className="flex flex-col gap-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-mauve/15 text-mauve"
                    : "text-subtext hover:bg-surface0 hover:text-text",
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <ThemeSwitcher />
      </aside>
      <main className="flex-1 overflow-y-auto">
        <TopBar />
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/reels" element={<ReelsPage />} />
          <Route path="/reader" element={<ReaderPage />} />
          <Route path="/table" element={<TablePage />} />
          <Route path="/board" element={<KanbanPage />} />
          <Route path="/tags" element={<TagsPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/research" element={<ResearchChat />} />
        </Routes>
      </main>
    </div>
  );
}
