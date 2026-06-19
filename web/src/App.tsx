import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { BookOpen, Clapperboard, MessagesSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import KnowledgePage from "./views/KnowledgePage";
import ReelsPage from "./views/ReelsPage";
import ResearchChat from "./views/ResearchChat";

const nav = [
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/reels", label: "Reels", icon: Clapperboard },
  { to: "/research", label: "Research", icon: MessagesSquare },
];

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
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/knowledge" replace />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/reels" element={<ReelsPage />} />
          <Route path="/research" element={<ResearchChat />} />
        </Routes>
      </main>
    </div>
  );
}
