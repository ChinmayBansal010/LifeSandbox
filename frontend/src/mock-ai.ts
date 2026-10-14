/* ─── Mock AI response adapter ─────────────────────────────────────── */

const MOCK_RESPONSES = [
  `That's a fascinating question. Let me think through the implications step by step.

When we consider this decision, there are several factors worth weighing:

1. **Short-term impact**: The immediate effects would likely involve some adjustment period, but the disruption should be manageable.
2. **Long-term trajectory**: This path tends to open up opportunities that aren't obvious at first glance.
3. **Reversibility**: One advantage here is that most of the changes can be unwound if needed.

Would you like to explore any of these dimensions further?`,

  `I can see why this is on your mind. Let me offer a different perspective.

The conventional wisdom here might suggest playing it safe, but there's evidence that bold moves in situations like this tend to pay off — not because of the outcome itself, but because of the skills and resilience you build along the way.

That said, here are some concrete things to consider:
- What's the worst realistic scenario? (Not the catastrophic extreme, but a plausible downside.)
- What would you regret more: trying and failing, or never finding out?
- Are there ways to test this on a smaller scale first?`,

  `Great question. Let me map out the landscape for you.

**Option A** (the status quo) has the advantage of predictability. You know what you're getting, and there's comfort in that. But comfort and growth rarely coexist.

**Option B** (the change) introduces uncertainty, but also opens up:
- New relationships and networks
- Skills you wouldn't otherwise develop
- A sense of agency over your own trajectory

The research on decision-making suggests that people tend to overestimate the risk of change and underestimate their ability to adapt. What matters most to you in this decision?`,

  `That's worth exploring from multiple angles.

Here's what I notice about this situation: you're weighing a known quantity against an unknown possibility. The known quantity feels "safer" because you can predict it, but prediction and preference aren't the same thing.

**A useful exercise**: imagine yourself five years from now. Which version of yourself would you rather be — the one who stayed the course, or the one who took the leap? Both are valid; the point is to be honest about which one resonates more.

What does your gut tell you, setting aside all the practical considerations for a moment?`,

  `Let me break this down into the moving parts.

**Financial dimension**: The numbers matter, but they're rarely the whole story. A modest financial hit that positions you for growth often beats a comfortable plateau.

**Relational dimension**: How will this affect the people closest to you? Not just in the short term, but in terms of the example it sets and the energy you bring to your relationships.

**Personal dimension**: Will this decision align with the person you're becoming, or the person you used to be?

I find that the best decisions aren't the ones that optimize for a single metric — they're the ones that create alignment across these dimensions. Where do you feel the most alignment right now?`,

  `Interesting. Let me challenge a hidden assumption here.

You might be framing this as a binary choice — do it or don't — when there might be a third path you haven't considered yet. What if you could:

1. **Prototype the change** without fully committing
2. **Set clear criteria** for evaluating whether it's working
3. **Build in exit ramps** so the decision feels less permanent

This reduces the stakes significantly. Instead of a life-altering leap, it becomes an experiment — and experiments are allowed to fail. That's the whole point.

What would a small, reversible version of this look like?`,
];

import type { ScenarioNode } from './types';

let responseIndex = 0;

export async function getMockResponse(
  userMessage: string,
  rememberedContext?: ScenarioNode[]
): Promise<string> {
  // Simulate network latency
  const delay = 800 + Math.random() * 1200;
  await new Promise((resolve) => setTimeout(resolve, delay));

  // Use a deterministic but varied selection based on both index and message
  const hash = userMessage.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const idx = (hash + responseIndex) % MOCK_RESPONSES.length;
  responseIndex++;

  let response = MOCK_RESPONSES[idx];

  // If there are remembered exchanges from alternate branches, weave in a contextual note
  if (rememberedContext && rememberedContext.length > 0) {
    const memoryHighlights = rememberedContext
      .slice(0, 2)
      .map((n) => `"${n.userMessage.length > 35 ? n.userMessage.slice(0, 35) + '…' : n.userMessage}"`)
      .join(' and ');
    const contextPrefix = `> *Persisted context from alternate branch (${memoryHighlights}):*\n> Remembering what we previously explored as we branch here.\n\n`;
    response = contextPrefix + response;
  }

  return response;
}
