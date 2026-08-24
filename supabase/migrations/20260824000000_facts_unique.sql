-- One fact per (person, key, value): declare the invariant the code already relies on.
--
-- Context (2026-08-24): the production database carried `facts_person_key_value_uidx` while the
-- migrations did not, so a fresh database and production disagreed about whether a person could
-- hold the same fact twice. `add_fact` treats re-asserting a known fact as a no-op, which is only
-- meaningful if the database enforces uniqueness — otherwise the same LinkedIn connection date
-- accumulates a new row on every sync.
--
-- Partial (value is not null): a numeric-only fact leaves `value` null, and several null-valued
-- rows for one key are legitimate (repeated measurements of the same quantity).
--
-- We refuse to delete anything. If the table already holds duplicates, the index is skipped with a
-- notice telling the operator what to look at: which rows to merge is their call, not this
-- migration's.
do $$
declare
  dupes bigint;
begin
  select count(*) into dupes from (
    select person_id, key, value
    from facts
    where value is not null
    group by person_id, key, value
    having count(*) > 1
  ) d;

  if dupes > 0 then
    raise notice
      'facts: % duplicate (person_id, key, value) group(s) — unique index NOT created. Inspect with: select person_id, key, value, count(*) from facts where value is not null group by 1,2,3 having count(*) > 1; then merge or delete the extra rows and re-run this migration.',
      dupes;
  else
    create unique index if not exists facts_person_key_value_uidx
      on facts (person_id, key, value)
      where value is not null;
  end if;
end
$$;
