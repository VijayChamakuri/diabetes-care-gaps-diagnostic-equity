-- Cohort construction for the NHANES 2017-2018 undiagnosed-diabetes analysis.
-- Parameters: $min_age, $borderline_include (boolean), $borderline_value (0 or 1), $hba1c_threshold.
-- Missing-data codes 7 (refused) and 9 (do not know) are treated as missing, never as "no".

create or replace table cohort_base as
select
    d.seqn,
    d.ridageyr as age,
    d.riagendr as sex_code,
    d.ridreth3 as race_code,
    case d.ridreth3
        when 1 then 'Mexican American'
        when 2 then 'Other Hispanic'
        when 3 then 'Non-Hispanic White'
        when 4 then 'Non-Hispanic Black'
        when 6 then 'Non-Hispanic Asian'
        when 7 then 'Other/Multiracial'
    end as race_label,
    d.wtmec2yr as weight,
    d.sdmvpsu as psu,
    d.sdmvstra as stratum,
    q.diq010,
    g.lbxgh as hba1c,
    b.bmxbmi as bmi,
    case h.hiq011 when 1 then 1 when 2 then 0 end as insured,
    case u.huq030 when 1 then 1 when 3 then 1 when 2 then 0 end as routine_care,
    case m.mcq300c when 1 then 1 when 2 then 0 end as family_history
from raw_demo d
left join raw_diq q on q.seqn = d.seqn
left join raw_ghb g on g.seqn = d.seqn
left join raw_bmx b on b.seqn = d.seqn
left join raw_hiq h on h.seqn = d.seqn
left join raw_huq u on u.seqn = d.seqn
left join raw_mcq m on m.seqn = d.seqn;

create or replace table cohort_attrition as
with steps(step, description, n) as (
    values
    (1, 'NHANES 2017-2018 participants (DEMO_J)',
        (select count(*) from cohort_base)),
    (2, 'Examined, with a positive MEC exam weight',
        (select count(*) from cohort_base where weight > 0)),
    (3, 'Meets the minimum age',
        (select count(*) from cohort_base where weight > 0 and age >= $min_age)),
    (4, 'Valid diabetes questionnaire answer (yes, no or borderline)',
        (select count(*) from cohort_base
          where weight > 0 and age >= $min_age and diq010 in (1, 2, 3))),
    (5, 'Borderline answers handled per the analysis variant',
        (select count(*) from cohort_base
          where weight > 0 and age >= $min_age and diq010 in (1, 2, 3)
            and (diq010 <> 3 or $borderline_include))),
    (6, 'HbA1c measured',
        (select count(*) from cohort_base
          where weight > 0 and age >= $min_age and diq010 in (1, 2, 3)
            and (diq010 <> 3 or $borderline_include) and hba1c is not null)),
    (7, 'Known race and ethnicity (analysis cohort)',
        (select count(*) from cohort_base
          where weight > 0 and age >= $min_age and diq010 in (1, 2, 3)
            and (diq010 <> 3 or $borderline_include) and hba1c is not null
            and race_label is not null))
)
select step, description, n,
       coalesce(lag(n) over (order by step) - n, 0) as removed
from steps
order by step;

create or replace table cohort as
select
    seqn,
    age,
    case when sex_code = 2 then 1 else 0 end as female,
    race_label,
    weight,
    psu,
    stratum,
    case when diq010 = 1 then 1 when diq010 = 2 then 0 else $borderline_value end as diagnosed,
    hba1c,
    case when hba1c >= $hba1c_threshold then 1 else 0 end as hba1c_pos,
    bmi,
    insured,
    routine_care,
    family_history
from cohort_base
where weight > 0
  and age >= $min_age
  and diq010 in (1, 2, 3)
  and (diq010 <> 3 or $borderline_include)
  and hba1c is not null
  and race_label is not null;
