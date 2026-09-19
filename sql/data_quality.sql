-- Data-quality gates on the analysis cohort. Every row must pass or the pipeline stops.
create or replace table data_quality as
select 'seqn_unique' as check_name,
       count(*) = count(distinct seqn) as passed,
       'rows=' || count(*) || ' distinct=' || count(distinct seqn) as detail
from cohort
union all
select 'weights_positive', coalesce(min(weight), 0) > 0, 'min weight=' || min(weight) from cohort
union all
select 'psu_masked_values', count(*) = 0, 'rows with psu not in (1,2)=' || count(*)
from cohort where psu not in (1, 2)
union all
select 'no_lonely_psu_strata',
       coalesce(min(k), 0) >= 2,
       'min PSUs per stratum=' || coalesce(min(k), 0)
from (select stratum, count(distinct psu) as k from cohort group by stratum)
union all
select 'race_categories_allowed', count(*) = 0, 'unexpected categories=' || count(*)
from cohort
where race_label not in ('Mexican American', 'Other Hispanic', 'Non-Hispanic White',
                         'Non-Hispanic Black', 'Non-Hispanic Asian', 'Other/Multiracial')
union all
select 'diagnosed_is_binary', count(*) = 0, 'non-binary rows=' || count(*)
from cohort where diagnosed not in (0, 1) or diagnosed is null
union all
select 'hba1c_present_and_plausible',
       count(*) = 0, 'rows with hba1c null or outside 3..20=' || count(*)
from cohort where hba1c is null or hba1c < 3 or hba1c > 20
union all
select 'hba1c_positive_group_present',
       count(*) filter (where hba1c_pos = 1) > 0,
       'hba1c positives=' || count(*) filter (where hba1c_pos = 1)
from cohort
union all
select 'age_in_survey_range', count(*) = 0, 'rows outside 12..80=' || count(*)
from cohort where age < 12 or age > 80
union all
select 'missingness_reported', true,
       'bmi=' || count(*) filter (where bmi is null)
       || ' insured=' || count(*) filter (where insured is null)
       || ' routine_care=' || count(*) filter (where routine_care is null)
       || ' family_history=' || count(*) filter (where family_history is null)
from cohort;
