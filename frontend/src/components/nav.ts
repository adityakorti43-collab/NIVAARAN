import { BarChart3, Bot, Calculator, FileStack, FlaskConical, Gauge, ListChecks, Network, ReceiptText, ScaleIcon, ScrollText, Search, Waypoints } from "lucide-react";

export const NAV_GROUPS = [
  { label: "Overview", items: [{ to: "/dashboard", label: "Dashboard", icon: Gauge }] },
  {
    label: "Analyse", items: [
      { to: "/documents", label: "Documents", icon: FileStack },
      { to: "/claim", label: "Claim workspace", icon: ReceiptText },
      { to: "/evidence", label: "Evidence explorer", icon: Search },
    ],
  },
  {
    label: "Understand", items: [
      { to: "/constellation", label: "Claim map", icon: Network },
      { to: "/money-flow", label: "Money flow", icon: Waypoints },
      { to: "/what-if", label: "What-if calculator", icon: Calculator },
      { to: "/assistant", label: "Assistant", icon: Bot },
    ],
  },
  {
    label: "Act", items: [
      { to: "/fairness", label: "Mismatch checks", icon: ScaleIcon },
      { to: "/actions", label: "Next steps", icon: ListChecks },
      { to: "/costs", label: "Treatment costs", icon: BarChart3 },
      { to: "/evaluation", label: "Evaluation", icon: FlaskConical },
      { to: "/reports", label: "Reports", icon: ScrollText },
    ],
  },
];

export const NAV = NAV_GROUPS.flatMap((g) => g.items);
