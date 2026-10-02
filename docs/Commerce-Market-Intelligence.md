# Commerce & Market Intelligence

### Turning fragmented commerce data into evidence you can act on

---

> **Commerce has more data than ever. The challenge is no longer finding data — it is turning fragmented data into useful intelligence.**

---

## A note on how to read this document

This document describes a **concept** — Commerce & Market Intelligence — and uses **MarketRadar** as a working example of that concept.

The two are not the same thing, and the difference is kept explicit throughout:

| Label | Meaning |
| --- | --- |
| **Implemented in MarketRadar** | Working today, verified against the running system |
| **Future opportunity** | Part of the concept. **Not built.** Described as possibility, never as capability |

Nothing here claims sales predictions, guaranteed revenue, or competitive outcomes. Those claims would be unsupportable, and a tool whose entire purpose is evidence discipline should not make them about itself.

---

## 1. The core idea

Every commerce business already has access to an enormous amount of public information. Product listings, prices, merchant websites, local business records, search results, ratings, reviews, marketplace listings. It is all there.

The difficulty is that none of it arrives as intelligence. It arrives as fragments:

- A price with no reliable indication of *which* product it belongs to
- A business name that may or may not be the same business as one you already know
- A search result that might be a shop, or might be a directory listing shops
- A figure with no timestamp, so you cannot tell whether anything has changed

The gap between **having data** and **having intelligence** is where most commerce research time is actually spent — and where most of it is wasted.

### The pipeline

```
Raw Data
    ↓
Structured Evidence        ← identity resolved, source recorded, confidence stated
    ↓
Context                    ← market, location, time, merchant, product
    ↓
Market Intelligence        ← organised, comparable, queryable
    ↓
AI Analysis                ← explains what the evidence shows
    ↓
Decision Support           ← a person decides
```

Each arrow is a step where something can quietly go wrong. A price attached to the wrong product. Two shops merged into one record. A cached result counted as a fresh measurement. The value of the pipeline is not that it moves data along — it is that each step is auditable and each transition is defensible.

---

## 2. What is Commerce & Market Intelligence?

In plain terms: **the practice of turning scattered commercial signals into a structured, current, trustworthy picture of a market.**

Commerce information is spread across:

| Source | What it offers | What it lacks |
| --- | --- | --- |
| Product catalogues | Names, variants, sizes | Consistency between merchants |
| Merchant websites | Authoritative product and price data | Structure; every site differs |
| Local business listings | Addresses, coordinates, ratings | Often no website |
| Marketplaces | Wide selection, comparable listings | Seller identity is ambiguous |
| Search results | Broad reach | No distinction between a shop and an article about shops |
| Ratings and reviews | Sentiment signal | No pricing or availability |
| Historical observations | Change over time | Only if someone recorded them |

### Data vs Intelligence

This distinction is the whole discipline.

| | Data | Intelligence |
| --- | --- | --- |
| **Form** | A number, a name, a URL | A statement with context and confidence |
| **Example** | `$19.99` | "One verified price of $19.99, observed at a named merchant on a product-specific page, for the exact size requested, on 26 September" |
| **Question answered** | "What is on this page?" | "What can I reasonably conclude, and how sure can I be?" |
| **Failure mode** | Looks precise, may be wrong | Says when it does not know |

A price on its own is data. The same price with **merchant, location, timestamp, product identity, and source** is intelligence — because now you can act on it, check it, and compare it to something else.

---

## 3. Why this is needed

These are ordinary, widespread problems in commerce — not hypotheticals.

**Competitors are difficult to monitor.** Knowing who competes with you in a specific place is a manual exercise repeated whenever you want it refreshed.

**Prices change frequently and without notice.** By the time a spreadsheet is compiled, some of it is already stale.

**Products appear across multiple channels** under different names, sizes and pack quantities. The same item is listed a dozen ways.

**Local availability is hard to verify.** A catalogue page proves a merchant *offers* a product. It does not prove the shop down the road has it on the shelf. These are routinely conflated.

**Marketplace information is fragmented.** Each platform is its own island with its own identifiers.

**Manual market research is slow.** A single competitive review can take days and is stale on delivery.

**Smaller businesses lack the tooling entirely.** Enterprise market intelligence platforms exist. They are priced for enterprises.

**Analysts spend their time collecting rather than analysing.** The scarce skill is interpretation; the time goes to gathering.

**Historical change is invisible unless someone recorded it.** Without a deliberate record, "has this moved?" is unanswerable.

---

## 4. The Commerce Intelligence model

```
    Products  ·  Prices  ·  Merchants  ·  Markets
    Locations ·  Marketplaces ·  Trends ·  Financial Signals
                        ↓
              Structured Evidence
                        ↓
              Market Intelligence
                        ↓
             AI-Assisted Analysis
```

### Why context is the whole game

Consider a single fact: **$19.99**.

On its own it is unusable. Add context and it becomes intelligence:

| Context | Without it |
| --- | --- |
| **Which product** — exact brand, variant, size, pack quantity | A 750ml price attached to a 50ml query is confidently wrong |
| **Which merchant** — and are you sure it is that merchant? | Two shops in a chain are not one shop |
| **Where** — the location the search was scoped to | A price in another region tells you nothing local |
| **When** — a timestamp | You cannot detect change without one |
| **From what source** — the exact page | You cannot verify a claim you cannot trace |
| **How confident** — verified, or merely observed? | A listing-page price belongs to *some* product in a list |

A price missing any one of these is not intelligence. It is a number that looks like intelligence, which is worse than no number at all.

---

## 5. Shopping Intelligence

*Concept category. MarketRadar today is a business-facing tool with no shopper-facing product — see the labelling below.*

Commerce intelligence applied to the buying side can help a shopper:

- discover products across merchants rather than one site at a time
- find nearby merchants that actually carry a category
- compare prices where a price can genuinely be attributed to the product
- understand availability signals — and their limits
- discover alternatives and adjacent variants
- compare marketplace listings alongside direct merchant listings

The goal is not search. Search returns pages. The goal is:

```
Search
   ↓
Relevant Product      ← the right item, not a similar one
   ↓
Relevant Merchant     ← a real business, identified reliably
   ↓
Evidence              ← source, price, size, date
   ↓
Useful Shopping Information
```

> **Implemented in MarketRadar:** product discovery across merchants, product identity matching, price evidence with source and date, merchant identification. These run as business tools.
>
> **Future opportunity:** a shopper-facing interface, personalised recommendations, saved lists, alerts. **Not built.**

---

## 6. Pricing Intelligence

Pricing is where the difference between data and intelligence is most consequential, because a wrong price is actionable in the wrong direction.

Useful pricing intelligence covers price comparison across merchants, local price differences, merchant-level pricing, price history, price change detection, verified price evidence, and ongoing monitoring.

### The distinction that matters most

> **"Price not verified" does not mean "product not available."**

These are separate questions and conflating them produces false conclusions about a competitor's inventory.

A merchant may list a product on a category page carrying a price that applies to the whole category. The product is genuinely there. The price simply cannot be attributed to it. Reporting that as "unavailable" would be a false negative about a real business's real stock.

### A vocabulary that keeps them apart

| State | Means | Does **not** mean |
| --- | --- | --- |
| **Verified** | A single product-specific price, identity and size confirmed | That it is the best price available |
| **Unavailable** | The product was found; no price could be attributed to it | The product is out of stock |
| **Unknown** | Insufficient evidence either way | The merchant does not sell it |
| **Unverified** | Something was observed but did not meet the bar | That it is false |

Four states, not two. Most tools collapse this to "found / not found" and lose the distinction that carries the risk.

> **Implemented in MarketRadar:** verified price evidence with strict identity and size matching; a four-state vocabulary throughout; lowest / average / highest computed across verified observations only; price change detection over recorded history.
>
> **Future opportunity:** continuous price monitoring and change alerts. **Not built.**

---

## 7. Merchant Intelligence

Before you can say anything about products or prices in a market, you have to know **who is actually in it** — and be confident that two records are, or are not, the same business.

Merchant intelligence helps a business understand who operates in a market, which merchants appear in search, where they are located, what their web presence is, what availability signals exist, whether they appear on marketplaces, and how visible they are.

### Two things make this hard

**Identity.** The same business appears as "Smith & Co Wines", "Smith and Company", and a domain that matches neither. Two branches of one chain appear as two results with one shared website. Merging them loses a location; splitting them invents a competitor. A wrong merge is particularly damaging because it is hard to detect and hard to undo.

A specific, real trap: small businesses frequently list a **social media page as their website**. Treating that page as the business's own domain means every business that does the same collapses into a single record. The page is genuine evidence the business exists — it is simply not an identity.

**Geographic relevance.** A result can be a real business, correctly identified, and in the wrong country. Search results do not reliably carry location. A business without an address or coordinates cannot have its geographic relevance confirmed, and pretending otherwise puts a distant shop in a local market report.

> **Implemented in MarketRadar:** merchant identity resolution with ranked matching (domain, then name, then address, then controlled fuzzy matching); ambiguous chains held as uncertain rather than guessed; social, directory, marketplace and publisher domains excluded from identity; government and military namespaces excluded from commercial classification; explicit flagging when geographic relevance cannot be confirmed.

---

## 8. Competitive Intelligence

Structured market information can help a business understand competitor presence in a defined market and place, what products competitors offer, what prices can be verified, how visible competitors are in search, their geographic coverage, their marketplace presence, and how these have changed across recorded observations.

### What this deliberately is not

This is factual intelligence and decision support. It does not identify a "winner", name a "market leader", or tell you how to "beat" anyone. Those framings require inferences the evidence does not support — market share, sales volume, profitability — none of which is observable from public listings.

What *is* observable, and therefore what should be reported:

| Rather than | State this |
| --- | --- |
| "Competitor X dominates" | "5 verified businesses were observed in this market and location" |
| "X is winning on price" | "One verified price of $19.99 was observed at X; no verified price was available for Y" |
| "Y is losing ground" | "Y was not present in the most recent search. Absence from one search is not evidence that a business has closed or left the market" |
| "The market is growing" | "Two distinct measurements are available; the observed value moved from 5 to 2" |

The second column is less exciting and considerably more useful, because it can be checked.

> **Implemented in MarketRadar:** competitor discovery scoped to market and location; classification separating real businesses from directories, articles, social pages and marketplaces; evidence-strength statuses (verified / discovered / uncertain); visibility signals; full observation history; rejected results kept visible so nothing disappears silently.

---

## 9. Trend Intelligence

A single snapshot tells you the state of a market. It cannot tell you whether anything is changing — and change is usually the actionable part.

Useful trend intelligence covers price movement, availability change, merchant visibility change, merchants entering or leaving a view, product movement across merchants, and marketplace changes.

### Three principles that make trend analysis honest

**1. One observation is not a trend.**

A single reading is a point. It has no direction. Reporting it as "stable" claims you watched it hold steady — you did not, you looked once.

**2. Repeated cached information is not automatically a new measurement.**

This one is easy to get wrong and hard to notice. If a system caches responses — and any system that respects its data provider's cost will — then re-running the same search returns *identical* data. If each run is recorded as an observation, you accumulate several records describing **one** measurement.

A naive system sees three records with the same value and reports "stable". It has not observed stability. It has read the same answer three times.

**3. Only genuinely distinct observations establish a direction.**

Two or more readings that actually differ, separated in time, within a comparable context. Anything less is insufficient history, and saying so plainly is more useful than a confident number.

### And one more

> **"Absent from the latest search" does not mean "closed."**

Search results vary. A business missing from one result set may simply not have been returned. Treating that as closure produces a false and potentially damaging conclusion about a real company.

> **Implemented in MarketRadar:** change detection across recorded observations; identical consecutive readings collapsed into a single measurement; direction stated only where two or more distinct measurements exist; "insufficient history" reported explicitly rather than filled in; absence from a latest search flagged with that caveat attached.
>
> **Current state, stated plainly:** because responses are cached for seven days, two genuinely distinct measurements of the same query in the same place require searches more than a week apart. With the history recorded so far, no trend series yet has enough distinct measurements to show a direction — and the system says so rather than inventing one.

---

## 10. Marketplace Intelligence

Commerce no longer happens in one place. A single product may be sold through a merchant's own website, one or more marketplaces, local shops, and platform-specific storefronts — often at different prices, under different names, by sellers whose relationship to the brand is unclear.

Looking at one channel gives a partial and potentially misleading view. A price that looks competitive on a marketplace may be uncompetitive against direct merchants, and a product that appears widely available may be listed by a handful of resellers.

The difficulty is **seller identity**. A marketplace listing attributed to a name is not the same as a listing verifiably from that business — and treating the two alike attributes prices to merchants who never set them.

> **Implemented in MarketRadar:** shopping-channel listings are used as one evidence source within price verification, and are attributed to a nearby merchant only when identity resolves confidently; evidence from a marketplace listing is recorded with a distinct scope so it is never confused with a merchant's own catalogue.
>
> **Future opportunity:** a dedicated marketplace intelligence capability — cross-channel comparison, seller-level analysis, channel coverage. **Not built.**

---

## 11. Financial Intelligence

> ### ⚠ Future opportunity — not implemented
>
> **MarketRadar performs no financial analysis of any kind today.** There is no pricing economics, no margin analysis, no revenue signal, no cost modelling. This section describes where the concept could extend, not what the system does.

Market observations are, in principle, an input to financial reasoning. Verified prices over time across identified merchants in a defined market are the raw material for questions such as:

- **Pricing economics** — how observed prices distribute across a market
- **Revenue signals** — inferred cautiously, and only where evidence genuinely supports it
- **Margin analysis** — observed prices against known costs, which would require cost data the system does not have
- **Cost considerations** — supplier and wholesale intelligence
- **Financial trends** — price movement as an economic indicator
- **Market economics** — structure, concentration, price dispersion

Each of these requires evidence the current system does not collect. Presenting them as capability would be exactly the kind of overreach this discipline exists to avoid.

---

## 12. Why AI matters

The traditional analytics pattern:

```
Data  →  Dashboard  →  Human interpretation
```

Dashboards are good at showing numbers and poor at explaining them. The interpretive work — what changed, what it means, what is missing, what to look at next — falls entirely on the reader, who must hold the caveats in their head.

The AI-assisted pattern:

```
Data  →  Evidence  →  Context  →  Structured Facts  →  AI Analysis  →  Human Decision
```

The key difference is not that AI appears. It is **where** it appears: after the facts have been established, not instead of establishing them.

AI can help with questions dashboards answer badly:

| Question | Why it is hard for a dashboard |
| --- | --- |
| *What changed?* | Requires comparing states and knowing which differences matter |
| *What prices are available?* | Requires knowing which prices are trustworthy |
| *Which products were observed?* | Requires product identity, not string matching |
| *Which merchants appeared?* | Requires identity resolution |
| *What information is missing?* | Dashboards show what exists, not what does not |
| *Is there enough history for a trend?* | Requires distinguishing measurements from repeats |
| *What should I investigate next?* | Requires reasoning over gaps |

That sixth row is the one most tools fail. Knowing what you *do not* know is a large part of market intelligence, and it is invisible on a chart.

---

## 13. Evidence-first AI

**This is the central idea of the whole approach.**

> ### Evidence first. AI second.

### AI should not be the source of truth

A language model asked to analyse a market will produce a fluent answer whether or not the evidence supports it. Fluency is not accuracy, and in commerce the errors are expensive: a confidently invented price, a competitor described as failing, a trend asserted from a single data point.

The answer is not a better prompt. It is a different architecture:

```
Evidence            ← recorded observations with source and confidence
    ↓
Structured Facts    ← computed by deterministic logic, not generated
    ↓
AI Analysis         ← narrates the facts; may not add to them
```

The facts are produced by code. The AI receives those facts — not the raw data — and explains them. Its output is then checked against the facts before anyone sees it.

The practical consequence: **if the AI is unavailable, the factual analysis is still there.** Only the narration is missing. That is the correct dependency direction.

### The vocabulary this requires

A system that cannot express uncertainty will manufacture certainty. Six states, kept distinct:

| State | Meaning |
| --- | --- |
| **Verified** | Strongest available evidence for this kind of claim |
| **Discovered** | Real, but on weaker evidence |
| **Uncertain** | Could not be distinguished reliably from something else |
| **Unknown** | Insufficient evidence either way — **never a negative finding** |
| **Unavailable** | Found, but could not be attributed |
| **Insufficient history** | Not enough distinct measurements to state a direction |

### Why this matters specifically in commerce

Three concrete cases where the honest answer and the confident answer diverge:

> **If a price cannot be verified, the system must not say the product is unavailable.**
> A shop that stocks an item would be reported as not stocking it. A buyer acts on that. A competitor is mischaracterised.

> **If a competitor is absent from one search, the system must not say the business has closed.**
> Search results vary between runs. Reporting closure is both wrong and potentially damaging to a real company.

> **If there is only one measurement, the system must not claim a trend.**
> "Prices are falling" from a single reading is a fabrication with a number attached — the most persuasive kind of error.

> **Implemented in MarketRadar:** factual statements computed deterministically from recorded evidence, each carrying a reference back to the records behind it; the AI layer receives only those computed facts; generated summaries are validated before display and withheld if they assert an unsupported conclusion or cite a figure absent from the facts; the full factual analysis is produced with or without an AI provider.
>
> **Current state, stated plainly:** no AI vendor is connected, so the system runs in **facts-only mode** today. The narration layer is built and tested; nothing is generating text at present.

---

## 14. MarketRadar as a worked example

MarketRadar is a practical implementation of this concept — **industry-agnostic by design**. Nothing in it is specific to a product category, retailer or country.

### The layers

```
Market Research        →  what does this market look like in search?
        ↓
Competitor Intelligence →  who actually operates here?
        ↓
Product Intelligence   →  what do they offer?
        ↓
Price Intelligence     →  what can be verified about price?
        ↓
Trend Intelligence     →  what has changed?
        ↓
Market Pulse           →  one coherent snapshot
        ↓
AI Analyst             →  what does the evidence show?
```

Each layer consumes only the layer beneath it. That ordering is the architecture, not a diagram convenience — it is what prevents analysis from quietly re-deriving facts it should be reading.

| Layer | Contribution |
| --- | --- |
| **Market Research** | Search visibility for a market in a resolved location — organic and local results together |
| **Competitor Intelligence** | Identifies real businesses, separates them from directories and articles, resolves identity, records evidence |
| **Product Intelligence** | Searches each merchant's own catalogue, matches product identity strictly, records what was and was not found |
| **Price Intelligence** | Verifies prices against strict identity, size and page-type rules; everything else stays unavailable with a reason |
| **Trend Intelligence** | Detects change across distinct measurements; reports insufficient history rather than inventing direction |
| **Market Pulse** | Assembles one read-only snapshot for one market and place, so sections cannot be mismatched |
| **AI Analyst** | Computes factual statements with evidence references; optionally narrates them under validation |

### The positioning

> **MarketRadar is not a search tool.** Search returns pages.
>
> It is an approach to turning fragmented commerce data into structured market intelligence — with the confidence of each claim stated, and the evidence behind it retained.

---

## 15. Worked example — wine retail

*Wine retail is used here as one illustration. The same flow applies unchanged to any category; nothing in the system is wine-specific.*

**Scenario.** An independent wine retailer wants to understand the market around their shop: who else is selling, what they carry, and what can be established about price.

### The flow

```
Raw Search
    ↓
Merchant Identification    ← which results are actual businesses?
    ↓
Product Identification     ← is this the exact product, or a near-miss?
    ↓
Price Evidence             ← can this price be attributed to this product?
    ↓
Location Context           ← is this business relevant to this place?
    ↓
Historical Observations    ← what did we see, and when?
    ↓
Market Pulse               ← one coherent picture
    ↓
AI Analysis                ← what does the evidence show?
```

### What each step produces

**Raw search** returns a mixture: shops, a review directory, a social page, an article listing "the best wine shops", a regional guide. Roughly half is not a business.

**Merchant identification** separates them. Directories and articles are set aside — and kept visible, with the reason, rather than silently dropped. Real businesses are identified by domain, place record, name and address. Two branches of one chain are held as uncertain rather than merged.

**Product identification** is where near-misses are caught. A search for a specific 750ml wine will surface the same producer's other bottlings, different vintages, gift packs and multipacks. Each is rejected with a stated reason — different size, different variant. Harmless differences are normalised (`750 ML` and `750ml`; `No. Twelve` and `No 12`), but a 50ml and a 750ml are never treated as the same product.

**Price evidence** applies the strict rules. A price on a product page, for the confirmed size, at a confidently identified merchant, becomes **verified**. A price on a category page — which belongs to some product in a list — becomes **unavailable**, with the reason recorded. The product is still reported as found.

**Location context** confirms geographic relevance where address or coordinates exist, and flags it explicitly where they do not.

**Historical observations** record each discovery with a timestamp, so later searches can be compared rather than overwritten.

**Market Pulse** assembles one snapshot for that market and place: businesses observed and their evidence strength, products and their status, verified prices, visibility signals, and an explicit data-quality section.

**AI analysis** produces statements such as:

- *"5 verified businesses were observed in this market and location."*
- *"1 verified price measurement is available: $19.99 for the exact product and size requested."*
- *"2 product observations are 'unknown' — the evidence was insufficient either way. That is not a finding that the merchant does not stock the product."*
- *"2 businesses were not present in the latest observation. Absence from one search is not evidence that a business has closed or left the market."*
- *"1 business had no address or coordinates reported, so geographic relevance could not be verified."*

Every one of those traces back to specific records.

### What this does not claim

No sales forecast. No revenue projection. No statement that one shop is outperforming another. No recommendation to change price. The retailer gets an organised, sourced, honestly-caveated picture of their market — and makes their own decision.

---

## 16. Other industries

The concept is category-agnostic. These are **potential applications** of Commerce & Market Intelligence — not existing MarketRadar integrations.

### Grocery
Product prices across local stores, promotional pricing, local availability signals, basket-level comparison. High product turnover and dense local competition make frequent, structured observation particularly useful.

### Electronics
Product pricing across merchants and marketplaces, availability, model and variant disambiguation. Strict identity matching matters enormously — storage tiers, model years and regional variants are trivially confused and expensively wrong.

### Fashion
Availability by size and colourway, price monitoring through markdown cycles, marketplace presence, seasonal movement. Variant explosion makes product identity the central challenge.

### Automotive
Local dealer and service-provider discovery, parts and service pricing, competitor presence by area, geographic coverage. Strongly local, which makes location resolution essential.

### Beauty
Product discovery across merchants, price comparison, merchant presence, marketplace listings. Shade, size and set variants make identity matching decisive.

### Home & Furniture
Product discovery, pricing across large-format retailers, marketplace monitoring, regional availability. High price dispersion makes comparison valuable.

### Sports & Fitness
Equipment pricing, merchant availability, marketplace visibility, seasonal patterns.

### B2B Commerce
Supplier discovery in a category and region, pricing intelligence where published, competitive research, market structure. Often the least well-served by consumer-oriented tools.

---

## 17. Who benefits

### Shoppers
Better product discovery across merchants rather than one site at a time, and price visibility with a clear indication of what is actually verified.
*Concept-level. MarketRadar has no shopper-facing product today.*

### Small businesses
Competitive and market research of a kind usually available only to organisations that can afford enterprise platforms. **This is arguably the strongest case**: the gap between what large retailers know about their markets and what independents know is largely a tooling gap.

### Retailers
Pricing visibility across a local market, product intelligence about what competitors carry, competitor presence and visibility — with evidence attached rather than asserted.

### E-commerce teams
Marketplace and channel intelligence, product identity across listings, price positioning. The identity problem is acute here, where the same product is listed many ways by many sellers.

### Analysts
Structured market research with sources retained, so time shifts from collecting toward analysing — and any figure can be traced to the record behind it.

### Business teams
Evidence-based market understanding in language that states its own confidence, so a decision-maker can see what is solid and what is not.

---

## 18. Business value

Framed as what this **can** support — not as guarantees.

**Can reduce manual research effort.** Discovery, identity resolution and evidence collection are repeatable, so effort moves toward interpretation.

**Can organise fragmented information.** Signals from several sources become one structured picture per market and place.

**Can improve pricing visibility.** Where a price can be verified, it is verified. Where it cannot, that is stated — which is also useful.

**Can support understanding of competitor presence.** Who operates in a market, with evidence strength attached.

**Can enable monitoring of market change.** Recorded observations make change detectable, where enough distinct measurements exist.

**Can identify information gaps.** The system reports what is missing — businesses with no website, evidence that could not confirm location, insufficient history. Knowing what you do not know is genuinely actionable.

**Can support better decisions.** Traceable evidence and stated confidence give a decision-maker something to weigh.

**Can make market intelligence accessible to smaller businesses.** The research discipline of a large organisation, at a scale a small one can use.

### What it does not do

It does not guarantee outcomes, increase revenue, predict sales, or determine competitive position. It organises evidence. People decide.

---

## 19. From data to decision

```
                    Commerce Data
                          ↓
      Products · Prices · Merchants · Finance
           Trends · Marketplaces
                          ↓
                      Evidence          ← sourced, timestamped, identity-resolved
                          ↓
                      Context           ← market, location, time
                          ↓
               Market Intelligence      ← organised and comparable
                          ↓
                    AI Analysis         ← explains the evidence
                          ↓
                  Human Decision        ← judgement, priorities, risk
```

### Why the human step is last — and stays last

Not deference. Three practical reasons.

**The system sees public signals only.** It does not know your costs, contracts, supplier relationships, strategy or constraints. A price observation is one input among many the decision-maker holds.

**Evidence has limits, and they matter.** "Insufficient history" and "geographic relevance unconfirmed" are not failures — they are information a person must weigh. A system that resolved them automatically would be inventing certainty.

**Judgement is the point.** Whether a competitor's price matters depends on positioning, margin and intent. The evidence informs that call. It cannot make it.

A tool that makes the decision for you has to be right. A tool that gives you traceable evidence and states its confidence only has to be honest — a far more achievable and far more useful standard.

---

## 20. The future of Commerce Intelligence

> ### ⚠ FUTURE OPPORTUNITIES
>
> Everything in this section is **not currently implemented** in MarketRadar. These are directions the concept could extend, described as possibility.

**Continuous market monitoring.** Scheduled observation so history accumulates without manual searching — which is what makes trend analysis genuinely useful.

**AI research agents.** Autonomous investigation of specific questions, gathering evidence toward an answer.

**Marketplace intelligence.** A dedicated capability for cross-channel comparison and seller-level analysis.

**Automated competitive research.** Recurring competitive reviews, produced on a cadence.

**Financial intelligence.** Pricing economics, margin analysis, market structure — requiring cost data not currently collected.

**Personalised shopping intelligence.** Consumer-facing discovery shaped by preference and location.

**Predictive analytics.** Forecasting from history — and only with enough history to support it honestly, which is a high bar and easily abused.

**Automated alerts.** Notification when something meaningful changes, rather than when anything changes.

**Natural-language market analysis.** Conversational questions against recorded evidence, answered within the same evidence discipline.

**Cross-market comparison.** One market against another, one region against another.

### The constant

Whatever gets added, the ordering holds:

> **Evidence first. AI second.**

Every future capability makes the discipline more important, not less. A monitoring system that reports phantom changes is worse than no monitoring. A predictive model built on measurements that were actually cached repeats is worse than no model. Capability without evidence discipline does not produce better intelligence — it produces more confident errors, faster.

---

## Summary — current vs future

### Implemented in MarketRadar today

| Capability | |
| --- | --- |
| Market research with location resolution | Organic and local search for a market in a resolved place |
| Competitor discovery and identity | Real businesses separated from directories, articles, social pages; identity resolved; ambiguity preserved |
| Product intelligence | Merchant catalogue evidence with strict product identity matching |
| Price intelligence | Verified prices under strict rules; four-state vocabulary; statistics over verified observations only |
| Trend intelligence | Change across distinct measurements; insufficient history reported honestly |
| Market Pulse | One coherent read-only snapshot per market and location |
| AI Analyst | Deterministic facts with evidence references; validated narration layer |
| Evidence discipline | Six-state confidence vocabulary; sources and timestamps retained throughout |

### Future opportunities — not implemented

Financial intelligence · continuous monitoring and alerts · dedicated marketplace intelligence · predictive analytics · shopper-facing product · personalised recommendations · conversational Q&A · cross-market comparison · AI research agents · connected AI vendor (the narration layer is built; no provider is connected, so the system runs facts-only today)

---

*Commerce & Market Intelligence — turning fragmented commerce data into evidence you can act on.*
*MarketRadar. Evidence first. AI second.*
