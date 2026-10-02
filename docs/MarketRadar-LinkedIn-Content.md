# MarketRadar — LinkedIn Content Kit

Ready-to-post content. Every claim here is accurate to what MarketRadar currently implements; future directions are labelled as such.

---

# 1. LinkedIn Article

**Suggested title:** *Commerce has more data than ever. That's not the problem.*

---

Commerce has more data than ever. Product listings, prices, merchant sites, local business records, marketplace listings, ratings, reviews. It is all public, and there is more of it every year.

That is not the problem. The problem is that none of it arrives as intelligence.

It arrives as fragments. A price with no reliable indication of which product it belongs to. A business name that may or may not be the same business you already have on file. A search result that might be a shop — or might be a directory listing shops. A number with no timestamp, so you cannot tell whether anything has moved.

The gap between having data and having intelligence is where most commerce research time actually goes. And where most of it is wasted.

## What turns data into intelligence

A single fact: **$19.99**.

On its own, unusable. Now add context:

- **Which product** — exact brand, variant, size, pack quantity
- **Which merchant** — and are you confident it is that merchant?
- **Where** — the location the search was scoped to
- **When** — a timestamp
- **From what source** — the exact page it came from
- **How confident** — verified, or merely observed?

Same number. Now it is intelligence, because you can act on it, check it, and compare it to something else.

A price missing any one of those is not intelligence. It is a number that looks like intelligence — which is worse than no number at all.

## Three places this goes wrong

I have been building **MarketRadar**, a commerce and market intelligence platform, and three problems have turned out to matter more than everything else combined.

**1. Identity.** The same business appears as "Smith & Co Wines", "Smith and Company", and a domain matching neither. Two branches of one chain appear as two results sharing one website. Merge them and you lose a location. Split them and you invent a competitor.

A specific trap: small businesses often list a **social media page as their website**. Treat that page as the business's own domain and every business doing the same collapses into one record. The page is real evidence the business exists. It is not an identity.

**2. Attribution.** A price on a category page belongs to *some* product in that list — not necessarily the one you searched for. A 50ml price attached to a 750ml query is confidently, expensively wrong. And a product can be genuinely stocked while its price simply cannot be attributed.

Which leads to a distinction most tools collapse:

> **"Price not verified" does not mean "product not available."**

Four states, not two: **verified**, **unavailable**, **unknown**, **unverified**. Collapsing them to found/not-found loses exactly the distinction that carries the risk.

**3. Repetition mistaken for measurement.** This one is subtle, and I got it wrong before I got it right.

Any system that respects its data provider's cost will cache responses. Re-run the same search and you get identical data back. If each run is recorded as an observation, you accumulate several records describing **one** measurement.

A naive system sees three records with the same value and reports "stable". It has not observed stability. It has read the same answer three times.

In the real data, every merchant with repeat observations had exactly one distinct value. Three records. One measurement. Reporting that as a trend would have been confidence manufactured out of nothing.

## Evidence first. AI second.

This is the part I would argue hardest for.

A language model asked to analyse a market will produce a fluent answer whether or not the evidence supports it. Fluency is not accuracy, and in commerce the errors are expensive: an invented price, a competitor described as failing, a trend asserted from a single data point.

The answer is not a better prompt. It is a different ordering:

```
Evidence  →  Structured Facts  →  AI Analysis  →  Human Decision
```

The facts are computed by code. The AI receives those facts — never the raw data — and explains them. Its output is checked against the facts before anyone sees it.

The practical consequence: **if the AI is unavailable, the factual analysis is still there.** Only the narration is missing. That is the correct dependency direction, and it is the opposite of how most "AI-powered" tools are built.

It also requires a vocabulary that can express uncertainty, because a system that cannot will manufacture certainty:

**verified · discovered · uncertain · unknown · unavailable · insufficient history**

Six states. The one that matters most is **unknown** — meaning insufficient evidence either way, and explicitly *not* a negative finding.

Three cases where the honest answer and the confident answer diverge:

- If a price cannot be verified, do not say the product is unavailable. A shop that stocks it would be reported as not stocking it.
- If a competitor is absent from one search, do not say the business has closed. Search results vary. That conclusion is wrong and potentially damaging to a real company.
- If there is one measurement, do not claim a trend. "Prices are falling" from a single reading is a fabrication with a number attached — the most persuasive kind of error.

## What MarketRadar actually does

Seven layers, each consuming only the one beneath it:

**Market Research** → search visibility for a market in a resolved location
**Competitor Intelligence** → who actually operates here, with identity resolved
**Product Intelligence** → what they offer, matched strictly
**Price Intelligence** → what can genuinely be verified about price
**Trend Intelligence** → what has changed, across distinct measurements
**Market Pulse** → one coherent snapshot per market and place
**AI Analyst** → what the evidence shows, with references back to it

It is industry-agnostic by design. Nothing in it is specific to a category, retailer or country — it has been exercised against coffee shops, automotive repair and wine retail without changing a line.

A real output, from real data:

> *"5 verified businesses were observed in this market and location."*
> *"1 verified price measurement is available: $19.99 for the exact product and size requested."*
> *"2 product observations are 'unknown' — the evidence was insufficient either way. That is not a finding that the merchant does not stock the product."*
> *"2 businesses were not present in the latest observation. Absence from one search is not evidence that a business has closed or left the market."*

Less exciting than "Competitor X is losing ground." Considerably more useful, because every line traces back to a specific record.

## Where this applies

The concept is category-agnostic: grocery, electronics, fashion, automotive, beauty, home and furniture, sports and fitness, B2B.

The strongest case is probably **small businesses**. The gap between what a large retailer knows about its market and what an independent knows is largely a tooling gap. Enterprise market intelligence exists — priced for enterprises.

## What is still ahead

Continuous monitoring so history accumulates without manual searching. Marketplace intelligence across channels. Financial intelligence — pricing economics, margin analysis. Predictive analytics, with enough history to support it honestly. Conversational analysis over recorded evidence.

None of that is built. I would rather say so than imply otherwise.

And whatever gets added, the ordering holds. **Evidence first. AI second.**

A monitoring system that reports phantom changes is worse than no monitoring. A predictive model built on cached repeats is worse than no model. Capability without evidence discipline does not produce better intelligence. It produces more confident errors, faster.

---

*MarketRadar is a commerce and market intelligence platform: FastAPI, React, and a strict evidence model. Always happy to talk about the identity and attribution problems — they are harder and more interesting than they look.*

---
---

# 2. Headline options

**Problem-led**
1. Commerce has more data than ever. That's not the problem.
2. The hardest problem in commerce data isn't collection. It's identity.
3. Why "price not verified" must never mean "product not available"
4. Three records. One measurement. Why most trend analysis is wrong.

**Principle-led**
5. Evidence first. AI second.
6. I built a market intelligence platform that refuses to guess
7. What a market intelligence tool should say when it doesn't know
8. Building AI that can't invent facts — by not letting it produce them

**Build-led**
9. Building MarketRadar: turning fragmented commerce data into structured intelligence
10. 481 tests, and most of them exist to stop the system overstating what it knows

**Insight-led**
11. Absence of evidence is not evidence of absence — especially in commerce data
12. The six words that made our market intelligence trustworthy

> **Recommended:** #1 for reach, #5 for positioning, #4 for a technical audience.

---

# 3. Opening hooks

1. Commerce has more data than ever. But data alone doesn't create intelligence.
2. A price without a product, a merchant, a place and a timestamp isn't intelligence. It's a number that looks like one.
3. Three records in the database. All the same value. A naive system calls that "stable". It isn't — we read the same cached answer three times.
4. "Price not verified" does not mean "product not available." Most tools collapse those. It's the distinction that carries the risk.
5. A language model asked to analyse a market will produce a fluent answer whether the evidence supports it or not.
6. Small businesses don't lack market intelligence because the data is private. They lack it because the tooling is priced for enterprises.
7. The most useful thing a market intelligence tool can say is "I don't have enough evidence to tell you that."
8. Two branches of one chain look like two businesses. Merge them and you lose a location. Split them and you invent a competitor.

---

# 4. One-line description

> **MarketRadar turns fragmented commerce data — products, prices, merchants, trends — into structured market intelligence, with the confidence of every claim stated and the evidence behind it retained.**

**Alternatives:**
- An industry-agnostic commerce and market intelligence platform built on a strict evidence model: verified, unknown and unavailable are never confused.
- Commerce and market intelligence that states what it knows, what it doesn't, and why — evidence first, AI second.

---

# 5. Short project description
*(~60 words — LinkedIn Projects, portfolio)*

> **MarketRadar — Commerce & Market Intelligence**
>
> An industry-agnostic platform that turns fragmented commerce data into structured market intelligence. Discovers competitors, matches product identity, verifies prices against strict evidence rules, and detects change across genuinely distinct measurements. Built on an evidence-first model: facts are computed deterministically, AI narrates them under validation, and uncertainty is stated rather than smoothed over.

---

# 6. Medium project description
*(~150 words)*

> **MarketRadar — Commerce & Market Intelligence**
>
> Commerce has more data than ever, but it arrives as fragments: prices without product identity, business names that may or may not be the same business, search results that might be shops or might be directories listing shops.
>
> MarketRadar turns those fragments into structured market intelligence. It resolves locations to a canonical form before searching, separates real businesses from directories and social pages, matches product identity strictly enough that a 50ml is never mistaken for a 750ml, and verifies prices only where they can genuinely be attributed to the exact product.
>
> The architecture is evidence-first. Factual statements are computed deterministically from recorded observations, each carrying a reference back to the records behind it. An optional AI layer narrates those facts and is validated before display — it cannot introduce a figure or a conclusion the evidence doesn't support.
>
> Seven layers: Market Research, Competitors, Products, Price Intelligence, Trends, Market Pulse, AI Analyst. Industry-agnostic by design.
>
> **Stack:** FastAPI · SQLAlchemy · React · TypeScript · MUI · 481 tests

---

# 7. Taglines

**Principle**
1. **Evidence first. AI second.** ← *primary*
2. Intelligence you can trace.
3. States what it knows. And what it doesn't.

**Capability**
4. Fragmented commerce data, structured into market intelligence.
5. Products, prices, merchants, trends — with the evidence attached.
6. Market intelligence with its sources still attached.

**Contrast**
7. Not a search tool. A market intelligence model.
8. Confidence, stated — not implied.
9. The market, as the evidence actually describes it.

> **Recommended pairing:** *MarketRadar — Commerce & Market Intelligence.* **Evidence first. AI second.**

---

# 8. Hashtags

**Core (use 3–5)**
`#MarketIntelligence` `#CommerceIntelligence` `#CompetitiveIntelligence` `#PricingIntelligence` `#RetailTech`

**Technical**
`#AI` `#DataEngineering` `#EvidenceBasedAI` `#SoftwareArchitecture` `#Python` `#FastAPI` `#React` `#TypeScript`

**Business**
`#Ecommerce` `#Retail` `#SmallBusiness` `#MarketResearch` `#DataDriven` `#ProductAnalytics`

**Suggested sets**

| Audience | Tags |
| --- | --- |
| **Business** | `#MarketIntelligence #CommerceIntelligence #CompetitiveIntelligence #Retail #SmallBusiness` |
| **Technical** | `#AI #EvidenceBasedAI #SoftwareArchitecture #Python #DataEngineering` |
| **Balanced** ← recommended | `#MarketIntelligence #CommerceIntelligence #AI #Ecommerce #RetailTech` |

> LinkedIn engagement drops with tag count. **Three to five is the sweet spot.**

---

# 9. Short-form posts

### A — The measurement problem *(technical)*

> Three records in the database. All the same value.
>
> A naive system reports "stable". It isn't — we read the same cached answer three times.
>
> Any system that respects its data provider's cost caches responses. Re-run the same search, get identical data. Record each run as an observation and you accumulate several records describing **one** measurement.
>
> So: identical consecutive readings collapse into a single measurement. Direction is stated only where two or more genuinely distinct measurements exist. Everything else reports "insufficient history".
>
> Less impressive. Considerably more honest.
>
> `#MarketIntelligence #DataEngineering #AI`

### B — The vocabulary problem *(business)*

> "Price not verified" does not mean "product not available."
>
> Most commerce tools collapse those into found/not-found — and lose exactly the distinction that carries the risk.
>
> A merchant may list a product on a category page with a price that applies to the whole category. The product is genuinely there. The price simply can't be attributed to it.
>
> Report that as "unavailable" and you've made a false claim about a real business's real stock.
>
> Four states, not two: **verified · unavailable · unknown · unverified**
>
> `#CommerceIntelligence #RetailTech #PricingIntelligence`

### C — Evidence-first AI *(positioning)*

> A language model asked to analyse a market will produce a fluent answer whether the evidence supports it or not.
>
> The fix isn't a better prompt. It's a different ordering.
>
> **Evidence → Structured Facts → AI Analysis → Human Decision**
>
> Facts computed by code. The AI receives those facts — never the raw data — and explains them. Its output is validated against the facts before anyone sees it.
>
> The consequence: if the AI is unavailable, the factual analysis is still there. Only the narration is missing.
>
> That's the correct dependency direction — and the opposite of how most "AI-powered" tools are built.
>
> **Evidence first. AI second.**
>
> `#AI #EvidenceBasedAI #MarketIntelligence`

---

# 10. Accuracy notes

Before posting, these are the boundaries the content stays inside.

### Safe to claim — implemented and verified

Market research with location resolution · competitor discovery with identity resolution and classification · product intelligence with strict identity matching · price verification with a four-state vocabulary · trend detection over distinct measurements · Market Pulse snapshots · AI Analyst with deterministic facts and a validated narration layer · industry-agnostic design · 481 passing tests

### Must stay labelled as future

Financial intelligence · continuous monitoring and alerts · dedicated marketplace intelligence · predictive analytics · shopper-facing product · personalised recommendations · conversational Q&A · cross-market comparison

### Two points to state carefully

**No AI vendor is connected.** The narration layer is built, tested and validated — but nothing is generating text today. The system runs facts-only. Say "built" rather than "running".

**Trend history is thin.** The mechanism works; with a seven-day response cache, distinct measurements need searches more than a week apart, so no series yet shows a direction. This is genuinely a good story — the system says "insufficient history" instead of inventing a number — but do not imply trends are being reported.

### Never claim

Revenue increases · sales predictions · competitive outcomes · market share · "beat competitors" · "identify the market leader" · guaranteed results

---

*Evidence first. AI second.*
