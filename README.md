# AgnesClaw Demo Flow Guide

Voice-first merchant co-pilot demo. Show each feature end-to-end in order. **~12–15 minutes total.**

---

## Part 0: Setup (1 min)

### Launch console
```bash
cd app
uvicorn main:app --reload --port 8080
```

Open browser: **http://localhost:8080/console**

Expected: landing page with Agnes orb (large purple circle).

> Browser mic permission: **Allow** when prompted.

---

## Part 1: Voice Connection & Wake Word (2 min)

**Action:** Click orb. Listen for Charon voice (female, measured).

**Say:** *"Agnes, hello."*

**Expected:**
- Orb glows / pulses
- Transcription appears bottom-left ("Agnes hello")
- Agnes responds: *"Hi there. I'm here to help with your store. What can I do?"*
- Sentiment card top-right updates with pulse indicator

**Demo point:** Live transcription + voice feedback loop.

---

## Part 2: Customer Review Sentiment (2 min)

**Say:** *"Agnes, check my customer
- Sentiment card animates. Shows:
  - Overall sentiment gauge (numeric, pie chart)
  - Top themes: *"Great coffee", "Long wait", "Friendly staff"* (clickable chips)
  - 7-day trend sparkline
  - Footfall pattern mini-chart
- Summary panel updates with: *"Overnight, 8 reviews arrived. Sentiment: 78% positive. Key complaint: c
heckout speed."*

**Demo point:** Sentiment aggregation across channels (Google, Facebook, Instagram, Reddit). Confidence
-aware hedging ("likely a supply issue — should I check?").

---

## Part 3: Draft Customer Reply (2 min)

**Say:** *"Agnes, help me reply to the negative review about wait times."*

**Expected:**
- Message card animates into view (left panel)
- Shows: review text ("Waited 20 mins for my order...")
- Drafted reply appears below: *"Hi there — we're sorry your wait was longer than usual. We've added an
other till during peak hours. Please give us another chance!"*
- Includes: ✏️ Edit, ✓ Approve, ✗ Reject buttons
- When approved: Queued for posting (WhatsApp/Telegram integration note: "Message queued for your appro
val on social channels")

**Demo point:** Tone-aware drafting respects Soul config (warm, empathetic, never promise refunds).

---

## Part 4: Weekly Trend Report (2 min)

**Say:** *"Agnes, give me the weekly sales trend report."*

**Expected:**
- Summary panel expands. Shows formatted table:
  ```
  WEEKLY TREND REPORT
  ─────────────────────
  Peak hours: Fri–Sun 11:00–14:00, 19:00–21:00
  Avg transaction: $8.50 (↑5% vs last week)
  Top item: Garlic pork ribs (32% of sales)
  Footfall Mon–Thu: 40% lower (typical)

  Recommendation:
  • Increase pork ribs prep Friday (demand spike +18%)
  • Stock additional frozen stock by 3pm daily
  ```
- Sentiment chip highlights "Demand for ribs" with trend arrow

**Demo point:** Structured trend detection + actionable recommendations grounded in real footfall/senti
ment data.

---

## Part 5: Visual Assistant (Monitor Screen) (2 min)

**Say:** *"Agnes, monitor my screen and tell me what you see."*

**Expected:**
- Visual Assistant panel activates
- Screenshot capture happens (or simulated in offline mode)
- Agnes narrates: *"I see your Google Reviews page. 3 new positive reviews today — customers love your
coffee blend. One review mentions 'out of stock' on spice mix. Your competitors are offering similar dr
inks at lower prices. Should I draft responses?"*
- Panels auto-update: Message card shows 3 draft templates ready for approval

**Demo point:** Computer vision + live analysis. Competitive pricing signals flagged.

---

## Part 6: Operational Checklist & Crisis (1.5 min)

**Say:** *"Agnes, start the morning prep checklist."* (or) *"Agnes, health inspector just arrived."*

#### Morning scenario
**Expected:**
- Checklist card appears with:
  ```
  OPENING CHECKLIST — 08:00
  ────────────────────────
  [ ] Till float counted ($200)
  [ ] Espresso machine heated
  [ ] Chiller temps checked (4°C)
  [ ] Daily specials updated online
  [ ] Volunteer shift roster confirmed
  ```
- Agnes: *"We have 2 volunteers confirmed. Coffee stocks good. Proceed with opening."*

#### Crisis scenario: *"Health inspector arrived"*
**Expected:**
- Checklist card switches to Crisis protocol:
  ```
  CRISIS: HEALTH INSPECTION
  ─────────────────────────
  1. ✓ Check chiller temps (staff on it)
  2. Inspect under-sink storage (risk: unlabeled bottles)
  3. Review food handling practices
  4. Document any remediation timelines

  SUGGESTED ACTIONS:
  • Photograph all labels and temperature logs
  • Notify volunteer coordinator (Wei Ming)
  • Log inspector findings → shared file
  ```

**Demo point:** Phase-aware prompts + crisis fallback behavior tree.

---

## Part 7: Volunteer Coordination (1 min)

**Say:** *"Agnes, message my volunteer coordinator about tonight's shift."*

**Expected:**
- Message card populates with draft:
  ```
  Draft for Telegram (Wei Ming):
  "Hi Wei — can you confirm we have
  3 staff for tonight 7pm-10pm? Friday
  is busy. Also, new volunteer Sarah
  available 8-10pm if needed."
  ```
- Shows delivery options: WhatsApp, Telegram, SMS
- Agnes: *"I can send this right now or you can edit first."*

**Demo point:** Multi-channel outbound + template system for recurring coordinator tasks.

---

## Part 8: Inventory Demand Signal (1 min)

**Say:** *"Agnes, what's trending in my community?"*

**Expected:**
- Sentiment card highlights new theme: *"Supply disruption — customers asking about spice mix"*
- Summary panel: *"Over past 48 hou
y tomorrow, avoid stockout."*

**Demo point:** Real-time demand detection from social chatter → inventory automation nudges.

---

## Part 9: Marketing Generation (1 min, optional)

**Say:** *"Agnes, generate a poster for spice mix promotion."*

**Expected:**
- Marketing card activates
- Generated image appears: promotional graphic with product photo + text ("**Fresh Spice Mix Back in St
ock!**")
- Agnes: *"Image ready for Instagram. Should I also generate a TikTok video script?"*
- Options: Share to Instagram, TikTok, WhatsApp, or download as PDF

**Demo point:** End-to-end content generation (text → visual → distribution).

---

## Part 10: Handoff & Session Wrap (1 min)

**Say:** *"Agnes, summarize today and save my session."*

**Expected:**
- Summary panel expands with final report:
  ```
  SESSION SUMMARY — 06:15
  ────────────────────────
  ✓ 8 customer reviews monitored
  ✓ 3 replies drafted + approved
  ✓ Weekly trend report generated
  ✓ Crisis protocol triggered (health check)
  ✓ Spice mix reorder flagged
  ✓ 1 volunteer shift confirmed

  OVERNIGHT RECOMMENDATIONS (queued):
  • Monitor stockout sentiment spike
  • Reorder spice mix by 5pm
  • Approve volunteer shift confirmation
  ```
- Agnes: *"All set. Your session is saved. See you tomorrow!"*
- Orb dims. Session persists to Firestore (if enabled).

**Demo point:** Session persistence + next-day continuity.

---

## Part 11: Offline Fallback (optional, 30s)

**Action:** Unplug network / disable APIs. Try voice command.

**Say:** *"Agnes, what's my invento
- Agnes responds using cached merchant data
- Message card shows: *"(Offline mode: using cached data) Inventory snapshot from 2 hours ago..."*
- No outbound calls attempted (graceful degradation)

**Demo point:** Resilience. Console runs offline; just no external integrations.

---

## Talking Points (30s closing)

**Mention:**

1. **Always-on listening** — Voice console handles barge-in (interrupt mid-sentence). Charon voice pers
ona consistent across all interactions.

2. **Progressive trust** — First session asks for merchant details (store name, location, hours). Subse
quent sessions remember and build on that context.

3. **Grounding layer** — Every tool call is whitelist-validated before execution. No hallucinated actio
ns.

4. **Multi-agent orchestration** — Root orchestrator routes to specialists (Message_Agent, Trend_Engine
, Complication_Advisor, etc.) based on intent. Each has its own tools & constraints.

5. **Channel integration roadmap** — Telegram/WhatsApp webhooks live in code; ready to activate with AP
I keys. Volunteers can chat directly; Agnes responds autonomously or queues for merchant approval.

## Troubleshooting Live Demo

| Issue | Fix |
|-------|-----|
| Mic not working | Check browser permission + speaker/mic hardware |
| No transcription | Reload `/console` page + allow mic again |
| Orb unresponsive | Check `uvicorn` logs for Python errors; restart server |
| Panels not updating | Open browser DevTools → Console tab; check for JS errors |
| No sentiment data (offline) | Expected. Fixture data still loads; external APIs return empty graceful
ly |
| Slow response | Vertex AI / ADK first call has cold-start (5–10s). Subsequent calls ~1–2s |

---

## Post-Demo Q&A Prompts

- **"Can multiple merchants share one console?"** Yes — tenant isolation via `session_id`. Multi-mercha
nt roadmap uses Firestore namespacing.
- **"What happens if internet drops mid-session?"** WebSocket closes cleanly. Session state saved. Next
 connection auto-hydrates.
- **"Can merchants customize voice?"** Voice persona (Charon) is fixed for now. Roadmap: support for re
gional accents / gender options.
- **"How do you handle PII?"** Merchant data is anonymized fixture + Firestore-only storage. No chat lo
gs sent externally.
- **"Can I integrate my own tools?"** Yes. Add to `app/hlm_orchestrator/tools.py` + grounding whitelist
. ADK handles execution.

---

## Timing Sheet
| Volunteer coord | 1 min | 13:30 |
| Inventory demand | 1 min | 14:30 |
| Marketing (opt) | 1 min | 15:30 |
| Wrap + summary | 1 min | 16:30 |
| **TOTAL** | **~12–16 min** | — |

> **Adapt to time available.** If short on time, skip "Volunteer coord" + "Marketing gen". Must-see: Vo
ice connection, Sentiment, Draft, Trend, Checklist/Crisis.
