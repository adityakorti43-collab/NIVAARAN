import { Bot, Calculator, FileStack, Gauge, ListChecks, ReceiptText, ScrollText } from "lucide-react";

export const NAV_GROUPS = [
  { label: "Overview", items: [{ to: "/dashboard", label: "Dashboard", icon: Gauge }] },
  {
    label: "Analyse", items: [
      { to: "/documents", label: "Documents", icon: FileStack },
      { to: "/claim", label: "Claim workspace", icon: ReceiptText },
    ],
  },
  {
    label: "Understand", items: [
      { to: "/what-if", label: "What-if calculator", icon: Calculator },
      { to: "/assistant", label: "Assistant", icon: Bot },
    ],
  },
  {
    label: "Act", items: [
      { to: "/actions", label: "Next steps", icon: ListChecks },
      { to: "/reports", label: "Reports", icon: ScrollText },
    ],
  },
];

export const NAV = NAV_GROUPS.flatMap((g) => g.items);
