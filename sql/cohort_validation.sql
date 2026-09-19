-- Independent recount of the cohort straight from the raw tables, plus attrition invariants.
create or replace table cohort_validation as
select 'attrition_never_increases' as check_name,
       count(*) = 0 as passed,
       'steps that add rows=' || count(*) as detail
from (select n - lag(n) over (order by step) as delta from cohort_attrition)
where delta > 0
union all
select 'attrition_last_step_equals_cohort',
       (select n from cohort_attrition order by step desc limit 1) = (select count(*) from cohort),
       'attrition=' || (select n from cohort_attrition order by step desc limit 1)
       || ' cohort=' || (select count(*) from cohort)
union all
select 'independent_recount_matches',
       (select count(*)
          from raw_demo d
          join raw_diq q on q.seqn = d.seqn
          join raw_ghb g on g.seqn = d.seqn
         where d.wtmec2yr > 0 and d.ridageyr >= $min_age
           and q.diq010 in (1, 2, 3) and (q.diq010 <> 3 or $borderline_include)
           and g.lbxgh is not null and d.ridreth3 in (1, 2, 3, 4, 6, 7))
       = (select count(*) from cohort),
       'recount vs cohort'
union all
select 'first_step_equals_demo_rows',
       (select n from cohort_attrition where step = 1) = (select count(*) from raw_demo),
       'demo rows=' || (select count(*) from raw_demo);
