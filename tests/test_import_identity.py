"""Identité d'un contact à l'import : quand demander, quand suivre LinkedIn.

Chaque cas vient d'une mesure du 22/11 sur la pile des contacts « ambigus » de la sync LinkedIn
(29 noms) : une vingtaine étaient la même personne déjà en base, dont les mises à jour étaient
refusées à chaque passage — soit parce que l'URL LinkedIn avait changé, soit parce que seul
l'affichage du nom avait bougé.
"""

import os

import pytest

from people_memory.config import Settings
from people_memory.db import Database
from people_memory.repository import GraphRepository

pytestmark = pytest.mark.integration


def _repo() -> GraphRepository:
    url = os.environ.get("PEOPLE_MEMORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PEOPLE_MEMORY_TEST_DATABASE_URL is not set")
    settings = Settings(
        database_url=url,
        api_token=None,
        enable_raw_sql=False,
        default_source="test",
        cors_origins=(),
    )
    repo = GraphRepository(Database(settings))
    with repo.db.connection() as conn:
        conn.execute(
            "truncate deleted_records, interactions, facts, edges, affiliations, identifiers, "
            "orgs, people restart identity cascade"
        )
    return repo


def test_changed_linkedin_slug_is_followed_not_blocking() -> None:
    """Un slug LinkedIn modifié n'est pas une contradiction : c'est le même profil."""
    repo = _repo()
    old_url = "https://www.linkedin.com/in/bastien-morel-15280a171"
    new_url = "https://www.linkedin.com/in/bastien-morel1"
    created = repo.remember_person(
        full_name="Bastien Morel",
        current_org="Atelier Vert",
        current_role="Customer success manager",
        linkedin_url=old_url,
        confirmed_new=True,
        source="test",
    )
    assert created["status"] == "created"
    person_id = created["person"]["id"]

    again = repo.remember_person(
        full_name="Bastien Morel",
        current_org="Skello",
        current_role="FinOps Analyst",
        linkedin_url=new_url,
        source="linkedin",
    )
    assert again["status"] == "updated", again
    assert again["person"]["id"] == person_id
    fetched = repo.get_person(person_id)
    assert fetched["linkedin_url"] == new_url
    assert fetched["current_org"] == "Skello"
    with repo.db.connection() as conn:
        urls = {
            row["value"]
            for row in conn.execute(
                "select value from identifiers where kind = 'linkedin'"
            ).fetchall()
        }
    # L'ancien slug reste un identifiant : une vieille exportation continue de le reconnaître.
    assert {old_url.lower(), new_url.lower()} <= urls


def test_name_rendering_on_the_same_profile_is_not_a_conflict() -> None:
    """Emoji, accent ou abréviation sur un même profil : même personne, mise à jour appliquée."""
    repo = _repo()
    url = "https://www.linkedin.com/in/luc-moreau"
    created = repo.remember_person(
        full_name="Luc Moreau 🦂",
        current_org="Maison Lune",
        linkedin_url=url,
        confirmed_new=True,
        source="test",
    )
    assert created["status"] == "created"
    person_id = created["person"]["id"]

    again = repo.remember_person(
        full_name="Luc Moreau",
        current_org="Equans Digital Cyber",
        current_role="SOC Perimeter",
        linkedin_url=url,
        source="linkedin",
    )
    assert again["status"] == "updated", again
    fetched = repo.get_person(person_id)
    assert fetched["current_org"] == "Equans Digital Cyber"
    # Le nom stocké n'est pas réécrit à la légère : seul le contenu professionnel suit LinkedIn.
    assert fetched["full_name"] == "Luc Moreau 🦂"
    with repo.db.connection() as conn:
        assert conn.execute("select count(*) as n from people").fetchone()["n"] == 1


def test_shared_first_name_alone_creates_a_new_person() -> None:
    """Un prénom partagé n'est pas une ressemblance de nom : deux fiches."""
    repo = _repo()
    created = repo.remember_person(
        full_name="Camille Morin", confirmed_new=True, source="test"
    )
    assert created["status"] == "created"

    other = repo.remember_person(full_name="Camille Lemoine", source="linkedin")
    assert other["status"] == "created", other
    with repo.db.connection() as conn:
        assert conn.execute("select count(*) as n from people").fetchone()["n"] == 2


def test_shared_email_with_a_different_name_still_asks() -> None:
    """La prudence d'origine tient : un email peut être partagé, il n'identifie pas à lui seul."""
    repo = _repo()
    created = repo.remember_person(
        full_name="Ada Lovelace", email="ada@example.com", confirmed_new=True, source="test"
    )
    assert created["status"] == "created"

    collision = repo.remember_person(
        full_name="A Different Person", email="ada@example.com", source="test"
    )
    assert collision["status"] == "needs_confirmation"


def test_unrelated_name_on_a_shared_identifier_still_asks() -> None:
    """Un identifiant mal rattaché doit rester visible, pas être absorbé en silence.

    Cas mesuré le 22/11 : deux contacts de la pile portaient un profil LinkedIn rangé sous un nom
    qui n'a rien à voir — c'est une erreur de données, et elle doit se voir.
    """
    repo = _repo()
    url = "https://www.linkedin.com/in/nova-lumen"
    created = repo.remember_person(
        full_name="Nova Lumen", linkedin_url=url, confirmed_new=True, source="test"
    )
    assert created["status"] == "created"

    mismatched = repo.remember_person(
        full_name="Aster Vale", current_org="Skello", linkedin_url=url, source="linkedin"
    )
    assert mismatched["status"] == "needs_confirmation"


def test_abbreviated_surname_on_the_same_profile_is_the_same_person() -> None:
    """« Landry F » et « Landry FOKAM » : un nom abrégé, pas une autre personne."""
    repo = _repo()
    url = "https://www.linkedin.com/in/landry-fokam-61569923a"
    created = repo.remember_person(
        full_name="Landry FOKAM",
        current_org="Voltalia",
        linkedin_url=url,
        email="landry.fokam@example.com",
        confirmed_new=True,
        source="test",
    )
    assert created["status"] == "created"

    again = repo.remember_person(
        full_name="Landry F",
        current_org="Voltalia",
        current_role="Investment Analyst",
        linkedin_url=url,
        source="linkedin",
    )
    assert again["status"] == "updated", again
    assert again["person"]["id"] == created["person"]["id"]
