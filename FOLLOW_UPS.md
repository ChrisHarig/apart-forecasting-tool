# Follow-ups

Stuff to come back to once the multi-pane workspace lands. Captured so we
don't lose them while we're focused on the bigger refactor.

## 1. Chart toolbar box alignment

The **Metric**, **Group by**, and **Filters** boxes in `SourceTimelineChart`
render at slightly different vertical heights, and the inner controls
(`<select>`s, the `+` button, the small meta lines) sit at different vertical
positions across boxes. Audit so all three boxes share a common baseline /
height and the inner controls line up. Different *horizontal* widths are
fine — it's the vertical drift that reads sloppy.

## 2. Year-over-year / season-over-season overlay

Add a graph option that takes one continuous time axis and slices it into
recurring periods (years, flu seasons, months, ...), then renders one line
per period overlaid on a shared X axis (e.g. epiweek 40 → 39). Useful for
seasonality comparisons — at a glance: "is this year's flu peak earlier
or later than the last five?".

Non-trivial because it changes both the X axis interpretation (calendar
date → relative position within a period) and the bucketing logic (we'd
group by `period × within-period-position` instead of `date`). Probably
its own chart mode toggle alongside the existing time-series.

## 3. Rename Group by / Filter; clarify semantics

We default to **summing per timestamp** (or `mean`/`max` per the
column's declared aggregation). That makes the current "Group by" a
*disaggregation* — it splits the default aggregate into multiple lines.
"Group by" reads like an aggregation operation but it's actually the
inverse here.

Likely renames:

- **Group by → Split by** (more accurate to what it does)
- **Filter → Where** (or keep as Filter, but document; the friction is
  more about the *combination* with split-by than the name)

Edge case to think through: when the user splits by column X, does it
still make sense to allow filtering on column X simultaneously? Probably
not — pre-filtering before split is fine, but post-filter on the split
axis is just hiding series. Consider:

- Hide column X from the filter `+` menu when X is the split axis
- Or keep it but treat it as "which split values to show" — equivalent
  to the existing Series picker

Either way: the same column shouldn't be expressible as filter + split
in two different places.
