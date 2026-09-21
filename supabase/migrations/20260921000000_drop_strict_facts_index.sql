-- Drop `facts_person_key_value_uidx`, a unique index this fork once added and upstream never had.
--
-- Why it existed: a fork-only migration (20260824000000_facts_unique.sql) made (person_id, key, value)
-- unique so that re-asserting a known fact would be a no-op instead of raising. Upstream reached the
-- same goal differently, and better: `facts_person_key_value_date_num_uidx` keys on the date and the
-- number too, so "Lupi worked at X in 2024" and "Lupi worked at X in 2026" are two facts rather than
-- one overwriting the other. That is the right semantics for a memory about people — a value that
-- changes over time is history, not a duplicate.
--
-- Why it must go rather than merely be ignored: with both indexes present, upstream's add_fact keys
-- its ON CONFLICT on the date/num index, so a fact re-appearing with a *different* date satisfies
-- that index and then hits this one — a UniqueViolation raised from outside the ON CONFLICT clause,
-- which nothing catches. Every LinkedIn sync that refreshed a dated fact would fail.
--
-- Dropping a uniqueness constraint destroys no row: it only stops refusing future ones. The rows this
-- index was keeping unique stay exactly as they are.
--
-- `if exists` because an installation created after this fork's migration was dropped never had it.

drop index if exists facts_person_key_value_uidx;
