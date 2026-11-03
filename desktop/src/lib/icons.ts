/**
 * Hand-drawn 24×24 line icons (no icon font or external package). Each icon is
 * a list of stroked paths plus optional filled paths, in currentColor.
 */
export interface IconShape {
  stroke: string[];
  fill?: string[];
}

const circle = (cx: number, cy: number, r: number) =>
  `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;

export const ICONS = {
  // stems
  vocals: {
    stroke: [
      "M12 3a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z",
      "M5.5 11a6.5 6.5 0 0 0 13 0",
      "M12 17.5V21",
      "M8.5 21h7",
    ],
  },
  guitar: {
    stroke: [
      "M11 13l9-9",
      "M18 2.5l3.5 3.5",
      "M10.4 9.6a4 4 0 0 0-5.7 1.2c-.7 1.2-.4 2.3-1.4 3.3s-.8 2.7.7 4.2 3.1 1.6 4.1.7 2.1-.7 3.3-1.4a4 4 0 0 0 1.2-5.7",
      circle(8.5, 15.5, 1.5),
    ],
  },
  drums: {
    stroke: [
      "M4 9a8 3 0 1 0 16 0a8 3 0 1 0-16 0",
      "M4 9v7c0 1.7 3.6 3 8 3s8-1.3 8-3V9",
      "M7.5 3l4.5 6",
      "M16.5 3L12 9",
    ],
  },
  bass: {
    stroke: ["M5 19.5c6-2 10-6 10-11a5 5 0 0 0-9.6-2"],
    fill: [circle(6.6, 8.6, 1.7), circle(19, 7, 1.1), circle(19, 11.5, 1.1)],
  },
  piano: {
    stroke: [
      "M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
      "M7.5 12v7",
      "M12 12v7",
      "M16.5 12v7",
    ],
    fill: ["M6.3 5h2.4v7H6.3z", "M10.8 5h2.4v7h-2.4z", "M15.3 5h2.4v7h-2.4z"],
  },
  other: { stroke: ["M2 12h3l2-5 3 10 3-14 3 13 2-4h4"] },
  // interface
  plus: { stroke: ["M12 5v14", "M5 12h14"] },
  queue: {
    stroke: ["M4 6h16", "M4 12h9", "M4 18h6", "M15 14.5l5.5 3.5-5.5 3.5z"],
  },
  models: {
    stroke: [
      "M12 2.8l8 4.6v9.2l-8 4.6-8-4.6V7.4z",
      "M4 7.4l8 4.6 8-4.6",
      "M12 12v9.2",
    ],
  },
  settings: {
    stroke: [
      "M6 4v16",
      "M12 4v16",
      "M18 4v16",
      "M4 15h4",
      "M10 8h4",
      "M16 13h4",
    ],
  },
  folder: {
    stroke: [
      "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    ],
  },
  pause: { stroke: ["M9 5v14", "M15 5v14"] },
  play: { stroke: ["M7 4.5v15l12-7.5z"] },
  x: { stroke: ["M6 6l12 12", "M18 6L6 18"] },
  retry: { stroke: ["M20 11a8 8 0 1 0-2.3 5.7", "M20 4v7h-7"] },
  check: { stroke: ["M5 12.5l4.5 4.5L19 7"] },
  link: {
    stroke: [
      "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1",
      "M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    ],
  },
  upload: {
    stroke: [
      "M12 15V4",
      "M7.5 8.5L12 4l4.5 4.5",
      "M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3",
    ],
  },
  download: { stroke: ["M12 4v11", "M7.5 10.5L12 15l4.5-4.5", "M4 19h16"] },
  cpu: {
    stroke: [
      "M7 7h10v10H7z",
      "M10 3v4",
      "M14 3v4",
      "M10 17v4",
      "M14 17v4",
      "M3 10h4",
      "M3 14h4",
      "M17 10h4",
      "M17 14h4",
    ],
  },
  gpu: {
    stroke: [
      "M3 7h18v10H3z",
      "M7 17v3",
      "M11 17v3",
      circle(12, 12, 2.5),
      "M17.5 10v4",
    ],
  },
  ram: {
    stroke: [
      "M3 8h18v8H3z",
      "M7 11v2",
      "M11 11v2",
      "M15 11v2",
      "M6 16v3",
      "M18 16v3",
    ],
  },
  shield: {
    stroke: [
      "M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z",
      "M8.5 12l2.5 2.5 4.5-5",
    ],
  },
  external: {
    stroke: [
      "M14 4h6v6",
      "M20 4l-9 9",
      "M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4",
    ],
  },
  loop: {
    stroke: [
      "M17 2l3 3-3 3",
      "M4 11V9a4 4 0 0 1 4-4h12",
      "M7 22l-3-3 3-3",
      "M20 13v2a4 4 0 0 1-4 4H4",
    ],
  },
  reset: { stroke: ["M4 11a8 8 0 1 1 2.3 5.7", "M4 4v7h7"] },
  arrowRight: { stroke: ["M5 12h14", "M13 6l6 6-6 6"] },
  arrowLeft: { stroke: ["M19 12H5", "M11 6l-6 6 6 6"] },
  mix: {
    stroke: ["M4 12h2", "M8 8v8", "M12 4v16", "M16 7v10", "M20 10v4"],
  },
  scissors: {
    stroke: [
      circle(6, 7, 2.5),
      circle(6, 17, 2.5),
      "M8 8.5L20 18",
      "M8 15.5L20 6",
    ],
  },
} satisfies Record<string, IconShape>;

export type IconName = keyof typeof ICONS;
