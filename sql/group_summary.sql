-- Dashboard-ready group summary. Weighted counts are population estimates from survey weights;
-- unweighted counts are respondents. Variance and confidence intervals come from the survey module.
create or replace table group_summary as
with pooled as (
    select race_label as group_name, * from cohort
    union all
    select 'All groups' as group_name, * from cohort
)
select
    group_name,
    count(*) as respondents,
    sum(weight) as weighted_population,
    sum(hba1c_pos) as hba1c_positive_respondents,
    sum(weight * hba1c_pos) as weighted_hba1c_positive,
    sum(weight * hba1c_pos) / sum(weight) as hba1c_positive_share,
    sum(hba1c_pos * diagnosed) as diagnosed_among_positive,
    sum(hba1c_pos * (1 - diagnosed)) as undiagnosed_among_positive,
    sum(weight * hba1c_pos * (1 - diagnosed)) as weighted_undiagnosed,
    case when sum(weight * hba1c_pos) > 0
         then sum(weight * hba1c_pos * (1 - diagnosed)) / sum(weight * hba1c_pos) end
         as undiagnosed_share
from pooled
group by group_name
order by group_name;
