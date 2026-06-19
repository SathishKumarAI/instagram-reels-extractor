import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ResearchChat from "../views/ResearchChat";
import { fmtNum } from "../lib/utils";

describe("ResearchChat", () => {
  it("renders the empty-state prompt", () => {
    render(<ResearchChat />);
    expect(screen.getByText(/Research Chat/i)).toBeDefined();
    expect(screen.getByPlaceholderText(/Ask a research question/i)).toBeDefined();
  });
});

describe("fmtNum", () => {
  it("formats thousands and millions", () => {
    expect(fmtNum(2956)).toBe("3.0K");
    expect(fmtNum(1_500_000)).toBe("1.5M");
    expect(fmtNum(null)).toBe("—");
  });
});
