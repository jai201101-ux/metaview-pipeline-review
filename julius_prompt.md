# Julius, corrected prompt

Paste this with the same workbook attached. Three things changed from the July prompt: deals are
counted once, the chart labels are built from the right columns, and every number on the page is
computed, not typed in.

---

Analyse the attached Salesforce workbook. Reporting period: May 2026, compared with April 2026. AE target treatment: full monthly target (ENT $125,000, MM and SMB $100,000).

Counting rule, which overrides everything else: the export has one row per product line, and the deal's Amount is repeated on every line. Count each Opportunity ID once. Deal value in USD is the sum of "Total Price (converted)" across the deal's lines. Use the product lines only for the product chart. Confirm at the start: 15,510 source rows, 15,056 deals, 454 lines collapsed.

Won month is the Stage 7W Entered Date, lost month is the Stage 7L Entered Date. Treat the 1,330 deals closed lost on 13 May 2026 as a bulk hygiene close-out: keep them, show them as a separate grey bar, and exclude them from every win rate.

Produce these ten outputs, one chart each, dark theme (background #0B0F14, text #F3F4F6, cyan #22D3EE, green #22C55E, red #F87171, grey #6B7280):
1. Period scorecard: won count, won value, average won deal, real lost count and value, bulk close-out count, win rate excluding the bulk close-out, open pipeline count, value and weighted value.
2. Won and lost trend, 12 months ending May 2026, bulk close-out as a third series.
3. Regional performance, May versus April won value, EMEA and AMER. Label each bar with its own month's value. Do not label a May bar with an April figure.
4. Segment performance, same rule, ENT, MM, SMB.
5. Top 10 products by won value in May, from product lines of won deals.
6. Open pipeline by stage, open value and weighted value.
7. Open pipeline by region.
8. Open pipeline by segment.
9. AE target attainment for every AE, one bar each, green at or above 100%, amber 50 to 99%, red below 50%. Include AEs with no May win.
10. Priority deals: open deals with a close date in May or June 2026, ranked by weighted value, one row per deal, with a risk flag when the close date has passed, days in stage exceed 1.5 times the stage median, or the amount is missing.

Then: the 20% growth check (May versus April plus 20%; June needed versus June pipeline, unweighted and weighted), three findings, three actions, and a data quality section.

Rules for the output: compute every figure in the final page from the data in the same run; never paste a number from an earlier cell. Round money to the nearest dollar and percentages to one decimal in every table. Where a figure cannot be computed, say so rather than estimating.

Sanity values to check your own output against before finishing: May won 136 deals and $1,110,259; April won 154 deals and $1,252,205; 4 AEs at or above target; open pipeline 926 deals, $18,740,429, weighted $6,602,438. If any of these differ by more than 1%, find the cause and report it rather than overriding the number.
