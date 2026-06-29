# MetaLearn UI/UX Mockup — Antigravity Edition

This directory contains a high-fidelity, interactive, and completely client-side Single Page Application (SPA) mockup for **MetaLearn**, designed by the Antigravity agent.

## Design Highlights

1. **Premium Dark Theme**: Features a deep cosmic palette (rich dark blues, glowing neon accents, cyber cyan, and emerald) designed to optimize visual focus and learning engagement.
2. **Glassmorphism**: Elegant translucent panels utilizing `backdrop-filter: blur()` to create high-end depth and layering.
3. **Fluid Micro-Animations**: Smooth visual transitions for routing, quiz validation feedback (success/error states), and interactive slider updates.
4. **Data-Driven Architecture**: Fully client-side rendering engine that parses structured JSON schemas to dynamically build quiz types and animations.

## Key Screens & Flows

1. **Landing Page**: Immersive entry point with a live, zero-friction interactive demo of a neural network slider widget.
2. **Onboarding Quiz (Core)**: A diagnostic setup wizard that tests knowledge, captures goals (e.g., career switch, skill building), and schedules lessons.
3. **Registration / Login**: Smooth entrance gate preserving user choices into the database/state.
4. **Library**: Topics catalog (e.g., Deep Learning, Data Structures, Quantum Physics) driven by JSON.
5. **Study Screen (Core)**: Immersive player that supports:
   - Text blocks
   - Multiple choice quizzes (live check & explanation)
   - Interactive matching pairs
   - Drag-and-drop sort lists
   - Math simulators (weight multiplier adjustments)
6. **My Page**: Dashboard showing daily progress, XP, streaks, and current course paths.

## Interactive Content JSON Schema

All lessons are configured as JSON structures, allowing the engine to adapt to different layouts without hardcoded components:

```json
{
  "id": "lesson-1",
  "title": "Neural Networks Basics",
  "pages": [
    {
      "type": "content",
      "title": "...",
      "body": "..."
    },
    {
      "type": "quiz-choice",
      "question": "...",
      "options": [{"id": "a", "text": "...", "correct": true}],
      "explanation": "..."
    },
    {
      "type": "quiz-match",
      "question": "...",
      "pairs": [{"left": "...", "right": "..."}]
    },
    {
      "type": "quiz-sort",
      "question": "...",
      "items": [{"id": "1", "text": "..."}]
    }
  ]
}
```

## How to Run

Simply open [index.html](index.html) in any modern web browser. No compilation, node modules, or servers are strictly required, though a local static server (e.g. `npx serve`, VS Code Live Server) works perfectly.
