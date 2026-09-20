window.PROJECTS = [
  {
    slug: "pulse",
    featured: true,
    name: "Pulse",
    year: "2026",
    status: "Live",
    oneLiner:
      "A live briefing desk for weather and earth events. Warehouse tests pass before any model writes a label.",
    problem:
      "Public feeds are late, duplicated, and messy. A useful desk has to stay trustworthy when the schema drifts.",
    approach:
      "NWS, NASA EONET, and Open-Meteo land as Bronze. Contracts must pass before Gold is labeled. The hosted page is a read replica.",
    demo: "./pulse/",
    repo: "",
    tags: ["Python", "Airflow", "AWS", "dbt", "RAG / LLM", "DuckDB"],
    highlights: [
      "Play-through: one warning walks Bronze → contracts → Gold",
      "Failed warehouse tests skip model writes",
      "Map and briefing cards sit on Gold tables, not a chatbot",
    ],
  },
];
